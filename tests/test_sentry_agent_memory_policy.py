"""Real OPA/PolicyStore qualification with synthetic requests and temporary notes.

No model, real vault, owner identity, transport or production policy changes.
Persistent-thread restriction checks reuse the existing isolated MCP fixture.
"""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from test_household_reasoning import request_for
from test_knowledge_api import fields, setup
from test_sentry_prebound_mcp import PRODUCTS, SAFE

from anima_ha.db.migrate import migrate
from anima_ha.family_routines import FAMILY_ROUTINES_MANIFEST, FamilyRoutinesNativePlugin
from anima_ha.intelligence import IntelligenceRequestFactory
from anima_ha.plugins import NativeRuntime
from anima_ha.policy import AutonomyPolicy, OpaPolicyClient, PolicyService, PostgresPolicyStore
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBoundaryError

pytest_plugins = ("test_sentry_prebound_mcp",)


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url or not os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"):
        pytest.skip("requires isolated routines PostgreSQL and real OPA")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    return url


def configured(
    tmp_path: Path,
    database_url: str,
    *,
    enabled: bool,
    autonomy: bool = True,
) -> tuple[CoreSentryBoundary, Any, Any]:
    _, _, manager, _ = setup(tmp_path)
    # A neighbouring native tool proves this flag is not a general mutation grant.
    manager.register(
        FAMILY_ROUTINES_MANIFEST, NativeRuntime(FamilyRoutinesNativePlugin(None, None))
    )
    manager.enable(FAMILY_ROUTINES_MANIFEST.plugin_id)
    template = request_for(manager)
    request = IntelligenceRequestFactory.for_direct_sentry_interaction(
        sentry_request_id=str(uuid4()),
        household_id=uuid4(),
        source_surface="voice",
        user_text="Synthetic bounded memory qualification",
        tools=manager.list_tools(),
        service_client_id="synthetic-household-client",
    )
    request = replace(
        request,
        lifecycle=template.lifecycle,
        claim_owner=template.claim_owner,
        lease_expires_at=template.lease_expires_at,
        fencing_generation=template.fencing_generation,
    )
    assert request.principal_id is None
    policy = PolicyService(
        OpaPolicyClient(os.environ["ANIMA_FAMILY_ROUTINES_TEST_OPA_URL"]),
        autonomy=AutonomyPolicy(security_secure_action=autonomy),
        audit_store=PostgresPolicyStore(database_url),
    )
    boundary = CoreSentryBoundary(
        manager,
        policy,
        cast(Any, SimpleNamespace(get=lambda _: request)),
        agent_memory_enabled=enabled,
    )
    return boundary, request, manager


def decisions(database_url: str, household_id: UUID) -> list[Any]:
    with psycopg.connect(database_url) as connection:
        return list(
            connection.execute(
                "SELECT decision, reason_code, principal_id, input_snapshot "
                "FROM anima_policy_decisions WHERE household_id=%s ORDER BY evaluated_at",
                (household_id,),
            ).fetchall()
        )


def test_disabled_agent_memory_gate_denies_create_and_update_before_policy_or_files(
    tmp_path: Path,
    database_url: str,
) -> None:
    boundary, request, _ = configured(tmp_path, database_url, enabled=False)
    for tool, arguments in (
        ("anima.knowledge.create_note", fields()),
        (
            "anima.knowledge.update_note",
            {**fields(), "note_id": str(uuid4()), "expected_digest": "0" * 64},
        ),
    ):
        result = boundary.invoke_tool(request, tool, arguments)
        assert result["status"] == "DENIED" and result["reason"] == "AGENT_MEMORY_NOT_ENABLED"
    assert not list((tmp_path / "ANIMA").rglob("*.md"))
    assert decisions(database_url, request.household_id) == []


def test_real_opa_allows_exact_builtin_create_update_without_forging_user_authority(
    tmp_path: Path,
    database_url: str,
) -> None:
    boundary, request, _ = configured(tmp_path, database_url, enabled=True)
    created = boundary.invoke_tool(request, "anima.knowledge.create_note", fields())
    assert created["status"] == "SUCCEEDED", created
    note = created["result"]["note"]
    assert note["principal_id"] is None and note["household_id"] == str(request.household_id)
    assert fields()["body"] not in json.dumps(created)
    updated_fields = {
        **fields(),
        "body": "SYNTHETIC_CORRECTED_NOTE_NOT_POLICY_INPUT",
        "note_id": note["note_id"],
        "expected_digest": note["digest"],
    }
    updated = boundary.invoke_tool(
        request, "anima.knowledge.update_note", updated_fields, ordinal=2
    )
    assert updated["status"] == "SUCCEEDED", updated
    assert updated["result"]["note"]["digest"] != note["digest"]
    assert updated["result"]["note"]["principal_id"] is None
    files = list((tmp_path / "ANIMA").rglob("*.md"))
    assert len(files) == 1
    assert updated_fields["body"] in files[0].read_text()
    assert fields()["body"] not in files[0].read_text()
    rows = decisions(database_url, request.household_id)
    assert len(rows) == 2
    for decision, reason, principal, snapshot in rows:
        assert decision == "ALLOW" and reason == "EXPLICIT_ANIMA_SECURE_AUTONOMY"
        assert principal is None and snapshot["identity"]["principal_id"] is None
        assert snapshot["origin"] == "AUTONOMOUS_AGENT"
        assert snapshot["identity"]["assurance"] not in {"AUTHENTICATED", "STRONG_AUTHENTICATED"}
        assert snapshot["identity"]["evidence_ids"] == []
        assert snapshot["policy"]["role"] is None
    assert fields()["body"] not in json.dumps(rows, default=str)
    assert updated_fields["body"] not in json.dumps(rows, default=str)
    with psycopg.connect(database_url) as connection:
        assert connection.execute(
            "SELECT count(*) FROM anima_identity_evidence WHERE household_id=%s",
            (request.household_id,),
        ).fetchone() == (0,)


def test_existing_opa_autonomy_disabled_case_denies_even_when_deployment_gate_enabled(
    tmp_path: Path,
    database_url: str,
) -> None:
    boundary, request, _ = configured(tmp_path, database_url, enabled=True, autonomy=False)
    result = boundary.invoke_tool(request, "anima.knowledge.create_note", fields())
    assert result["status"] == "DENIED"
    rows = decisions(database_url, request.household_id)
    assert len(rows) == 1 and rows[0][0] == "DENY" and rows[0][1] == "POLICY_DEFAULT_DENY"
    assert rows[0][3]["origin"] == "AUTONOMOUS_AGENT"
    assert not list((tmp_path / "ANIMA").rglob("*.md"))


def test_agent_memory_flag_cannot_authorize_routines_or_spoofed_builtin_source(
    tmp_path: Path,
    database_url: str,
) -> None:
    boundary, request, manager = configured(tmp_path, database_url, enabled=True)
    result = boundary.invoke_tool(
        request,
        "anima.family-routines.create_routine",
        {
            "person_id": str(uuid4()),
            "label": "Synthetic routine",
            "days": [0],
            "start": "01:00",
            "end": "02:00",
            "timezone": "UTC",
        },
    )
    assert result["status"] == "DENIED"
    rows = decisions(database_url, request.household_id)
    assert len(rows) == 1 and rows[0][1] == "POLICY_DEFAULT_DENY"
    assert rows[0][3]["origin"] == "DIRECT_USER"
    plugin = manager.plugins["anima.knowledge"]
    plugin.manifest = replace(plugin.manifest, source="builtin:synthetic_not_knowledge")
    with pytest.raises(SentryBoundaryError, match="AGENT_MEMORY_SOURCE_INVALID"):
        boundary.invoke_tool(request, "anima.knowledge.create_note", fields())
    assert len(decisions(database_url, request.household_id)) == 1
    assert not list((tmp_path / "ANIMA").rglob("*.md"))


@pytest.mark.parametrize("tool_id", PRODUCTS)
def test_restricted_products_remain_unavailable_to_persistent_thread(
    bound: Any, tool_id: str
) -> None:
    module, client, _, payload, _ = bound
    client.catalogue.append(
        {"tool_id": tool_id, "availability": True, "content_persistence": "EPHEMERAL_RESTRICTED"}
    )
    result = module.anima_list_tools(payload["request_id"])
    assert result["tools"] == [SAFE]
    assert module.anima_invoke(payload["request_id"], tool_id, {})["status"] == "UNAVAILABLE"
    assert not any(call[0] == "invoke" for call in client.calls)
