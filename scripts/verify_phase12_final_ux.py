"""Exercise the normal Phase 12 composition with only the model scripted.

The database, graph, journal, attention, context, OPA, plugin, task, calendar,
and UI boundaries are real.  A deterministic model adapter is the sole test
seam so this target remains reproducible without a live Codex account.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from fastapi.testclient import TestClient

from anima_ha.agent import CodexTurnResult, FinalDecision, ScriptedCodexAdapter, TokenUsage
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph, ProviderReference
from anima_ha.ui_api import (
    UI_SESSION_COOKIE,
    create_app,
)
from anima_ha.ui_runtime import CoreUICommandGateway

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@localhost:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HA_SCOPE = os.environ.get("ANIMA_HA_PROVIDER_SCOPE", "phase12-final-ux")
HA_USER_ID = "phase12-final-ux-user"


def main() -> int:
    graph = PostgresHouseholdGraph(DATABASE_URL)
    document = sample_household_document()
    graph.commission(document)
    person = next(node for node in document.nodes if node.name == "Alex")
    graph.map_provider_reference(
        ProviderReference(
            uuid5(NAMESPACE_URL, f"anima:phase12:final-ux:{HA_SCOPE}:{HA_USER_ID}"),
            "home_assistant",
            HA_SCOPE,
            "user",
            HA_USER_ID,
            person.canonical_id,
        ),
        allow_remap=True,
    )
    model = ScriptedCodexAdapter(
        [
            CodexTurnResult(
                FinalDecision("DONE", True, "The connected ANIMA runtime is ready.", "done"),
                TokenUsage(),
                1.0,
                (),
            )
        ]
    )
    app = create_app(codex=model)
    service = app.state.ui_service
    assert isinstance(service.commands, CoreUICommandGateway)
    assert service.conversation.fallback_enabled is False
    assert service.conversation.pipeline is not None

    identity = service.map_ha_user(HA_USER_ID)
    cookie, csrf = service.issue_session(identity, "final-ux-target")
    client = TestClient(app)
    client.cookies.set(UI_SESSION_COOKIE, cookie)
    headers = {"X-Anima-CSRF": csrf, "Origin": "http://testserver"}

    conversation = client.post(
        "/api/v1/conversation",
        json={"text": "Connect to the commissioned runtime."},
        headers=headers,
    )
    assert conversation.status_code == 200, conversation.text
    task = client.post(
        "/api/v1/tasks",
        json={
            "payload": {
                "title": "Final UX durable reminder",
                "when": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                "note": "normal create_app path",
            }
        },
        headers=headers,
    )
    assert task.status_code == 200 and task.json()["status"] == "SUCCEEDED", task.text
    settings = client.put(
        "/api/v1/settings",
        json={"payload": {"accent": "sky", "reduced_motion": True}},
        headers=headers,
    )
    assert settings.status_code == 200, settings.text

    print(
        json.dumps(
            {
                "composition": "create_app_postgres_core",
                "fallback_enabled": service.conversation.fallback_enabled,
                "task_status": task.json()["status"],
                "conversation": conversation.json(),
                "settings_accent": settings.json()["settings"]["accent"],
                "household_id": str(identity.household_id),
                "principal_id": str(identity.principal_id),
                "ha_capability": "EXTERNAL_RESOURCE_GATE_HA_COMMISSIONING",
                "phase13": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
