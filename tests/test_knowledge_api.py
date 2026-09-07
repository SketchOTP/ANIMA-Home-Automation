"""Real HTTP routing + Core PluginManager + temporary native note files."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient

from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequestFactory,
)
from anima_ha.knowledge import KNOWLEDGE_MANIFEST, KnowledgeConfig, KnowledgeNativePlugin
from anima_ha.plugins import (
    ContentPersistence,
    ExecutionBoundary,
    NativeRuntime,
    PluginManager,
)
from anima_ha.policy import PolicyService
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_api import (
    DEFAULT_HOUSEHOLD_ID,
    DEFAULT_PRINCIPAL_ID,
    UIConfig,
    UIEventBroadcaster,
    UIService,
    create_app,
)
from anima_ha.ui_runtime import CoreUICommandGateway


class Evaluator:
    def __init__(self, deny: bool = False) -> None:
        self.deny = deny
        self.documents: list[dict[str, Any]] = []

    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        self.documents.append(document)
        return {
            "decision": "DENY" if self.deny else "ALLOW",
            "reason_code": "SYNTHETIC_POLICY",
            "policy_version": "test",
        }


def setup(
    tmp_path: Path, *, deny: bool = False
) -> tuple[TestClient, str, PluginManager, Evaluator]:
    managed = tmp_path / "ANIMA"
    managed.mkdir(mode=0o700)
    evaluator = Evaluator(deny)
    manager = PluginManager()
    manager.register(
        KNOWLEDGE_MANIFEST, NativeRuntime(KnowledgeNativePlugin(KnowledgeConfig(managed)))
    )
    manager.enable(KNOWLEDGE_MANIFEST.plugin_id)
    gateway = CoreUICommandGateway(manager, PolicyService(evaluator), events=UIEventBroadcaster())
    service = UIService(config=UIConfig(test_auth_enabled=True), commands=gateway)
    client = TestClient(create_app(service), follow_redirects=False)
    login = client.get("/auth/login")
    callback = client.get(login.headers["location"])
    return client, callback.headers["x-anima-csrf"], manager, evaluator


def fields() -> dict[str, Any]:
    return {
        "title": "Synthetic evidence",
        "body": "PROSE_SENTINEL_NOT_IN_POLICY_AUDIT",
        "note_type": "lesson",
        "classifier": "640",
        "classification": "SENTRY_INFERENCE",
        "confidence": 0.4,
        "source_refs": [
            {
                "kind": "event",
                "source_id": "synthetic-1",
                "meaning": "Attributed synthetic evidence",
            }
        ],
    }


def headers(csrf: str) -> dict[str, str]:
    return {"Origin": "http://testserver", "X-Anima-CSRF": csrf}


def test_http_core_filesystem_journey_and_body_free_policy_audit(tmp_path: Path) -> None:
    client, csrf, manager, evaluator = setup(tmp_path)
    assert client.get("/api/v1/knowledge").json()["items"] == []
    created = client.post(
        "/api/v1/knowledge/create", json={"payload": fields()}, headers=headers(csrf)
    )
    assert created.status_code == 200
    assert created.json()["status"] == "SUCCEEDED"
    note = created.json()["result"]["note"]
    assert fields()["body"] not in created.text
    assert fields()["body"] not in json.dumps(evaluator.documents)
    read = client.get(f"/api/v1/knowledge/{note['note_id']}").json()
    assert read["note"]["body"] == fields()["body"]
    assert read["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    assert note["household_id"] == str(DEFAULT_HOUSEHOLD_ID)
    assert note["principal_id"] == str(DEFAULT_PRINCIPAL_ID)
    edited = client.post(
        "/api/v1/knowledge/update",
        json={
            "payload": {
                **fields(),
                "body": "Corrected synthetic evidence",
                "enabled": False,
                "note_id": note["note_id"],
                "expected_digest": note["digest"],
            }
        },
        headers=headers(csrf),
    ).json()
    assert edited["status"] == "SUCCEEDED"
    assert not edited["result"]["note"]["enabled"]
    stale = client.post(
        "/api/v1/knowledge/update",
        json={
            "payload": {
                **fields(),
                "note_id": note["note_id"],
                "expected_digest": note["digest"],
            }
        },
        headers=headers(csrf),
    ).json()
    assert stale["status"] == "FAILED" and stale["reason"] == "KnowledgeConflict"
    retracted = client.post(
        "/api/v1/knowledge/retract",
        json={
            "payload": {
                "note_id": note["note_id"],
                "expected_digest": edited["result"]["note"]["digest"],
            }
        },
        headers=headers(csrf),
    ).json()
    assert retracted["status"] == "SUCCEEDED"
    assert client.get("/api/v1/knowledge").json()["items"] == []
    assert "body" not in client.get(f"/api/v1/knowledge/{note['note_id']}").json()["note"]
    descriptors = manager.list_tools()
    assert all(tool.content_persistence == ContentPersistence.FULL_DURABLE for tool in descriptors)
    assert all(
        tool.execution_boundary == ExecutionBoundary.POLICY_GATED_INTERNAL
        for tool in descriptors
        if not tool.read_only
    )


def test_http_auth_csrf_origin_and_unknown_fields_fail_closed(tmp_path: Path) -> None:
    client, csrf, _, _ = setup(tmp_path)
    assert client.post("/api/v1/knowledge/create", json={"payload": fields()}).status_code == 403
    assert (
        client.post(
            "/api/v1/knowledge/create",
            json={"payload": fields()},
            headers={
                **headers(csrf),
                "Origin": "https://attacker.invalid",
            },
        ).status_code
        == 403
    )
    invalid = client.post(
        "/api/v1/knowledge/create",
        json={
            "payload": {
                **fields(),
                "household_id": str(uuid4()),
            }
        },
        headers=headers(csrf),
    ).json()
    assert invalid["status"] == "FAILED"
    assert client.get("/api/v1/knowledge?limit=51").status_code == 422
    client.cookies.clear()
    assert client.get("/api/v1/knowledge").status_code == 401
    assert (
        client.post(
            "/api/v1/knowledge/create", json={"payload": fields()}, headers=headers(csrf)
        ).status_code
        == 401
    )
    assert not list((tmp_path / "ANIMA").rglob("*.md"))


def test_policy_denial_creates_no_notes(tmp_path: Path) -> None:
    client, csrf, _, _ = setup(tmp_path, deny=True)
    response = client.post(
        "/api/v1/knowledge/create", json={"payload": fields()}, headers=headers(csrf)
    )
    assert response.json()["status"] == "DENIED"
    assert client.get("/api/v1/knowledge").status_code == 403
    assert list((tmp_path / "ANIMA").iterdir()) == []


def test_unconfigured_is_honest_and_read_does_not_invalidate_itself(tmp_path: Path) -> None:
    client, _, manager, _ = setup(tmp_path)
    service = client.app.state.ui_service  # type: ignore[attr-defined]
    channel = service.commands.events.subscribe(uuid4())
    assert client.get("/api/v1/knowledge").status_code == 200
    assert not channel
    manager.disable(KNOWLEDGE_MANIFEST.plugin_id)
    assert client.get("/api/v1/knowledge").status_code == 503


def test_real_sentry_boundary_retains_tools_and_invokes_without_embedded_audit(
    tmp_path: Path,
) -> None:
    _, _, manager, evaluator = setup(tmp_path)
    request = IntelligenceRequestFactory.for_trigger(
        uuid4(),
        household_id=DEFAULT_HOUSEHOLD_ID,
        origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
        context_packet_id=uuid4(),
        context_digest="synthetic",
        tools=manager.list_tools(),
        provider_id="sentry",
        provider_version="synthetic",
    )
    request = replace(
        request,
        lifecycle=IntelligenceLifecycle.PROVIDER_RUNNING,
        claim_owner="synthetic-sentry",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=1),
        fencing_generation=1,
    )
    store = SimpleNamespace(get=lambda request_id: request)
    boundary = CoreSentryBoundary(
        manager, PolicyService(evaluator), cast(Any, store), agent_memory_enabled=True
    )
    assert {item["name"] for item in boundary.catalogue(request)} == {
        "list_notes",
        "get_note",
        "search_notes",
        "memory_index",
        "create_note",
        "update_note",
        "retract_note",
        "purge_expired",
    }
    result = boundary.invoke_tool(request, "anima.knowledge.create_note", fields())
    assert result["status"] == "SUCCEEDED"
    assert fields()["body"] not in json.dumps(result)
    note_id = result["result"]["note"]["note_id"]
    read = boundary.invoke_tool(
        request, "anima.knowledge.get_note", {"note_id": note_id}, ordinal=2
    )
    assert read["result"]["note"]["body"] == fields()["body"]
    assert fields()["body"] not in json.dumps(evaluator.documents)


def test_exact_source_mapping_cannot_be_spoofed(tmp_path: Path) -> None:
    _, _, manager, _ = setup(tmp_path)
    original = KNOWLEDGE_MANIFEST
    forged = replace(original, source="untrusted:other")
    other = PluginManager()
    other.register(
        forged, NativeRuntime(KnowledgeNativePlugin(KnowledgeConfig(tmp_path / "ANIMA")))
    )
    assert all(
        tool.execution_boundary == ExecutionBoundary.COORDINATED_CONSEQUENTIAL
        for tool in other.list_tools()
        if not tool.read_only
    )
    assert len(manager.list_tools()) == 8
