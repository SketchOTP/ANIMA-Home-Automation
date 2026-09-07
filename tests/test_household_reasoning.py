from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from test_knowledge_api import fields, setup

from anima_ha.household_reasoning import REASONING_GUIDANCE, household_reasoning_context
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
)
from anima_ha.policy import PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_api import DEFAULT_HOUSEHOLD_ID


def request_for(manager: Any) -> Any:
    request = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=DEFAULT_HOUSEHOLD_ID,
        source_surface="voice",
        user_text="Remember a useful lesson",
        tools=manager.list_tools(),
        service_client_id="synthetic-household-client",
    )
    return replace(
        request,
        lifecycle=IntelligenceLifecycle.PROVIDER_RUNNING,
        claim_owner="synthetic",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        fencing_generation=1,
    )


@pytest.mark.parametrize("enabled,denied", [(False, False), (True, False), (True, True)])
def test_agent_memory_grant_is_exact_and_still_policy_gated(
    tmp_path: Path, enabled: bool, denied: bool
) -> None:
    _, _, manager, evaluator = setup(tmp_path, deny=denied)
    request = request_for(manager)
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request)),
        agent_memory_enabled=enabled,
    )
    result = boundary.invoke_tool(request, "anima.knowledge.create_note", fields())
    descriptor = next(
        item
        for item in boundary.catalogue(request)
        if item["tool_id"] == "anima.knowledge.create_note"
    )
    assert descriptor["availability"] is enabled
    if enabled and not denied:
        assert result["status"] == "SUCCEEDED"
        assert evaluator.documents[-1]["origin"] == "AUTONOMOUS_AGENT"
        assert evaluator.documents[-1]["identity"]["principal_id"] is None
        assert evaluator.documents[-1]["identity"]["assurance"] != "AUTHENTICATED"
        assert len(list((tmp_path / "ANIMA").rglob("*.md"))) == 1
    else:
        assert result["status"] == "DENIED"
        assert not list((tmp_path / "ANIMA").rglob("*.md"))


def test_live_context_is_non_authoritative_and_does_not_change_stored_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = request_for(manager)
    original = dict(request.request_metadata["direct_context"])
    calls: list[dict[str, Any]] = []

    def preferences(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"items": [{"content": "Shared preference sentinel"}], "next_cursor": None}

    monkeypatch.setattr("anima_ha.household_reasoning.preferences_page", preferences)
    monkeypatch.setattr(
        "anima_ha.household_reasoning.family_routines_page",
        lambda *args, **kwargs: {"items": [], "next_cursor": None},
    )
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(evaluator),
        cast(Any, SimpleNamespace(get=lambda _: request)),
        reasoning_context_loader=lambda item: household_reasoning_context(item, object(), object()),
    )
    context = boundary.request_context(request)
    assert context["household_context"]["authority"] == "NONE"
    assert context["household_context"]["guidance"] == REASONING_GUIDANCE
    assert calls == [{"graph": calls[0]["graph"], "scope": "household", "limit": 10}]
    assert request.request_metadata["direct_context"] == original
    assert "household_context" not in original


def test_missing_context_stays_unavailable_not_empty_certainty(tmp_path: Path) -> None:
    _, _, manager, _ = setup(tmp_path)
    request = request_for(manager)
    result = household_reasoning_context(request, None, None)
    assert result["preferences"]["status"] == "UNAVAILABLE"
    assert result["routines"]["status"] == "UNAVAILABLE"
    assert request.origin == IntelligenceOrigin.DIRECT_SENTRY_INTERACTION


def test_failed_personal_lookup_keeps_shared_preferences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, manager, _ = setup(tmp_path)
    request = replace(request_for(manager), principal_id=uuid4())

    def preferences(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs.get("person_id"):
            raise ValueError("person no longer active")
        return {"items": [{"content": "Shared preference remains available"}], "next_cursor": None}

    monkeypatch.setattr("anima_ha.household_reasoning.preferences_page", preferences)
    result = household_reasoning_context(request, None, None)["preferences"]
    assert result["status"] == "PARTIAL"
    assert result["household"]["items"][0]["content"] == "Shared preference remains available"
    assert result["request_person"]["status"] == "UNAVAILABLE"
