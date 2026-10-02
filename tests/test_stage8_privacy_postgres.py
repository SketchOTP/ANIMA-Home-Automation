"""Current commissioned session retirement with real PG/OPA, no owner data."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import psycopg
import pytest
from test_stage2_delivery_postgres import isolated_url as isolated_url
from test_stage3_household_situation import situation as situation
from test_stage6_owner_postgres import connected as connected
from test_stage6_owner_postgres import frozen_request
from test_stage8_task_result_postgres import due_task

from anima_ha.intelligence import IntelligenceResult, IntelligenceResultStatus
from anima_ha.ui_api import PrincipalMappingRequired


@pytest.fixture(autouse=True)
def explicit_sentry_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")


@pytest.mark.parametrize("kind", ["approval", "ordinary"])
def test_retired_person_only_revokes_existing_session_result_scope(
    connected: dict[str, Any], kind: str
) -> None:
    value, core = connected, connected["service"].core_runtime
    # The shared synthetic test-login fixture uses a static mapping. Bind the
    # actual commissioned production resolver before these session route checks.
    value["service"].identity_resolver = core.identity_resolver
    if kind == "approval":
        plugin = core.plugins.plugins["anima.provider.home-assistant"]
        tool = next(t for t in plugin.tools.values() if t.name == "set_power")
        tool = replace(tool, risk_class="EXTERNAL_SIDE_EFFECT")
        plugin.tools[tool.tool_id] = core.plugins.tools[tool.tool_id] = tool
    boundary, request = frozen_request(value)
    if kind == "approval":
        result = boundary.invoke_tool(
            request,
            tool.tool_id,
            {
                "resource_id": str(value["resources"][0]),
                "desired_on": True,
                "capability_id": str(
                    core.graph.resource_capabilities(value["resources"][0])[0].canonical_id
                ),
            },
        )
        assert result["status"] == "REQUIRE_CONFIRMATION", result
        assert boundary.submit_result(
            request,
            "isolated",
            IntelligenceResult(request.request_id, IntelligenceResultStatus.WAITING_CONFIRMATION),
        )
        decided = value["client"].post(
            f"/api/v1/approvals/{result['result']['approval_id']}",
            headers=value["headers"],
            json={"payload": {"decision": "APPROVE"}},
        )
        assert decided.status_code == 200, decided.text
    else:
        assert boundary.submit_result(
            request,
            "isolated",
            IntelligenceResult(
                request.request_id,
                IntelligenceResultStatus.RESPONSE,
                response_text="Synthetic current private reply.",
            ),
        )

        # Use the current live-result interface only for this disclosure test;
        # connected worker and resident tests separately prove delivery.
        class CurrentReply:
            def get(self, request_id: Any, household_id: Any) -> dict[str, Any] | None:
                if request_id == request.request_id and household_id == value["home"]:
                    return {
                        "request_id": str(request_id),
                        "response": "Synthetic current reply.",
                        "status": "RESPONSE",
                        "available": True,
                    }
                return None

        value["service"].sentry_results = CurrentReply()
    path = f"/api/v1/conversation/{request.request_id}"
    active = value["client"].get(path)
    assert active.status_code == 200 and active.json()["available"], active.text
    task = due_task(value)
    assert core.owner_task_results._creator(task)
    with psycopg.connect(value["url"]) as conn:
        conn.execute(
            "UPDATE anima_graph_nodes SET retired_at=now() WHERE canonical_id=%s", (value["owner"],)
        )
        membership = conn.execute(
            "SELECT count(*) FROM anima_graph_relationships WHERE source_id=%s "
            "AND target_id=%s AND relationship_type='MEMBER_OF' AND retired_at IS NULL",
            (value["owner"], value["home"]),
        ).fetchone()
        assert membership is not None and membership[0] == 1
    # Historical provenance remains readable, but cannot be current authority.
    assert core.graph.get_node(value["owner"]).retired_at is not None
    for resolve in (
        core.identity_resolver.resolve_principal,
        core.identity_resolver.resolve_role,
        core.identity_resolver.resolve_access_level,
    ):
        with pytest.raises(PrincipalMappingRequired):
            resolve(value["owner"])
    denied = value["client"].get(path)
    assert denied.status_code == 401 and "response" not in denied.json(), denied.text
    assert not core.owner_task_results._creator(task)
    assert len(value["transport"].calls) == (1 if kind == "approval" else 0)
