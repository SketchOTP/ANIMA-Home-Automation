"""Verify the H4 browser-facing Core contract against PostgreSQL and OPA.

The HTTP surface is real, the graph identity is commissioned, and the only
reasoning seam is a deterministic model response.  This target deliberately
does not use the UI echo fallback or direct task/calendar service calls.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from anima_ha.agent import (
    CodexTurnResult,
    FinalDecision,
    ScriptedCodexAdapter,
    TokenUsage,
)
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph, ProviderReference
from anima_ha.ui_api import UI_SESSION_COOKIE, create_app
from anima_ha.ui_runtime import CoreUICommandGateway

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HA_SCOPE = "phase12-h4-browser"
HA_USER_ID = "test-ha-user"


def _commission_identity(graph: PostgresHouseholdGraph) -> None:
    document = sample_household_document()
    graph.commission(document)
    person = next(node for node in document.nodes if node.name == "Sam")
    graph.map_provider_reference(
        ProviderReference(
            uuid5(NAMESPACE_URL, f"anima:{HA_SCOPE}:{HA_USER_ID}"),
            "home_assistant",
            HA_SCOPE,
            "user",
            HA_USER_ID,
            person.canonical_id,
        ),
        allow_remap=True,
    )


def _app() -> Any:
    os.environ["ANIMA_DATABASE_URL"] = DATABASE_URL
    os.environ["ANIMA_OPA_URL"] = OPA_URL
    os.environ["ANIMA_HA_PROVIDER_SCOPE"] = HA_SCOPE
    model = ScriptedCodexAdapter(
        [
            CodexTurnResult(
                FinalDecision(
                    "DONE", True, "The commissioned ANIMA cognition path is connected.", "done"
                ),
                TokenUsage(),
                1.0,
                (),
            )
            for _ in range(32)
        ]
    )
    return create_app(codex=model)


def _session(app: Any) -> tuple[TestClient, dict[str, str], Any]:
    service = app.state.ui_service
    identity = service.map_ha_user(HA_USER_ID)
    cookie, csrf = service.issue_session(identity, "h4-core")
    client = TestClient(app)
    client.cookies.set(UI_SESSION_COOKIE, cookie)
    return client, {"X-Anima-CSRF": csrf, "Origin": "http://testserver"}, service


def _assert_ok(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert body.get("status") == "SUCCEEDED", body
    return body


def main() -> int:
    _commission_identity(PostgresHouseholdGraph(DATABASE_URL))
    app = _app()
    client, headers, service = _session(app)
    assert isinstance(service.commands, CoreUICommandGateway)
    assert service.conversation.pipeline is not None
    assert service.conversation.fallback_enabled is False

    conversation = client.post(
        "/api/v1/conversation",
        json={"text": "Tell me whether the commissioned runtime is connected."},
        headers=headers,
    )
    assert conversation.status_code == 200, conversation.text
    conversation_body = conversation.json()
    assert conversation_body["response"] == "The commissioned ANIMA cognition path is connected."
    trace = conversation_body["trace"]
    assert trace["pipeline"] == "journal_attention_context_agent"
    for key in ("event_id", "context_packet_id", "correlation_id", "causation_id"):
        assert key in trace
    assert trace["correlation_id"] == trace["event_id"]
    assert conversation_body["episode_id"]

    task = _assert_ok(
        client.post(
            "/api/v1/tasks",
            json={
                "payload": {
                    "title": "H4 browser lifecycle reminder",
                    "when": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    "note": "real Core task mutation",
                }
            },
            headers=headers,
        )
    )
    tasks = client.get("/api/v1/tasks")
    task_item = next(
        item for item in tasks.json()["items"] if item["title"] == "H4 browser lifecycle reminder"
    )
    task_id = task_item["task_id"]
    paused = _assert_ok(
        client.post(f"/api/v1/tasks/{task_id}/pause", json={"payload": {}}, headers=headers)
    )
    resumed = _assert_ok(
        client.post(f"/api/v1/tasks/{task_id}/resume", json={"payload": {}}, headers=headers)
    )
    cancelled = _assert_ok(
        client.post(f"/api/v1/tasks/{task_id}/cancel", json={"payload": {}}, headers=headers)
    )

    start = datetime.now(UTC) + timedelta(days=3)
    end = start + timedelta(hours=1)
    created_event = _assert_ok(
        client.post(
            "/api/v1/calendar",
            json={
                "payload": {
                    "title": "H4 editable event",
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "timezone": "UTC",
                }
            },
            headers=headers,
        )
    )
    events = client.get("/api/v1/calendar").json()["items"]
    event = next(item for item in events if item["title"] == "H4 editable event")
    event_id, version = event["event_id"], event["version"]
    updated = _assert_ok(
        client.post(
            f"/api/v1/calendar/{event_id}/update",
            json={
                "payload": {
                    "expected_version": version,
                    "title": "H4 edited event",
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "timezone": "UTC",
                }
            },
            headers=headers,
        )
    )
    stale = client.post(
        f"/api/v1/calendar/{event_id}/update",
        json={
            "payload": {
                "expected_version": version,
                "title": "H4 stale overwrite",
            }
        },
        headers=headers,
    )
    assert stale.status_code == 200 and stale.json()["status"] == "FAILED", stale.text
    current = next(
        item
        for item in client.get("/api/v1/calendar").json()["items"]
        if item["event_id"] == event_id
    )
    cancelled_event = _assert_ok(
        client.post(
            f"/api/v1/calendar/{event_id}/cancel",
            json={"payload": {"expected_version": updated["result"]["event"]["version"]}},
            headers=headers,
        )
    )

    settings = {
        "appearance": "light",
        "accent": "sky",
        "density": "compact",
        "reduced_motion": True,
        "text_scale": "large",
        "display_mode": "tablet",
        "visible_widgets": ["status", "tasks", "agenda"],
        "widget_order": ["agenda", "tasks", "status"],
    }
    saved = client.put("/api/v1/settings", json={"payload": settings}, headers=headers)
    assert saved.status_code == 200 and saved.json()["settings"]["appearance"] == "light", (
        saved.text
    )

    restarted = _app()
    # Reconstruct the application while retaining the original browser cookie.
    # Only the CSRF token is rotated by the normal bootstrap response; issuing a
    # replacement session would not prove process-restart continuity.
    restarted_client = TestClient(restarted)
    original_cookie = client.cookies.get(UI_SESSION_COOKIE)
    assert original_cookie is not None
    restarted_client.cookies.set(UI_SESSION_COOKIE, original_cookie)
    restarted_bootstrap = restarted_client.get("/api/v1/bootstrap")
    assert restarted_bootstrap.status_code == 200, restarted_bootstrap.text
    restarted_service = restarted.state.ui_service
    persisted = restarted_client.get("/api/v1/settings").json()["settings"]
    assert persisted == {**settings, "version": persisted["version"]}
    assert restarted_service.conversation.fallback_enabled is False
    assert restarted_client.get("/api/v1/tasks").status_code == 200
    assert restarted_client.get("/api/v1/calendar").status_code == 200

    print(
        json.dumps(
            {
                "composition": "create_app_postgres_core",
                "fallback_enabled": service.conversation.fallback_enabled,
                "conversation": {
                    "pipeline": trace["pipeline"],
                    "event_id": trace["event_id"],
                    "context_packet_id": trace["context_packet_id"],
                    "episode_id": conversation_body["episode_id"],
                },
                "task": {
                    "create": task["status"],
                    "pause": paused["status"],
                    "resume": resumed["status"],
                    "cancel": cancelled["status"],
                },
                "calendar": {
                    "create": created_event["status"],
                    "update": updated["status"],
                    "stale_update": stale.json()["status"],
                    "cancel": cancelled_event["status"],
                    "version_after_update": current["version"],
                },
                "settings_restart": persisted,
                "original_session_survived_restart": True,
                "ha": "EXTERNAL_RESOURCE_GATE_HA_COMMISSIONING",
                "phase13": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
