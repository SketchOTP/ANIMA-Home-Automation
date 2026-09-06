"""Host-side SENTRY turn orchestration for the ANIMA household client.

This module is deliberately independent of ANIMA Core.  A SENTRY host supplies
the model callback; the callback sees only the sparse context and the exact
request-bound catalogue returned by ANIMA.  All household reads and writes
remain client calls to the authenticated ANIMA service.
"""

from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Protocol

from anima_household_client import AnimaHouseholdClient, AnimaHouseholdError
from codex_model import CodexUnavailable, validate_calls

MAX_CALLS = 8
MAX_ROUNDS = 3
TURN_SECONDS = 270
FINAL_RESERVE_SECONDS = 100


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
        self.result_submission_started = True
        check_time()
        self.diagnostic_stage = "RESULT_SUBMIT"
        submitted = self.client.submit_result(
            request_id,
            binding,
            status=status,
            response=response,
            provider_ambiguous=status == "UNKNOWN_RESULT",
        )
        return {
            "status": submitted.get("status", "UNKNOWN_RESULT"),
            "request_id": request_id,
            "sentry_request_id": self.sentry_request_id,
            "tool_results": tool_results,
            "response": response,
        }
