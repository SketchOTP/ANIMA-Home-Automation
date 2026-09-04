"""Host-side SENTRY turn orchestration for the ANIMA household client.

This module is deliberately independent of ANIMA Core.  A SENTRY host supplies
the model callback; the callback sees only the sparse context and the exact
request-bound catalogue returned by ANIMA.  All household reads and writes
remain client calls to the authenticated ANIMA service.
"""

from __future__ import annotations

from typing import Any, Protocol

from anima_household_client import AnimaHouseholdClient, AnimaHouseholdError


class SentryTurnModel(Protocol):
    def plan(self, context: dict[str, Any], tools: list[dict[str, Any]]) -> dict[str, Any]: ...

    def final(
        self,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]],
    ) -> str: ...


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
    ) -> None:
        self.client = client
        self.model = model
        self.sentry_request_id = sentry_request_id
        self.source_surface = source_surface
        self.user_text = user_text
        self.identity_observation = identity_observation

    def run(self) -> dict[str, Any]:
        opened = (
            self.client.open_direct_interaction(
                self.sentry_request_id,
                self.source_surface,
                self.user_text if self.user_text is not None else "",
                self.identity_observation,
            )
            if self.user_text is not None
            else self.client.open_interaction(self.sentry_request_id, self.source_surface)
        )
        if opened.get("status") != "CLAIMED":
            return {"status": "UNAVAILABLE", "reason": "NO_ANIMA_REQUEST"}
        request_id = str(opened["request_id"])
        binding = str(opened["binding"])
        context = self.client.context(request_id, binding)
        catalogue = list(self.client.tools(request_id, binding).get("tools") or [])
        started = self.client.provider_start(request_id, binding)
        if started.get("status") != "PROVIDER_RUNNING":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "reason": "ANIMA_PROVIDER_START_REJECTED",
            }
        plan = self.model.plan(context, catalogue)
        calls = plan.get("calls") or []
        if not isinstance(calls, list) or len(calls) > 3:
            raise AnimaHouseholdError("SENTRY model plan exceeds bounded call count")
        tool_results: list[dict[str, Any]] = []
        for ordinal, call in enumerate(calls, start=1):
            if not isinstance(call, dict):
                raise AnimaHouseholdError("SENTRY model plan contains an invalid call")
            tool_results.append(
                self.client.invoke(
                    request_id,
                    binding,
                    str(call["tool_id"]),
                    dict(call.get("arguments") or {}),
                    ordinal,
                )
            )
        renewed = self.client.renew(request_id, binding)
        if renewed.get("status") != "RENEWED":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "tool_results": tool_results,
                "reason": "ANIMA_BINDING_RENEWAL_FAILED",
            }
        response = self.model.final(context, tool_results)
        renewed = self.client.renew(request_id, binding)
        if renewed.get("status") != "RENEWED":
            return {
                "status": "UNKNOWN_RESULT",
                "request_id": request_id,
                "sentry_request_id": self.sentry_request_id,
                "tool_results": tool_results,
                "reason": "ANIMA_BINDING_RENEWAL_FAILED",
            }
        submitted = self.client.submit_result(
            request_id,
            binding,
            status="RESPONSE",
            response=response,
        )
        return {
            "status": submitted.get("status", "UNKNOWN_RESULT"),
            "request_id": request_id,
            "sentry_request_id": self.sentry_request_id,
            "tool_results": tool_results,
            "response": response,
        }
