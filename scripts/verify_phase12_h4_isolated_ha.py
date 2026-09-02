"""Verify the browser command boundary against the real isolated HA fixture."""

from __future__ import annotations

import json
import os
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi.testclient import TestClient
from verify_phase6_home_assistant import (
    DockerHomeAssistant,
    commission_phase6_graph,
    onboard,
)

from anima_ha.agent import CodexTurnResult, FinalDecision, ScriptedCodexAdapter, TokenUsage
from anima_ha.graph import (
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
)
from anima_ha.ui_api import UI_SESSION_COOKIE, create_app

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HA_USER_ID = "h4-isolated-ui-user"
# Each harness run receives a fresh provider scope so stale mappings from a
# prior Docker fixture cannot contaminate the canonical resource resolution.
H4_INSTANCE_ID = uuid4()
HA_SCOPE = str(H4_INSTANCE_ID)


def _model() -> ScriptedCodexAdapter:
    return ScriptedCodexAdapter(
        [
            CodexTurnResult(
                FinalDecision("DONE", True, "The isolated ANIMA path is connected.", "done"),
                TokenUsage(),
                1.0,
                (),
            )
            for _ in range(4)
        ]
    )


def main() -> int:
    fixture = DockerHomeAssistant()
    token = ""
    try:
        fixture.start_new()
        token = onboard(fixture.base_url)
        websocket_url = fixture.base_url.replace("http://", "ws://") + "/api/websocket"
        graph = PostgresHouseholdGraph(DATABASE_URL)
        resource_id, _capability_id, _input_entity, _device_id, _linked_entity = (
            commission_phase6_graph(graph, _discovery(websocket_url, token), HA_SCOPE)
        )
        # The phase-6 commissioning includes the canonical sample household;
        # map the dedicated UI user to its commissioned resident without
        # copying provider credentials into the application or model.
        from anima_ha.fixtures import sample_household_document

        sample = sample_household_document()
        household = next(node for node in sample.nodes if node.kind == NodeKind.HOUSEHOLD)
        kitchen = next(node for node in sample.nodes if node.name == "Kitchen")
        resource = graph.get_node(resource_id)
        assert resource is not None
        graph.commission(
            CommissioningDocument(
                1,
                (household, kitchen, resource),
                (
                    CanonicalRelationship(
                        uuid5(NAMESPACE_URL, "anima:h4-isolated-ui:installed-in"),
                        RelationshipType.INSTALLED_IN,
                        resource_id,
                        kitchen.canonical_id,
                    ),
                ),
            )
        )
        resident = next(node for node in sample.nodes if node.name == "Sam")
        graph.map_provider_reference(
            ProviderReference(
                uuid5(NAMESPACE_URL, f"anima:h4-isolated:{HA_SCOPE}:{HA_USER_ID}"),
                "home_assistant",
                HA_SCOPE,
                "user",
                HA_USER_ID,
                resident.canonical_id,
            ),
            allow_remap=True,
        )
        os.environ.update(
            {
                "ANIMA_DATABASE_URL": DATABASE_URL,
                "ANIMA_OPA_URL": OPA_URL,
                "ANIMA_HA_ACCESS_TOKEN": token,
                "ANIMA_HA_TOKEN_SECRET_NAME": "ANIMA_HA_ACCESS_TOKEN",
                "ANIMA_HA_WEBSOCKET_URL": websocket_url,
                "ANIMA_HA_INSTANCE_ID": str(H4_INSTANCE_ID),
                "ANIMA_HA_PROVIDER_SCOPE": HA_SCOPE,
            }
        )
        app: Any = create_app(codex=_model())
        service = app.state.ui_service
        identity = service.map_ha_user(HA_USER_ID)
        cookie, csrf = service.issue_session(identity, "h4-isolated-ui")
        headers = {"X-Anima-CSRF": csrf, "Origin": "http://testserver"}
        with TestClient(app) as client:
            client.cookies.set(UI_SESSION_COOKIE, cookie)
            home = client.get("/api/v1/home")
            assert home.status_code == 200, home.text
            control = next(item for item in home.json()["controls"] if item["control_id"])
            control_id = str(control["control_id"])
            success = client.post(
                f"/api/v1/controls/{control_id}",
                json={"payload": {"desired_on": True}},
                headers=headers,
            )
            assert success.status_code == 200, success.text
            success_body = success.json()
            assert success_body["status"] == "SUCCEEDED", success_body

            ha_plugin = service.commands.manager.plugins[
                "anima.provider.home-assistant"
            ].runtime.plugin
            adapter = ha_plugin.adapter
            original_read = adapter.read_state

            def wrong_observation(resource: UUID, capability: UUID | None = None) -> dict[str, Any]:
                observed = dict(original_read(resource, capability))
                observed["state"] = "off"
                return observed

            adapter.read_state = wrong_observation
            mismatch = client.post(
                f"/api/v1/controls/{control_id}",
                json={"payload": {"desired_on": True}},
                headers=headers,
            )
            adapter.read_state = original_read
            assert mismatch.status_code == 200, mismatch.text
            mismatch_body = mismatch.json()
            assert mismatch_body["status"] in {"FAILED", "VERIFICATION_FAILED"}, mismatch_body

            print(
                json.dumps(
                    {
                        "fixture": "phase6_docker_home_assistant",
                        "ui_path": "HTTP -> CoreUICommandGateway -> Phase5 -> OPA -> Phase9 -> HA",
                        "success": success_body["status"],
                        "success_evidence": success_body["evidence"],
                        "deliberate_mismatch": mismatch_body["status"],
                        "mismatch_evidence": mismatch_body["evidence"],
                        "phase13": False,
                    },
                    sort_keys=True,
                )
            )
        return 0
    finally:
        fixture.close()


def _discovery(websocket_url: str, token: str) -> Any:
    from anima_ha.home_assistant import HAInstanceConfig, HassClientConnection

    config = HAInstanceConfig(H4_INSTANCE_ID, websocket_url, "ANIMA_HA_ACCESS_TOKEN", ssl=False)
    connection = HassClientConnection(
        config,
        token,
        event_callback=lambda event: None,
        disconnect_callback=lambda error: None,
    )
    try:
        discovery = connection.start()
        connection.activate()
        return discovery
    finally:
        connection.stop()


if __name__ == "__main__":
    raise SystemExit(main())
