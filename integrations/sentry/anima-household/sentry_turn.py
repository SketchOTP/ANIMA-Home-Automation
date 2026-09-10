"""Host-side SENTRY turn orchestration for the ANIMA household client.

This module is deliberately independent of ANIMA Core.  A SENTRY host supplies
the model callback; the callback sees only the sparse context and the exact
request-bound catalogue returned by ANIMA.  All household reads and writes
remain client calls to the authenticated ANIMA service.
"""

from __future__ import annotations

import re
import time
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol

from anima_household_client import AnimaHouseholdClient, AnimaHouseholdError
from codex_model import CodexUnavailable, validate_calls

MAX_CALLS = 8
MAX_ROUNDS = 3
TURN_SECONDS = 270
FINAL_RESERVE_SECONDS = 100
DECISION_NOTE_CREATE_ORDINAL = 10_001
DECISION_NOTE_UPDATE_ORDINAL = 10_002
DECISION_NOTE_TYPE = "decision"
DECISION_CLASSIFIER = "100.1"
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$")


class SentryTurnModel(Protocol):
    def plan(self, context: dict[str, Any], tools: list[dict[str, Any]]) -> dict[str, Any]: ...

    def final(
        self,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> str: ...


class IterativeSentryTurnModel(SentryTurnModel, Protocol):
    """Optional explicit capability; legacy plan/final callbacks stay single-pass."""

    def plan_round(
        self,
        context: dict[str, Any],
        tools: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        *,
        round_number: int,
        remaining_calls: int,
    ) -> dict[str, Any]: ...


class SentryHouseholdTurn:
    """Run one bounded model turn against ANIMA's typed household surface."""

    def __init__(
        self,
        client: AnimaHouseholdClient,
        model: SentryTurnModel,
        *,
        sentry_request_id: str,
        source_surface: str,
        user_text: str | None = None,
        identity_observation: dict[str, Any] | None = None,
        deadline: float | None = None,
    ) -> None:
        self.client = client
        self.model = model
        self.sentry_request_id = sentry_request_id
        self.source_surface = source_surface
        self.user_text = user_text
        self.identity_observation = identity_observation
        self.tool_invocation_started = False
        self.result_submission_started = False
        self.deadline = deadline
        self._has_run = False
        self.diagnostic_stage = "TURN_START"
        self._decision_note: dict[str, str] | None = None
        self._decision_request_id: str | None = None
        self._decision_binding: str | None = None
        self._decision_origin = "UNKNOWN"
        self._decision_journal_status = "NOT_STARTED"
        self._decision_context_categories: list[str] = []
        self._decision_tool_results: list[dict[str, Any]] = []
        self._decision_started_at: datetime | None = None
        self._decision_catalogue: list[dict[str, Any]] = []
        self._decision_override: dict[str, Any] | None = None
        self._decision_sources: list[dict[str, str]] = []
        self._decision_notification = "not_available"

    @staticmethod
    def _supports_decision_note(catalogue: list[dict[str, Any]], tool_id: str) -> bool:
        descriptor = next(
            (
                item
                for item in catalogue
                if item.get("tool_id") == tool_id and item.get("availability") is True
            ),
            None,
        )
        if descriptor is None:
            return False
        schema = descriptor.get("input_schema")
        note_type = (
            schema.get("properties", {}).get("note_type", {}) if isinstance(schema, dict) else {}
        )
        return (
            DECISION_NOTE_TYPE in note_type.get("enum", [])
            if isinstance(note_type, dict)
            else False
        )

    @staticmethod
    def _context_categories(context: dict[str, Any]) -> list[str]:
        categories = ["sparse_request_context"]
        if isinstance(context.get("identity_context"), dict):
            categories.append("identity_evidence")
        household = context.get("household_context")
        if isinstance(household, dict):
            if isinstance(household.get("preferences"), dict):
                categories.append("household_and_person_preferences")
            if isinstance(household.get("routines"), dict):
                categories.append("declared_routines")
            if isinstance(household.get("memory"), dict):
                categories.append("memory_lookup_available")
            if isinstance(household.get("presence"), dict):
                categories.append("fresh_presence_lookup_available")
            if isinstance(household.get("initiative"), dict):
                categories.append("notification_disposition")
        if any(key in context for key in ("truth", "truth_snapshot", "observations")):
            categories.append("bounded_truth_evidence")
        return categories

    @staticmethod
    def _notification_summary(context: dict[str, Any]) -> str:
        household = context.get("household_context")
        initiative = household.get("initiative") if isinstance(household, dict) else None
        notification = initiative.get("notification") if isinstance(initiative, dict) else None
        if not isinstance(notification, dict):
            return "not_available"
        allowed = "yes" if notification.get("allowed") is True else "no"
        required = "yes" if notification.get("required") is True else "no"
        reason = SentryHouseholdTurn._source_id(notification.get("reason"), "UNSPECIFIED")
        return f"allowed={allowed}; required={required}; reason={reason}"

    @staticmethod
    def _source_id(value: Any, fallback: str) -> str:
        candidate = str(value or "")
        return candidate if _SAFE_TOKEN.fullmatch(candidate) else fallback

    @staticmethod
    def _tool_activity(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        activity: list[dict[str, Any]] = []
        for item in tool_results[:MAX_CALLS]:
            host_call = item.get("host_call")
            if not isinstance(host_call, dict):
                continue
            tool_id = SentryHouseholdTurn._source_id(
                host_call.get("tool_id"), "unidentified.request_bound_tool"
            )
            status = SentryHouseholdTurn._source_id(item.get("status"), "UNKNOWN_RESULT")
            reason = item.get("reason")
            activity.append(
                {
                    "ordinal": int(host_call.get("ordinal", len(activity) + 1)),
                    "tool_id": tool_id,
                    "status": status,
                    "reason": (
                        SentryHouseholdTurn._source_id(reason, "REDACTED_DETAIL")
                        if reason is not None
                        else None
                    ),
                }
            )
        return activity

    def _decision_payload(
        self,
        *,
        title: str,
        body: str,
        confidence: float,
        source_refs: list[dict[str, str]],
    ) -> dict[str, Any]:
        encoded = body.encode("utf-8")
        if len(encoded) > 4096:
            body = encoded[:4080].decode("utf-8", errors="ignore").rstrip() + "\n[TRUNCATED]"
        return {
            "title": title[:120],
            "body": body,
            "note_type": DECISION_NOTE_TYPE,
            "classifier": DECISION_CLASSIFIER,
            "classification": "SENTRY_INFERENCE",
            "confidence": max(0.0, min(1.0, confidence)),
            "source_refs": source_refs[:12],
            "enabled": True,
            "retention_days": None,
            "person_refs": [],
        }

    def _start_decision_journal(
        self,
        request_id: str,
        binding: str,
        context: dict[str, Any],
        catalogue: list[dict[str, Any]],
        origin: str,
        trigger_id: str | None,
    ) -> str:
        self._decision_request_id = request_id
        self._decision_binding = binding
        self._decision_origin = self._source_id(origin, "UNKNOWN")
        self._decision_context_categories = self._context_categories(context)
        self._decision_notification = self._notification_summary(context)
        self._decision_catalogue = catalogue
        self._decision_started_at = datetime.now(UTC)
        if not all(
            self._supports_decision_note(catalogue, tool_id)
            for tool_id in ("anima.knowledge.create_note", "anima.knowledge.update_note")
        ):
            return "NOT_AVAILABLE_IN_REQUEST_CATALOGUE"
        source_id = self._source_id(request_id, "sentry-request")
        self._decision_sources = [
            {
                "kind": "request",
                "source_id": source_id,
                "meaning": "ANIMA intelligence request whose provider turn is being summarized.",
            }
        ]
        if trigger_id:
            self._decision_sources.append(
                {
                    "kind": "event",
                    "source_id": self._source_id(trigger_id, "sentry-trigger-event"),
                    "meaning": "Canonical trigger associated with this intelligence request.",
                }
            )
        categories = ", ".join(self._decision_context_categories)
        body = (
            "SENTRY decision journal\n\n"
            "State: PROVIDER_RUNNING\n"
            f"Request: {source_id}\n"
            f"Origin: {self._source_id(origin, 'UNKNOWN')}\n"
            f"Context categories made available: {categories}\n\n"
            f"Pre-model notification disposition: {self._decision_notification}\n\n"
            "ANIMA durably marked provider execution before this note. No model conclusion "
            "has been recorded yet. This journal stores an auditable conclusion summary, not "
            "private chain-of-thought, raw prompts, transcripts, secrets, or household payloads."
        )
        try:
            outcome = self.client.invoke(
                request_id,
                binding,
                "anima.knowledge.create_note",
                self._decision_payload(
                    title=f"SENTRY decision in progress · {source_id[:24]}",
                    body=body,
                    confidence=0.0,
                    source_refs=self._decision_sources,
                ),
                DECISION_NOTE_CREATE_ORDINAL,
            )
        except Exception:
            return "WRITE_UNAVAILABLE"
        receipt = outcome.get("result", {}).get("note") if isinstance(outcome, dict) else None
        if (
            outcome.get("status") == "SUCCEEDED"
            and isinstance(receipt, dict)
            and _SAFE_TOKEN.fullmatch(str(receipt.get("note_id", "")))
            and re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("digest", "")))
        ):
            self._decision_note = {
                "note_id": str(receipt["note_id"]),
                "digest": str(receipt["digest"]),
            }
            return "IN_PROGRESS"
        return self._source_id(outcome.get("status"), "WRITE_UNAVAILABLE")

    def _restricted_content_seen(self) -> bool:
        descriptors = {str(item.get("tool_id")): item for item in self._decision_catalogue}
        for activity in self._tool_activity(self._decision_tool_results):
            descriptor = descriptors.get(activity["tool_id"], {})
            if descriptor.get("content_persistence") == "EPHEMERAL_RESTRICTED":
                return True
        return False

    def _model_decision(self) -> tuple[str, str, list[str]]:
        value = self._decision_override or getattr(self.model, "last_decision_record", None)
        if not isinstance(value, dict):
            return (
                "The provider completed the turn but did not supply a separate conclusion summary.",
                "LOW",
                ["A provider-authored conclusion summary was unavailable."],
            )
        summary = value.get("summary")
        confidence = value.get("confidence")
        gaps = value.get("information_gaps")
        if (
            not isinstance(summary, str)
            or not summary.strip()
            or len(summary) > 1200
            or confidence not in {"LOW", "MEDIUM", "HIGH"}
            or not isinstance(gaps, list)
            or len(gaps) > 6
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 200 for item in gaps
            )
        ):
            return (
                "The provider conclusion summary did not satisfy the bounded audit contract.",
                "LOW",
                ["A schema-valid provider summary was unavailable."],
            )
        return summary.strip(), str(confidence), [item.strip() for item in gaps]

    def _complete_decision_journal(self, proposed_status: str) -> dict[str, Any]:
        completed_at = datetime.now(UTC)
        started_at = self._decision_started_at or completed_at
        summary, confidence, gaps = self._model_decision()
        restricted = self._restricted_content_seen()
        if restricted:
            summary = (
                "Restricted external content contributed to this turn. Its conclusion details "
                "were intentionally omitted from durable memory."
            )
            gaps = ["Restricted-content details remain live-only and are not reproduced here."]
        activity = self._tool_activity(self._decision_tool_results)
        record: dict[str, Any] = {
            "version": 1,
            "provider": "sentry",
            "request_id": self._decision_request_id,
            "origin": self._decision_origin,
            "provider_started_at": started_at.isoformat(),
            "decision_completed_at": completed_at.isoformat(),
            "elapsed_ms": max(0, int((completed_at - started_at).total_seconds() * 1000)),
            "proposed_result_status": self._source_id(proposed_status, "UNKNOWN_RESULT"),
            "decision_summary": summary,
            "confidence": confidence,
            "information_gaps": gaps,
            "context_categories": list(self._decision_context_categories),
            "pre_model_notification_disposition": self._decision_notification,
            "provider_reported_tool_activity": activity,
            "restricted_content_omitted": restricted,
            "journal_status": self._decision_journal_status,
        }
        if (
            self._decision_note is None
            or self._decision_request_id is None
            or self._decision_binding is None
        ):
            return record
        sources = list(self._decision_sources)
        for item in activity:
            sources.append(
                {
                    "kind": "tool_result",
                    "source_id": self._source_id(
                        f"{self._decision_request_id}:tool:{item['ordinal']}",
                        f"sentry-tool-{item['ordinal']}",
                    ),
                    "meaning": (
                        f"Request-bound {item['tool_id']} returned governed status "
                        f"{item['status']}."
                    )[:240],
                }
            )
        tool_lines = (
            "\n".join(
                f"- {item['ordinal']}. {item['tool_id']} -> {item['status']}"
                + (f" ({item['reason']})" if item["reason"] else "")
                for item in activity
            )
            or "- No semantic ANIMA tool was invoked."
        )
        gap_lines = "\n".join(f"- {gap}" for gap in gaps) or "- None reported."
        body = (
            "SENTRY decision journal\n\n"
            "State: RESULT_PREPARED\n"
            f"Request: {self._source_id(self._decision_request_id, 'sentry-request')}\n"
            f"Origin: {self._decision_origin}\n"
            f"Proposed Core result: {record['proposed_result_status']}\n"
            f"Provider elapsed: {record['elapsed_ms']} ms\n"
            f"Context categories made available: {', '.join(self._decision_context_categories)}\n"
            f"Pre-model notification disposition: {self._decision_notification}\n"
            f"Restricted content omitted: {'yes' if restricted else 'no'}\n\n"
            "Conclusion-level rationale\n"
            f"{summary}\n\n"
            f"Confidence: {confidence}\n\n"
            "Information gaps\n"
            f"{gap_lines}\n\n"
            "Governed tool activity\n"
            f"{tool_lines}\n\n"
            "This is a bounded audit summary, not private chain-of-thought. It excludes raw "
            "prompts, transcripts, response text, tool arguments/results, secrets and "
            "household payloads."
        )
        try:
            outcome = self.client.invoke(
                self._decision_request_id,
                self._decision_binding,
                "anima.knowledge.update_note",
                {
                    **self._decision_payload(
                        title=(
                            "SENTRY decision · "
                            f"{record['proposed_result_status']} · {self._decision_request_id[:18]}"
                        ),
                        body=body,
                        confidence={"LOW": 0.35, "MEDIUM": 0.65, "HIGH": 0.9}.get(confidence, 0.35),
                        source_refs=sources,
                    ),
                    "note_id": self._decision_note["note_id"],
                    "expected_digest": self._decision_note["digest"],
                },
                DECISION_NOTE_UPDATE_ORDINAL,
            )
            self._decision_journal_status = self._source_id(
                outcome.get("status") if isinstance(outcome, dict) else None,
                "WRITE_UNAVAILABLE",
            )
        except Exception:
            self._decision_journal_status = "WRITE_UNAVAILABLE"
        record["journal_status"] = self._decision_journal_status
        if self._decision_note is not None:
            record["journal_note_id"] = self._decision_note["note_id"]
        return record

    def finalize_failure_journal(self, failure_code: str) -> None:
        """Best-effort close of a started note; never changes the turn result."""
        if self._decision_started_at is None:
            return
        self._decision_override = {
            "summary": "The provider turn ended before a confirmed conclusion was available.",
            "confidence": "LOW",
            "information_gaps": [self._source_id(failure_code, "PROVIDER_FAILURE")],
        }
        self._complete_decision_journal("UNKNOWN_RESULT")

    def run(self, opened: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._has_run:
            raise CodexUnavailable("ANIMA_TURN_ALREADY_RUN")
        self._has_run = True
        deadline = self.deadline if self.deadline is not None else time.monotonic() + TURN_SECONDS
        planning_deadline = deadline - FINAL_RESERVE_SECONDS

        def check_time() -> None:
            if time.monotonic() >= deadline:
                raise CodexUnavailable("ANIMA_TURN_DEADLINE")

        def model_deadline(value: float) -> None:
            setter = getattr(self.model, "set_deadline", None)
            if callable(setter):
                setter(value)

        check_time()
        opened = (
            opened
            if opened is not None
            else (
                self.client.open_direct_interaction(
                    self.sentry_request_id,
                    self.source_surface,
                    self.user_text if self.user_text is not None else "",
                    self.identity_observation,
                )
                if self.user_text is not None
                else self.client.open_interaction(self.sentry_request_id, self.source_surface)
            )
        )
        if opened.get("status") != "CLAIMED":
            return {"status": "UNAVAILABLE", "reason": "NO_ANIMA_REQUEST"}
        request_id = str(opened["request_id"])
        binding = str(opened["binding"])
        self.diagnostic_stage = "CONTEXT"
        context = deepcopy(self.client.context(request_id, binding))
        self.diagnostic_stage = "CATALOGUE"
        catalogue = deepcopy(list(self.client.tools(request_id, binding).get("tools") or []))
        check_time()
        self.diagnostic_stage = "PROVIDER_START"
        started = self.client.provider_start(request_id, binding)
        if started.get("status") != "PROVIDER_RUNNING":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "reason": "ANIMA_PROVIDER_START_REJECTED",
            }
        tool_results: list[dict[str, Any]] = []
        self._decision_tool_results = tool_results
        self._decision_journal_status = self._start_decision_journal(
            request_id,
            binding,
            context,
            catalogue,
            str(opened.get("origin") or context.get("origin") or "UNKNOWN"),
            str(opened["trigger_id"]) if opened.get("trigger_id") else None,
        )
        iterative = getattr(self.model, "plan_round", None)
        round_limit = MAX_ROUNDS if callable(iterative) else 1
        stop_reason = "PLAN_COMPLETE"
        rounds = 0
        for round_number in range(1, round_limit + 1):
            if time.monotonic() >= planning_deadline:
                stop_reason = "PLANNING_DEADLINE"
                break
            model_deadline(planning_deadline)
            rounds = round_number
            remaining = MAX_CALLS - len(tool_results)
            self.diagnostic_stage = "MODEL_PLAN"
            try:
                plan = (
                    iterative(
                        deepcopy(context),
                        deepcopy(catalogue),
                        deepcopy(tool_results),
                        round_number=round_number,
                        remaining_calls=remaining,
                    )
                    if callable(iterative)
                    else self.model.plan(deepcopy(context), deepcopy(catalogue))
                )
            except CodexUnavailable as exc:
                if str(exc) in {"CODEX_TIMEOUT", "ANIMA_TURN_DEADLINE"} and (
                    time.monotonic() >= planning_deadline
                ):
                    # The tool-free planning process has already been killed.
                    # Use the reserved final slot, never retry this plan.
                    stop_reason = "PLANNING_DEADLINE"
                    break
                raise
            # Validate every call against the frozen catalogue before dispatch;
            # a later invalid call must not allow earlier side effects.
            self.diagnostic_stage = "PLAN_VALIDATE"
            calls = validate_calls(plan, catalogue, max_calls=min(3, remaining))
            if not calls:
                break
            for call in calls:
                if time.monotonic() >= planning_deadline:
                    stop_reason = "PLANNING_DEADLINE"
                    break
                self.diagnostic_stage = "TOOL_RENEW"
                if self.client.renew(request_id, binding).get("status") != "RENEWED":
                    raise AnimaHouseholdError("ANIMA_BINDING_RENEWAL_FAILED")
                if time.monotonic() >= planning_deadline:
                    stop_reason = "PLANNING_DEADLINE"
                    break
                ordinal = len(tool_results) + 1
                self.tool_invocation_started = True
                self.diagnostic_stage = "TOOL_INVOKE"
                outcome = self.client.invoke(
                    request_id,
                    binding,
                    call["tool_id"],
                    deepcopy(call["arguments"]),
                    ordinal,
                )
                self.diagnostic_stage = "TOOL_OUTCOME"
                tool_results.append(
                    {
                        **outcome,
                        "host_call": {"ordinal": ordinal, **deepcopy(call)},
                    }
                )
                if outcome.get("status") != "SUCCEEDED":
                    stop_reason = "TOOL_GATE_OR_FAILURE"
                    break
                descriptor = next(
                    tool for tool in catalogue if tool.get("tool_id") == call["tool_id"]
                )
                if descriptor.get("content_persistence") == "EPHEMERAL_RESTRICTED":
                    stop_reason = "RESTRICTED_CONTENT_FINAL_ONLY"
                    break
            if stop_reason != "PLAN_COMPLETE":
                break
            if len(tool_results) >= MAX_CALLS:
                stop_reason = "CALL_BUDGET_EXHAUSTED"
                break
            if callable(iterative) and round_number == MAX_ROUNDS:
                stop_reason = "ROUND_BUDGET_EXHAUSTED"
        check_time()
        self.diagnostic_stage = "FINAL_RENEW"
        renewed = self.client.renew(request_id, binding)
        if renewed.get("status") != "RENEWED":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "tool_results": tool_results,
                "reason": "ANIMA_BINDING_RENEWAL_FAILED",
            }
        model_deadline(deadline - 15)
        final_context = deepcopy(context)
        if callable(iterative):
            final_context["host_iteration"] = {
                "rounds": rounds,
                "calls": len(tool_results),
                "stop_reason": stop_reason,
            }
        self.diagnostic_stage = "MODEL_FINAL"
        response = self.model.final(final_context, deepcopy(tool_results))
        check_time()
        self.diagnostic_stage = "RESULT_RENEW"
        renewed = self.client.renew(request_id, binding)
        if renewed.get("status") != "RENEWED":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "tool_results": tool_results,
                "reason": "ANIMA_BINDING_RENEWAL_FAILED",
            }
        self.diagnostic_stage = "RESULT_PREPARE"
        statuses = {item.get("status") for item in tool_results}
        status = (
            "PARTIAL"
            if stop_reason
            in {
                "CALL_BUDGET_EXHAUSTED",
                "ROUND_BUDGET_EXHAUSTED",
                "PLANNING_DEADLINE",
            }
            else "RESPONSE"
        )
        for source, terminal in (
            ("UNKNOWN_RESULT", "UNKNOWN_RESULT"),
            ("REQUIRE_STRONGER_AUTH", "WAITING_STRONGER_AUTH"),
            ("REQUIRE_CONFIRMATION", "WAITING_CONFIRMATION"),
            ("UNAVAILABLE", "UNAVAILABLE"),
            ("DENIED", "FAILED"),
            ("POLICY_DENIED", "FAILED"),
            ("FAILED", "FAILED"),
            ("VERIFICATION_FAILED", "PARTIAL"),
        ):
            if source in statuses:
                status = terminal
                break
        if statuses - {"SUCCEEDED"} and status == "RESPONSE":
            status = "PARTIAL"
        decision_record = self._complete_decision_journal(status)
        self.result_submission_started = True
        check_time()
        self.diagnostic_stage = "RESULT_SUBMIT"
        submitted = self.client.submit_result(
            request_id,
            binding,
            status=status,
            response=response,
            metadata={"decision_record": decision_record},
            provider_ambiguous=status == "UNKNOWN_RESULT",
        )
        return {
            "status": submitted.get("status", "UNKNOWN_RESULT"),
            "request_id": request_id,
            "sentry_request_id": self.sentry_request_id,
            "tool_results": tool_results,
            "response": response,
        }
