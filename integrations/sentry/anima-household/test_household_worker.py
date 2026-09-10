"""Credential-free host tests: queue fencing, process limits and transport."""

from __future__ import annotations

import http.client
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anima_household_client import AnimaHouseholdClient, AnimaHouseholdError
from codex_model import (
    FINAL_SCHEMA,
    CodexHouseholdModel,
    CodexUnavailable,
    child_environment,
    diagnostic_error,
    plan_schema,
    validate_calls,
)
from household_worker import ActiveLease, HouseholdWorker, main
from sentry_turn import SentryHouseholdTurn

TOOL = {
    "tool_id": "household.read",
    "availability": True,
    "input_schema": {
        "type": "object",
        "properties": {"resource": {"type": "string"}},
        "required": ["resource"],
        "additionalProperties": False,
    },
}
CALL = {"tool_id": "household.read", "arguments": {"resource": "synthetic"}}
FINAL = {
    "response": "ok",
    "decision_summary": "The bounded evidence supports a concise response.",
    "confidence": "MEDIUM",
    "information_gaps": [],
}


def decision_tool(name: str) -> dict:
    return {
        "tool_id": f"anima.knowledge.{name}",
        "availability": True,
        "content_persistence": "FULL_DURABLE",
        "input_schema": {
            "type": "object",
            "properties": {
                "note_type": {"type": "string", "enum": ["event", "decision"]},
            },
        },
    }


class ClientFixture:
    def __init__(self):
        self.events = []
        self.empty = False
        self.lease = "RENEWED"
        self.start = "PROVIDER_RUNNING"
        self.outcome = "SUCCEEDED"
        self.submissions = []

    def open_interaction(self, *args):
        self.events.append("claim")
        if self.empty:
            return {"status": "EMPTY"}
        return {"status": "CLAIMED", "provider_id": "sentry", "request_id": "r", "binding": "b"}

    def context(self, *args):
        self.events.append("context")
        return {"user_text": "synthetic"}

    def tools(self, *args):
        self.events.append("catalogue")
        return {"tools": [TOOL]}

    def provider_start(self, *args):
        self.events.append("start")
        return {"status": self.start}

    def renew(self, *args):
        self.events.append("renew")
        return {"status": self.lease}

    def invoke(self, *args):
        self.events.append("invoke")
        return {"status": self.outcome}

    def submit_result(self, *args, **kwargs):
        self.events.append("submit")
        self.submissions.append(kwargs)
        return {"status": "RECORDED"}


class ModelFixture:
    def __init__(self, client):
        self.client = client
        self.auth = True
        self.calls = [CALL]
        self.heartbeat = lambda: None
        self.error = None

    def check_auth(self):
        return self.auth

    def plan(self, context, tools):
        self.heartbeat()
        self.client.events.append("model-plan")
        if self.error:
            raise CodexUnavailable(self.error)
        return {"calls": self.calls}

    def final(self, context, results):
        self.heartbeat()
        self.client.events.append("model-final")
        return "synthetic response never logged"


class IterativeModelFixture(ModelFixture):
    def __init__(self, client, planner):
        super().__init__(client)
        self.planner = planner
        self.rounds = []
        self.final_context = None

    def plan_round(self, context, tools, results, *, round_number, remaining_calls):
        self.heartbeat()
        self.client.events.append("model-plan")
        self.rounds.append((round_number, remaining_calls))
        return self.planner(context, tools, results, round_number, remaining_calls)

    def final(self, context, results):
        self.final_context = context
        return super().final(context, results)


class HealthCheckTests(unittest.TestCase):
    def check_health(self, payload):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", ["worker", "--check"]),
            patch("household_worker.signal.signal"),
            patch("household_worker.CodexHouseholdModel") as model,
            patch("household_worker.AnimaHouseholdClient") as client,
            patch("household_worker.HouseholdWorker") as worker,
            redirect_stdout(output),
        ):
            model.return_value.check_auth.return_value = True
            client.return_value.call.return_value = payload
            code = main()
            client.return_value.call.assert_called_once_with("/v1/health")
            client.return_value.open_interaction.assert_not_called()
            model.return_value.run.assert_not_called()
            worker.assert_not_called()
        return code, json.loads(output.getvalue())

    def test_real_core_health_state_is_ready_without_claim_or_model_call(self):
        code, output = self.check_health(
            {
                "detail": None,
                "provider_id": "anima-core",
                "state": "available",
                "version": "1",
            }
        )
        self.assertEqual(code, 0)
        self.assertEqual(output["status"], "READY")
        self.assertEqual(output["auth"], "CHATGPT_LOGIN_STATUS_ONLY")

    def test_missing_or_unavailable_state_fails_even_with_available_status(self):
        for payload in (
            {},
            {"status": "available"},
            {"state": "unavailable"},
            {"state": "unavailable", "status": "available"},
        ):
            with self.subTest(payload=payload):
                code, output = self.check_health(payload)
                self.assertEqual(code, 2)
                self.assertEqual(output["reason"], "ANIMA_CORE_UNAVAILABLE")

    def test_persistent_worker_recovers_from_transient_core_failure(self):
        class StopAfterBackoff:
            def __init__(self):
                self.stopped = False

            def is_set(self):
                return self.stopped

            def wait(self, _seconds):
                self.stopped = True
                return True

        output = io.StringIO()
        stop = StopAfterBackoff()
        with (
            patch.object(sys, "argv", ["worker", "--poll-seconds", "0.5"]),
            patch("household_worker.signal.signal"),
            patch("household_worker.threading.Event", return_value=stop),
            patch("household_worker.CodexHouseholdModel") as model,
            patch("household_worker.AnimaHouseholdClient"),
            patch("household_worker.HouseholdWorker") as worker,
            redirect_stdout(output),
        ):
            model.return_value.check_auth.return_value = True
            worker.return_value.run_once.side_effect = AnimaHouseholdError("private")
            code = main()
        self.assertEqual(code, 0)
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(records[0]["status"], "WORKER_STARTED")
        self.assertEqual(
            records[1],
            {
                "status": "WORKER_RECOVERING",
                "reason": "ANIMA_CLIENT_UNAVAILABLE",
                "attempt": 1,
            },
        )


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.client = ClientFixture()
        self.model = ModelFixture(self.client)
        self.worker = HouseholdWorker(self.client, self.model)

    def test_idle_has_no_model_or_renewal(self):
        self.client.empty = True
        self.assertEqual(self.worker.run_once(), {"status": "IDLE"})
        self.assertEqual(self.client.events, ["claim"])

    def test_unexpected_exceptions_report_only_stage_and_type_without_retry(self):
        cases = (
            ("context", "CONTEXT"),
            ("tools", "CATALOGUE"),
            ("provider_start", "PROVIDER_START"),
            ("invoke", "TOOL_INVOKE"),
            ("submit_result", "RESULT_SUBMIT"),
        )
        for method, stage in cases:
            with self.subTest(stage=stage):
                client = ClientFixture()
                model = ModelFixture(client)
                output = io.StringIO()
                with patch.object(
                    client, method, side_effect=TypeError("PRIVATE_SENTINEL")
                ) as fail:
                    with redirect_stdout(output), self.assertRaises(CodexUnavailable) as caught:
                        HouseholdWorker(client, model).run_once()
                self.assertEqual(fail.call_count, 1)
                self.assertEqual(caught.exception.exception_type, "TypeError")
                self.assertEqual(caught.exception.diagnostic_stage, stage)
                self.assertNotIn("PRIVATE_SENTINEL", output.getvalue())
                self.assertNotIn("PRIVATE_SENTINEL", json.dumps(client.submissions))
                self.assertEqual(
                    json.loads(output.getvalue()),
                    {
                        "status": "TURN_DIAGNOSTIC",
                        "stage": stage,
                        "exception_type": "TypeError",
                    },
                )
                self.assertEqual(client.events.count("claim"), 1)
                if method != "submit_result":
                    self.assertEqual(len(client.submissions), 1)
                    self.assertEqual(client.submissions[0]["status"], "UNKNOWN_RESULT")

    def test_model_failure_and_failed_terminal_delivery_are_separate_diagnostics(self):
        output = io.StringIO()
        with (
            patch.object(self.model, "plan", side_effect=KeyError("PRIVATE_SENTINEL")) as plan,
            patch.object(
                self.client, "submit_result", side_effect=OSError("PRIVATE_SENTINEL")
            ) as submit,
            redirect_stdout(output),
            self.assertRaises(CodexUnavailable),
        ):
            self.worker.run_once()
        self.assertEqual(plan.call_count, 1)
        self.assertEqual(submit.call_count, 1)
        self.assertEqual(
            [json.loads(x) for x in output.getvalue().splitlines()],
            [
                {"status": "TURN_DIAGNOSTIC", "stage": "MODEL_PLAN", "exception_type": "KeyError"},
                {
                    "status": "TURN_DIAGNOSTIC",
                    "stage": "FAILURE_SUBMIT",
                    "exception_type": "OSError",
                },
            ],
        )
        self.assertNotIn("invoke", self.client.events)

    def test_final_exception_diagnostic_preserves_ambiguity_after_invoke(self):
        with (
            patch.object(self.model, "final", side_effect=ValueError("PRIVATE_SENTINEL")),
            redirect_stdout(io.StringIO()),
            self.assertRaises(CodexUnavailable) as caught,
        ):
            self.worker.run_once()
        self.assertEqual(caught.exception.diagnostic_stage, "MODEL_FINAL")
        self.assertEqual(caught.exception.exception_type, "ValueError")
        self.assertTrue(self.client.submissions[0]["provider_ambiguous"])
        self.assertEqual(self.client.events.count("invoke"), 1)

    def test_auth_unavailable_does_not_claim(self):
        self.model.auth = False
        with self.assertRaisesRegex(CodexUnavailable, "CODEX_AUTH_UNAVAILABLE"):
            self.worker.run_once()
        self.assertEqual(self.client.events, [])

    def test_provider_start_precedes_model_and_result_is_content_free(self):
        result = self.worker.run_once()
        self.assertEqual(result, {"status": "RECORDED"})
        self.assertLess(self.client.events.index("start"), self.client.events.index("model-plan"))
        self.assertEqual(self.client.submissions[0]["status"], "RESPONSE")

    def test_decision_journal_is_started_before_model_and_completed_before_submission(self):
        create = decision_tool("create_note")
        update = decision_tool("update_note")
        self.client.tools = lambda *args: {"tools": [TOOL, create, update]}
        calls = []

        def invoke(request, binding, tool, arguments, ordinal):
            calls.append((tool, arguments, ordinal))
            self.client.events.append(tool)
            if tool == "anima.knowledge.create_note":
                return {
                    "status": "SUCCEEDED",
                    "result": {
                        "note": {
                            "note_id": "00000000-0000-0000-0000-000000000099",
                            "digest": "a" * 64,
                        }
                    },
                }
            if tool == "anima.knowledge.update_note":
                return {"status": "SUCCEEDED", "result": {"note": {"digest": "b" * 64}}}
            return {"status": "SUCCEEDED"}

        self.client.invoke = invoke
        self.model.calls = []
        self.model.last_decision_record = {
            "summary": "The available request context did not require a household mutation.",
            "confidence": "HIGH",
            "information_gaps": ["No fresh device read was requested."],
        }
        self.worker.run_once()
        self.assertLess(
            self.client.events.index("anima.knowledge.create_note"),
            self.client.events.index("model-plan"),
        )
        self.assertLess(
            self.client.events.index("anima.knowledge.update_note"),
            self.client.events.index("submit"),
        )
        completed = calls[-1][1]
        self.assertEqual(completed["note_type"], "decision")
        self.assertEqual(completed["classifier"], "100.1")
        self.assertIn("Conclusion-level rationale", completed["body"])
        self.assertNotIn("synthetic response never logged", completed["body"])
        record = self.client.submissions[0]["metadata"]["decision_record"]
        self.assertEqual(record["journal_status"], "SUCCEEDED")
        self.assertEqual(record["confidence"], "HIGH")

    def test_restricted_tool_omits_provider_summary_and_result_from_decision_note(self):
        restricted = {**TOOL, "content_persistence": "EPHEMERAL_RESTRICTED"}
        self.client.tools = lambda *args: {
            "tools": [restricted, decision_tool("create_note"), decision_tool("update_note")]
        }
        calls = []

        def invoke(request, binding, tool, arguments, ordinal):
            calls.append((tool, arguments, ordinal))
            self.client.events.append(tool)
            if tool == "anima.knowledge.create_note":
                return {
                    "status": "SUCCEEDED",
                    "result": {
                        "note": {
                            "note_id": "00000000-0000-0000-0000-000000000098",
                            "digest": "c" * 64,
                        }
                    },
                }
            if tool == "anima.knowledge.update_note":
                return {"status": "SUCCEEDED", "result": {"note": {"digest": "d" * 64}}}
            return {"status": "SUCCEEDED", "result": {"private": "RESTRICTED_SENTINEL"}}

        self.client.invoke = invoke
        self.model.last_decision_record = {
            "summary": "RESTRICTED_SENTINEL influenced the response.",
            "confidence": "MEDIUM",
            "information_gaps": [],
        }
        self.worker.run_once()
        completed = next(arguments for tool, arguments, _ in calls if tool.endswith("update_note"))
        self.assertNotIn("RESTRICTED_SENTINEL", completed["body"])
        record = self.client.submissions[0]["metadata"]["decision_record"]
        self.assertTrue(record["restricted_content_omitted"])
        self.assertNotIn("RESTRICTED_SENTINEL", json.dumps(record))

    def test_failed_start_never_calls_model(self):
        self.client.start = "CLAIM_LOST"
        with self.assertRaises(CodexUnavailable):
            self.worker.run_once()
        self.assertNotIn("model-plan", self.client.events)
        self.assertNotIn("invoke", self.client.events)

    def test_entire_plan_validated_before_dispatch(self):
        for bad in (
            {"tool_id": "shell", "arguments": {}},
            {"tool_id": "household.read", "arguments": {"extra": "invalid"}},
        ):
            with self.subTest(bad=bad):
                self.client.events.clear()
                self.model.calls = [CALL, bad]
                with self.assertRaises(CodexUnavailable):
                    self.worker.run_once()
                self.assertNotIn("invoke", self.client.events)

    def test_confirmation_stops_remaining_calls_and_preserves_status(self):
        self.client.outcome = "REQUIRE_CONFIRMATION"
        self.model.calls = [CALL, CALL]
        self.worker.run_once()
        self.assertEqual(self.client.events.count("invoke"), 1)
        self.assertEqual(self.client.submissions[0]["status"], "WAITING_CONFIRMATION")

    def test_restricted_content_forces_final_without_later_calls(self):
        self.client.tools = lambda *args: {
            "tools": [{**TOOL, "content_persistence": "EPHEMERAL_RESTRICTED"}]
        }
        self.model.calls = [CALL, CALL]
        self.worker.run_once()
        self.assertEqual(self.client.events.count("invoke"), 1)
        self.assertEqual(self.client.events.count("model-plan"), 1)
        self.assertIn("model-final", self.client.events)

    def test_provider_failure_has_one_submission_and_no_retry(self):
        self.model.error = "CODEX_AUTH_UNAVAILABLE"
        with self.assertRaisesRegex(CodexUnavailable, "CODEX_AUTH_UNAVAILABLE"):
            self.worker.run_once()
        self.assertEqual(self.client.events.count("model-plan"), 1)
        self.assertEqual(len(self.client.submissions), 1)
        self.assertEqual(self.client.submissions[0]["status"], "UNAVAILABLE")

    def test_lease_loss_prevents_dispatch(self):
        self.client.lease = "CLAIM_LOST"
        with self.assertRaisesRegex(CodexUnavailable, "ANIMA_LEASE_LOST"):
            self.worker.run_once()
        self.assertNotIn("model-plan", self.client.events)
        self.assertNotIn("invoke", self.client.events)

    def test_ambiguous_result_delivery_is_not_resubmitted(self):
        def lost(*args, **kwargs):
            self.client.events.append("submit")
            raise AnimaHouseholdError("fixture lost reply")

        self.client.submit_result = lost
        with self.assertRaises(CodexUnavailable):
            self.worker.run_once()
        self.assertEqual(self.client.events.count("submit"), 1)

    def test_final_auth_failure_after_tool_activity_is_ambiguous(self):
        def unavailable(*args):
            raise CodexUnavailable("CODEX_AUTH_UNAVAILABLE")

        self.model.final = unavailable
        with self.assertRaises(CodexUnavailable):
            self.worker.run_once()
        self.assertIn("invoke", self.client.events)
        self.assertEqual(self.client.submissions[0]["status"], "UNKNOWN_RESULT")

    def test_renew_only_while_called_and_rate_limited(self):
        stop = threading.Event()
        lease = ActiveLease(self.client, {"request_id": "r", "binding": "b"}, stop)
        with patch("household_worker.time.monotonic", return_value=1):
            lease()
            lease()
        self.assertEqual(self.client.events, ["renew"])
        with patch("household_worker.time.monotonic", return_value=22):
            lease()
        self.assertEqual(self.client.events, ["renew", "renew"])
        stop.set()
        with self.assertRaisesRegex(CodexUnavailable, "WORKER_STOPPED"):
            lease()


class IterationTests(unittest.TestCase):
    def test_discovery_then_operation_uses_returned_canonical_id(self):
        client = ClientFixture()
        canonical_id = "00000000-0000-0000-0000-000000000042"
        discover = {
            **TOOL,
            "tool_id": "household.discover",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        }
        client.tools = lambda *args: {"tools": [discover, TOOL]}
        invocations = []

        def invoke(request, binding, tool_id, arguments, ordinal):
            invocations.append((tool_id, arguments, ordinal))
            if tool_id == "household.discover":
                return {"status": "SUCCEEDED", "result": {"canonical_id": canonical_id}}
            self.assertEqual(arguments, {"resource": canonical_id})
            return {"status": "SUCCEEDED", "result": {"state": "ONLINE"}}

        client.invoke = invoke

        def planner(context, tools, results, round_number, remaining):
            self.assertEqual(
                [t["tool_id"] for t in tools], ["household.discover", "household.read"]
            )
            if round_number == 1:
                self.assertEqual(results, [])
                return {"calls": [{"tool_id": "household.discover", "arguments": {}}]}
            if round_number == 2:
                self.assertEqual(results[0]["host_call"]["ordinal"], 1)
                return {
                    "calls": [
                        {
                            "tool_id": "household.read",
                            "arguments": {
                                "resource": results[0]["result"]["canonical_id"],
                            },
                        }
                    ]
                }
            self.assertEqual(results[-1]["result"]["state"], "ONLINE")
            return {"calls": []}

        model = IterativeModelFixture(client, planner)
        HouseholdWorker(client, model).run_once()
        self.assertEqual([x[2] for x in invocations], [1, 2])
        self.assertEqual(model.rounds, [(1, 8), (2, 7), (3, 6)])
        self.assertEqual(client.submissions[0]["status"], "RESPONSE")

    def test_cumulative_eight_calls_three_rounds_no_ordinal_reuse(self):
        client = ClientFixture()
        ordinals = []

        def invoke(request, binding, tool_id, arguments, ordinal):
            self.assertNotIn(ordinal, ordinals)
            ordinals.append(ordinal)
            return {"status": "SUCCEEDED"}

        client.invoke = invoke
        model = IterativeModelFixture(
            client,
            lambda context, tools, results, round_number, remaining: {
                "calls": [CALL] * min(3, remaining),
            },
        )
        HouseholdWorker(client, model).run_once()
        self.assertEqual(ordinals, list(range(1, 9)))
        self.assertEqual(model.rounds, [(1, 8), (2, 5), (3, 2)])
        self.assertEqual(
            model.final_context["host_iteration"]["stop_reason"], "CALL_BUDGET_EXHAUSTED"
        )
        self.assertEqual(client.submissions[0]["status"], "PARTIAL")

    def test_three_round_cap_independent_of_call_cap(self):
        client = ClientFixture()
        model = IterativeModelFixture(client, lambda *args: {"calls": [CALL]})
        HouseholdWorker(client, model).run_once()
        self.assertEqual(len(model.rounds), 3)
        self.assertEqual(client.events.count("invoke"), 3)
        self.assertEqual(
            model.final_context["host_iteration"]["stop_reason"], "ROUND_BUDGET_EXHAUSTED"
        )

    def test_over_budget_round_rejected_before_any_calls_in_round(self):
        client = ClientFixture()
        model = IterativeModelFixture(client, lambda *args: {"calls": [CALL] * 3})
        with self.assertRaisesRegex(CodexUnavailable, "INVALID_PLAN"):
            HouseholdWorker(client, model).run_once()
        self.assertEqual(client.events.count("invoke"), 6)

    def test_restricted_or_gated_result_allows_final_only(self):
        for outcome in (
            "RESTRICTED",
            "REQUIRE_CONFIRMATION",
            "REQUIRE_STRONGER_AUTH",
            "DENIED",
            "FAILED",
            "UNKNOWN_RESULT",
            "UNAVAILABLE",
        ):
            with self.subTest(outcome=outcome):
                client = ClientFixture()
                if outcome == "RESTRICTED":
                    client.tools = lambda *args: {
                        "tools": [{**TOOL, "content_persistence": "EPHEMERAL_RESTRICTED"}]
                    }
                else:
                    client.outcome = outcome
                model = IterativeModelFixture(client, lambda *args: {"calls": [CALL, CALL]})
                HouseholdWorker(client, model).run_once()
                self.assertEqual(len(model.rounds), 1)
                self.assertEqual(client.events.count("invoke"), 1)
                self.assertEqual(client.events.count("model-final"), 1)

    def test_model_cannot_mutate_frozen_catalogue_between_rounds(self):
        client = ClientFixture()

        def planner(context, tools, results, round_number, remaining):
            if round_number == 1:
                tools[0]["tool_id"] = "shell"
                return {"calls": [CALL]}
            self.assertEqual(tools[0]["tool_id"], "household.read")
            return {"calls": [{"tool_id": "shell", "arguments": {}}]}

        model = IterativeModelFixture(client, planner)
        with self.assertRaisesRegex(CodexUnavailable, "TOOL_NOT_IN_REQUEST_CATALOGUE"):
            HouseholdWorker(client, model).run_once()
        self.assertEqual(client.events.count("invoke"), 1)

    def test_turn_object_cannot_reuse_ordinals_on_second_run(self):
        client = ClientFixture()
        turn = SentryHouseholdTurn(
            client,
            ModelFixture(client),
            sentry_request_id="synthetic",
            source_surface="test",
        )
        turn.run()
        with self.assertRaisesRegex(CodexUnavailable, "ANIMA_TURN_ALREADY_RUN"):
            turn.run()
        self.assertEqual(client.events.count("claim"), 1)

    def test_planning_time_budget_leaves_final_and_stops_next_round(self):
        client = ClientFixture()
        clock = [0.0]

        def invoke(*args):
            clock[0] = 171.0
            client.events.append("invoke")
            return {"status": "SUCCEEDED"}

        client.invoke = invoke
        model = IterativeModelFixture(client, lambda *args: {"calls": [CALL]})
        with patch("sentry_turn.time.monotonic", side_effect=lambda: clock[0]):
            HouseholdWorker(client, model).run_once()
        self.assertEqual(len(model.rounds), 1)
        self.assertEqual(client.events.count("model-final"), 1)
        self.assertEqual(model.final_context["host_iteration"]["stop_reason"], "PLANNING_DEADLINE")

    def test_expired_deadline_launches_no_model_or_tool(self):
        client = ClientFixture()
        model = ModelFixture(client)
        turn = SentryHouseholdTurn(
            client,
            model,
            sentry_request_id="synthetic",
            source_surface="test",
            deadline=-1,
        )
        with self.assertRaisesRegex(CodexUnavailable, "ANIMA_TURN_DEADLINE"):
            turn.run()
        self.assertEqual(client.events, [])

    def test_planning_deadline_failure_goes_to_final_without_plan_retry(self):
        client = ClientFixture()
        clock = [0.0]

        def planner(*args):
            clock[0] = 171.0
            raise CodexUnavailable("CODEX_TIMEOUT")

        model = IterativeModelFixture(client, planner)
        with patch("sentry_turn.time.monotonic", side_effect=lambda: clock[0]):
            HouseholdWorker(client, model).run_once()
        self.assertEqual(len(model.rounds), 1)
        self.assertNotIn("invoke", client.events)
        self.assertEqual(client.events.count("model-final"), 1)
        self.assertEqual(client.submissions[0]["status"], "PARTIAL")


class CodexTests(unittest.TestCase):
    def test_http_and_unix_error_classification_is_bounded_and_content_free(self):
        cases = (
            (
                409,
                b'{"error":"TRUSTED_ACTION_SPEC_UNAVAILABLE"}',
                {"service_code": "TRUSTED_ACTION_SPEC_UNAVAILABLE"},
            ),
            (401, b'{"error":"interaction binding expired"}', {"service_code": "BINDING_EXPIRED"}),
            (400, b'{"error":"PRIVATE_SENTINEL"}', {"service_code": "UNCLASSIFIED"}),
            (409, b'{"error":{"private":"PRIVATE_SENTINEL"}}', {"service_code": "UNCLASSIFIED"}),
            (500, b"PRIVATE_SENTINEL", {"transport_code": "INVALID_JSON"}),
            (409, b"x" * (64 * 1024 + 1), {"transport_code": "RESPONSE_LIMIT"}),
            (200, b'{"error":"PRIVATE_SENTINEL"}', {"service_code": "UNCLASSIFIED"}),
        )
        for transport in ("http", "unix"):
            for status, raw, expected in cases:
                with self.subTest(transport=transport, status=status, expected=expected):
                    endpoint = "http://127.0.0.1:1" if transport == "http" else "/synthetic.sock"
                    with patch("anima_household_client._token", return_value="synthetic"):
                        client = AnimaHouseholdClient(endpoint, "/synthetic.token")
                    response = MagicMock(status=status)
                    response.read.return_value = raw
                    with (
                        patch("anima_household_client.build_opener") as opener,
                        patch("anima_household_client._UnixConnection") as unix,
                    ):
                        unix.return_value.getresponse.return_value = response
                        if status >= 400:
                            opener.return_value.open.side_effect = HTTPError(
                                "http://127.0.0.1:1",
                                status,
                                "PRIVATE_SENTINEL",
                                {},
                                io.BytesIO(raw),
                            )
                        else:
                            opener.return_value.open.return_value.__enter__.return_value = response
                        with self.assertRaises(AnimaHouseholdError) as caught:
                            client.call("/v1/requests/synthetic/invoke", {"ordinal": 1})
                        self.assertEqual(
                            caught.exception.safe_diagnostics(), {"http_status": status, **expected}
                        )
                        self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))
                        if transport == "http":
                            self.assertEqual(opener.return_value.open.call_count, 1)
                        else:
                            self.assertEqual(unix.return_value.request.call_count, 1)
                            response.read.assert_called_once_with(64 * 1024 + 1)

    def test_transport_disconnect_and_timeout_are_distinct_without_exception_text(self):
        for exc, code in (
            (http.client.RemoteDisconnected("PRIVATE_SENTINEL"), "REMOTE_DISCONNECTED"),
            (TimeoutError("PRIVATE_SENTINEL"), "TIMEOUT"),
            (ConnectionRefusedError("PRIVATE_SENTINEL"), "CONNECTION_REFUSED"),
        ):
            with self.subTest(code=code):
                with patch("anima_household_client._token", return_value="synthetic"):
                    client = AnimaHouseholdClient("/synthetic.sock", "/synthetic.token")
                with patch("anima_household_client._UnixConnection") as unix:
                    unix.return_value.getresponse.side_effect = exc
                    with self.assertRaises(AnimaHouseholdError) as caught:
                        client.call("/v1/requests/synthetic/invoke")
                self.assertEqual(caught.exception.safe_diagnostics(), {"transport_code": code})
                self.assertNotIn("PRIVATE_SENTINEL", str(caught.exception))

    def test_safe_http_diagnostic_reaches_terminal_detail_without_retry(self):
        client = ClientFixture()
        error = AnimaHouseholdError(
            "PRIVATE_SENTINEL",
            http_status=409,
            service_code="TRUSTED_ACTION_SPEC_UNAVAILABLE",
        )
        output = io.StringIO()
        with (
            patch.object(client, "invoke", side_effect=error) as invoke,
            redirect_stdout(output),
            self.assertRaises(CodexUnavailable),
        ):
            HouseholdWorker(client, ModelFixture(client)).run_once()
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "status": "TURN_DIAGNOSTIC",
                "stage": "TOOL_INVOKE",
                "exception_type": "AnimaHouseholdError",
                "http_status": 409,
                "service_code": "TRUSTED_ACTION_SPEC_UNAVAILABLE",
            },
        )
        self.assertEqual(len(client.submissions), 1)
        self.assertEqual(client.submissions[0]["status"], "UNKNOWN_RESULT")
        self.assertIn(
            "http_status=409;service_code=TRUSTED_ACTION_SPEC_UNAVAILABLE",
            client.submissions[0]["detail"],
        )
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(client.submissions))

    def test_diagnostic_never_formats_exception_or_exposes_custom_class_name(self):
        class PrivateMessage(Exception):
            def __str__(self):
                raise AssertionError("Exception text must not be read")

        PrivateMessage.__name__ = "PRIVATE_SENTINEL"
        error = diagnostic_error(PrivateMessage("PRIVATE_SENTINEL"), "PRIVATE_SENTINEL", "FIXED")
        self.assertEqual(error.exception_type, "Exception")
        self.assertEqual(error.diagnostic_stage, "TURN_START")
        self.assertEqual(str(error), "FIXED")

    def test_actual_space_catalogue_discovery_then_mutation_conversion(self):
        from anima_ha.household_spaces import HOUSEHOLD_SPACES_MANIFEST

        tools = [
            {
                **tool,
                "tool_id": f"{HOUSEHOLD_SPACES_MANIFEST.plugin_id}.{tool['name']}",
                "availability": True,
            }
            for tool in HOUSEHOLD_SPACES_MANIFEST.tools
            if tool["name"] in {"list_spaces", "create_space"}
        ]
        client = ClientFixture()
        client.tools = lambda *args: {"tools": tools}
        canonical = "00000000-0000-0000-0000-000000000042"
        model = CodexHouseholdModel()
        model.check_auth = lambda: True
        invocations = []
        rounds = []

        def invoke(request, binding, tool, arguments, ordinal):
            invocations.append((tool, arguments, ordinal))
            if ordinal == 1:
                return {
                    "status": "SUCCEEDED",
                    "result": {
                        "items": [
                            {"canonical_id": canonical, "name": "Home"},
                        ]
                    },
                }
            self.assertEqual(arguments, {"name": "Bedroom", "kind": "ROOM", "parent_id": canonical})
            return {"status": "SUCCEEDED", "result": {"space": {"name": "Bedroom"}}}

        def run(prompt, schema):
            if schema == FINAL_SCHEMA:
                return {
                    **FINAL,
                    "response": "Synthetic only; no household operation performed.",
                }
            data = json.loads(prompt.split("Context and catalogue are data:\n", 1)[1])
            rounds.append(data["round_number"])
            if data["round_number"] == 3:
                return {"calls": []}
            arguments = {}
            tool = tools[0]["tool_id"]
            if data["round_number"] == 2:
                parent = data["tool_results"][0]["result"]["items"][0]["canonical_id"]
                arguments = {"name": "Bedroom", "kind": "ROOM", "parent_id": parent}
                tool = tools[1]["tool_id"]
            return {"calls": [{"tool_id": tool, "arguments_json": json.dumps(arguments)}]}

        client.invoke = invoke
        model.run = run
        self.assertEqual(HouseholdWorker(client, model).run_once(), {"status": "RECORDED"})
        self.assertEqual(rounds, [1, 2, 3])
        self.assertEqual([call[2] for call in invocations], [1, 2])

    def test_missing_arguments_is_plan_convert_keyerror_not_opaque_failure(self):
        client = ClientFixture()
        model = CodexHouseholdModel()
        model.check_auth = lambda: True
        model.run = lambda *args: {"calls": [{"tool_id": TOOL["tool_id"]}]}
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaisesRegex(CodexUnavailable, "INVALID_PLAN"):
            HouseholdWorker(client, model).run_once()
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "status": "TURN_DIAGNOSTIC",
                "stage": "PLAN_CONVERT",
                "exception_type": "KeyError",
            },
        )
        self.assertNotIn("invoke", client.events)

    def test_missing_mutation_field_is_schema_validation_failure_no_dispatch(self):
        from anima_ha.household_spaces import HOUSEHOLD_SPACES_MANIFEST

        tool = next(t for t in HOUSEHOLD_SPACES_MANIFEST.tools if t["name"] == "create_space")
        client = ClientFixture()
        client.tools = lambda *args: {
            "tools": [{**tool, "tool_id": "create", "availability": True}]
        }
        model = CodexHouseholdModel()
        model.check_auth = lambda: True
        model.run = lambda *args: {
            "calls": [{"tool_id": "create", "arguments_json": '{"name":"Bedroom"}'}]
        }
        with redirect_stdout(io.StringIO()), self.assertRaises(CodexUnavailable) as caught:
            HouseholdWorker(client, model).run_once()
        self.assertEqual(str(caught.exception), "INVALID_TOOL_ARGUMENTS")
        self.assertEqual(caught.exception.diagnostic_stage, "PLAN_VALIDATE")
        self.assertEqual(caught.exception.exception_type, "ValidationError")
        self.assertNotIn("invoke", client.events)

    def test_active_cli_is_stopped_at_phase_deadline(self):
        model = CodexHouseholdModel(timeout=30)
        started = time.monotonic()
        model.set_deadline(started + 0.2)
        with tempfile.TemporaryFile(dir="/dev/shm") as schema_file:
            with self.assertRaisesRegex(CodexUnavailable, "CODEX_TIMEOUT"):
                model._capture(
                    [sys.executable, "-c", "import time; time.sleep(5)"],
                    b"synthetic",
                    schema_file.fileno(),
                )
        self.assertLess(time.monotonic() - started, 2)

    def test_cli_process_respects_absolute_deadline(self):
        model = CodexHouseholdModel(timeout=30)
        model.set_deadline(-1)
        with tempfile.TemporaryFile(dir="/dev/shm") as schema_file:
            with patch("codex_model.subprocess.Popen") as spawn:
                with self.assertRaisesRegex(CodexUnavailable, "ANIMA_TURN_DEADLINE"):
                    model._capture([sys.executable], b"synthetic", schema_file.fileno())
                spawn.assert_not_called()

    def test_iterative_cli_prompt_carries_prior_results_and_remaining_budget(self):
        model = CodexHouseholdModel()
        captured = []

        def run(prompt, schema):
            captured.append((prompt, schema))
            return {
                "calls": [
                    {"tool_id": "household.read", "arguments_json": '{"resource":"canonical-42"}'}
                ]
            }

        model.run = run
        result = model.plan_round(
            {},
            [TOOL],
            [{"result": {"canonical_id": "canonical-42"}}],
            round_number=2,
            remaining_calls=2,
        )
        self.assertIn('"canonical_id": "canonical-42"', captured[0][0])
        self.assertEqual(captured[0][1]["properties"]["calls"]["maxItems"], 2)
        self.assertEqual(result["calls"][0]["arguments"]["resource"], "canonical-42")

    def test_learning_review_compares_declared_context_without_minting_authority(self):
        model = CodexHouseholdModel()
        captured = []
        model.run = lambda prompt, schema: captured.append((prompt, schema)) or {"calls": []}
        context = {
            "household_context": {
                "initiative": {
                    "learning_review": {"candidates": [{"candidate_id": "candidate-1"}]},
                },
                "preferences": [{"scope": "household"}],
                "routines": [{"label": "declared routine"}],
            }
        }
        self.assertEqual(
            model.plan_round(context, [], [], round_number=1, remaining_calls=1), {"calls": []}
        )
        prompt = captured[0][0]
        self.assertIn("Compare candidates with the supplied owner preferences", prompt)
        self.assertIn("without changing either one", prompt)
        self.assertIn("Never infer an actor, identity, causation, authority", prompt)

    def test_environment_drops_core_and_provider_credentials(self):
        with patch.dict(
            os.environ,
            {
                "ANIMA_DATABASE_URL": "secret",
                "OPENAI_API_KEY": "secret",
                "ANIMA_SENTRY_CLIENT_TOKEN_FILE": "private",
                "HA_TOKEN": "secret",
            },
        ):
            env = child_environment()
        self.assertNotIn("ANIMA_DATABASE_URL", env)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("ANIMA_SENTRY_CLIENT_TOKEN_FILE", env)
        self.assertNotIn("HA_TOKEN", env)

    def test_disabled_catalogue_entry_cannot_be_called(self):
        with self.assertRaises(CodexUnavailable):
            validate_calls({"calls": [CALL]}, [{**TOOL, "availability": False}])
        self.assertEqual(plan_schema([])["properties"]["calls"]["maxItems"], 0)

    def test_remote_schema_refs_rejected_without_network(self):
        with self.assertRaisesRegex(CodexUnavailable, "NONLOCAL_TOOL_SCHEMA"):
            validate_calls(
                {"calls": [CALL]}, [{**TOOL, "input_schema": {"$ref": "https://invalid.test"}}]
            )

    def test_jsonl_requires_exact_final_and_completion(self):
        message = {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": json.dumps(FINAL)},
        }
        complete = {"type": "turn.completed"}

        def encode(events):
            return b"\n".join(json.dumps(event).encode() for event in events)

        self.assertEqual(
            CodexHouseholdModel.parse_events(encode([message, complete]), FINAL_SCHEMA),
            FINAL,
        )
        progress = {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "Preparing the structured result."},
        }
        self.assertEqual(
            CodexHouseholdModel.parse_events(encode([progress, message, complete]), FINAL_SCHEMA),
            FINAL,
        )
        for events in (
            [message],
            [message, progress, complete],
            [complete],
            [message, {"type": "turn.failed"}, complete],
            [{"type": "item.completed", "item": {"type": "command_execution"}}, message, complete],
        ):
            with self.subTest(events=events), self.assertRaises(CodexUnavailable):
                CodexHouseholdModel.parse_events(encode(events), FINAL_SCHEMA)

    def test_real_subprocess_timeout_and_output_limit(self):
        model = CodexHouseholdModel(timeout=1)
        with tempfile.TemporaryFile(dir="/dev/shm") as schema_file:
            fd = schema_file.fileno()
            with self.assertRaisesRegex(CodexUnavailable, "CODEX_TIMEOUT"):
                model._capture(
                    [sys.executable, "-c", "import time; time.sleep(5)"], b"synthetic", fd
                )
            with patch("codex_model.MAX_BYTES", 1024):
                with self.assertRaisesRegex(CodexUnavailable, "CODEX_OUTPUT_LIMIT"):
                    model._capture([sys.executable, "-c", "print('x'*4096)"], b"synthetic", fd)

    def test_active_process_is_cancelled_on_lease_loss(self):
        model = CodexHouseholdModel(timeout=5)
        ticks = 0

        def lost():
            nonlocal ticks
            ticks += 1
            if ticks > 2:
                raise CodexUnavailable("ANIMA_LEASE_LOST")

        model.heartbeat = lost
        with tempfile.TemporaryFile(dir="/dev/shm") as schema_file:
            fd = schema_file.fileno()
            with self.assertRaisesRegex(CodexUnavailable, "ANIMA_LEASE_LOST"):
                model._capture(
                    [sys.executable, "-c", "import time; time.sleep(5)"], b"synthetic", fd
                )

    def test_unsafe_endpoint_rejected_before_token_read(self):
        for endpoint in ("http://public.test", "http://localhost/?redirect=x", "relative.sock"):
            with self.subTest(endpoint=endpoint), self.assertRaises(AnimaHouseholdError):
                AnimaHouseholdClient(endpoint, "/not/read")

    def test_private_token_file_and_loopback_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-token"
            path.write_text("synthetic" * 8)
            path.chmod(0o600)
            client = AnimaHouseholdClient("http://127.0.0.1:1", str(path), timeout=0.1)
            with self.assertRaises(AnimaHouseholdError):
                client.call("/v1/health")

    def test_worker_consumes_http_fixture_then_idles_without_model(self):
        fixture = ClientFixture()
        token = "synthetic-service-token-" + "x" * 32

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                self.rfile.read(int(self.headers["Content-Length"]))
                if self.headers.get("Authorization") != f"Bearer {token}":
                    self.send_error(401)
                    return
                handlers = {
                    "/v1/interactions/open": fixture.open_interaction,
                    "/v1/requests/r/context": fixture.context,
                    "/v1/requests/r/tools": fixture.tools,
                    "/v1/requests/r/provider-start": fixture.provider_start,
                    "/v1/requests/renew": fixture.renew,
                    "/v1/requests/r/invoke": fixture.invoke,
                    "/v1/requests/r/result": fixture.submit_result,
                }
                response = json.dumps(handlers[self.path]()).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "test.token"
            token_file.write_text(token)
            token_file.chmod(0o600)
            with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    client = AnimaHouseholdClient(
                        f"http://127.0.0.1:{server.server_port}",
                        str(token_file),
                        timeout=1,
                    )
                    worker = HouseholdWorker(client, ModelFixture(fixture))
                    self.assertEqual(worker.run_once(), {"status": "RECORDED"})
                    fixture.empty = True
                    self.assertEqual(worker.run_once(), {"status": "IDLE"})
                    self.assertEqual(fixture.events.count("model-plan"), 1)
                    self.assertEqual(fixture.events.count("invoke"), 1)
                finally:
                    server.shutdown()
                    thread.join(timeout=2)

    def test_http_redirect_is_not_followed(self):
        paths = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):  # noqa: N802
                paths.append(self.path)
                self.send_response(302)
                self.send_header("Location", "/credential-leak-target")
                self.end_headers()

        with tempfile.TemporaryDirectory() as directory:
            token_file = Path(directory) / "test.token"
            token_file.write_text("synthetic" * 8)
            token_file.chmod(0o600)
            with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    client = AnimaHouseholdClient(
                        f"http://127.0.0.1:{server.server_port}",
                        str(token_file),
                        timeout=1,
                    )
                    with self.assertRaises(AnimaHouseholdError):
                        client.call("/v1/health")
                    self.assertEqual(paths, ["/v1/health"])
                finally:
                    server.shutdown()
                    thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
