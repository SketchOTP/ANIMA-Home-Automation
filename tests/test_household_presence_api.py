"""Real HTTP/Core tool path with synthetic Graph/Truth and explicit policy seam."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from test_family_routines_api import login
from test_household_presence import HOME, INSTANCE, NOW, PERSON, Graph, binding
from test_knowledge_api import Evaluator

from anima_ha.household_presence import (
    HOUSEHOLD_PRESENCE_MANIFEST,
    HouseholdPresenceNativePlugin,
    HouseholdPresenceService,
    SignalKind,
)
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import PolicyService
from anima_ha.ui_api import UIConfig, UIService
from anima_ha.ui_runtime import CoreUICommandGateway


def setup(*, deny: bool = False) -> tuple[Any, dict[str, str], Any, Graph]:
    graph = Graph()
    graph.add(binding(SignalKind.ROUTER_WIFI))
    evaluator = Evaluator(deny)
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_PRESENCE_MANIFEST,
        NativeRuntime(
            HouseholdPresenceNativePlugin(
                HouseholdPresenceService(
                    graph, graph.truth, classify_source=lambda _: SignalKind.ROUTER_WIFI
                ),
                INSTANCE,
                now=lambda: NOW,
            )
        ),
    )
    manager.enable(HOUSEHOLD_PRESENCE_MANIFEST.plugin_id)
    gateway = CoreUICommandGateway(manager, PolicyService(evaluator))
    service = UIService(
        config=UIConfig(test_auth_enabled=True),
        commands=gateway,
        read_model=SimpleNamespace(graph=graph),
        ha_user_map={"test-ha-user": (HOME, PERSON)},
    )
    client, headers = login(service)
    return client, headers, evaluator, graph


def test_presence_read_is_coarse_owner_scoped_and_sources_have_no_network_ids() -> None:
    client, _, evaluator, _ = setup()
    result = client.get("/api/v1/presence")
    assert result.status_code == 200, result.text
    page = result.json()
    assert page["can_edit"] is True
    assert page["items"][0]["value"] == "HOME"
    assert page["items"][0]["is_authentication"] is False
    sources = client.get("/api/v1/presence/sources")
    assert sources.status_code == 200, sources.text
    assert len(sources.json()["items"]) == 1
    assert "device_tracker." not in result.text + sources.text
    assert "mac" not in result.text.lower() + sources.text.lower()
    assert evaluator.documents


def test_assignment_session_owner_and_policy_denial_zero_change() -> None:
    client, headers, evaluator, graph = setup()
    handle = client.get("/api/v1/presence/sources").json()["items"][0]["source_handle"]
    payload = {"person_id": str(PERSON), "source_handle": handle, "freshness_seconds": 300}
    before = len(graph.commissions)
    evaluator.deny = True
    denied = client.post("/api/v1/presence/bind", headers=headers, json={"payload": payload})
    assert denied.status_code == 200 and denied.json()["status"] == "DENIED"
    assert len(graph.commissions) == before
    evaluator.deny = False
    for field in ("role", "household_id", "mac", "entity_id"):
        response = client.post(
            "/api/v1/presence/bind", headers=headers, json={"payload": {**payload, field: "FORGED"}}
        )
        assert response.status_code == 400 or response.json()["status"] != "SUCCEEDED"
    assert "FORGED" not in json.dumps(evaluator.documents)
    assert len(graph.commissions) == before


def test_presence_requires_session_and_binding_requires_csrf() -> None:
    client, _, _, graph = setup()
    assert client.post("/api/v1/presence/bind", json={"payload": {}}).status_code == 403
    assert not graph.commissions
    client.cookies.clear()
    assert client.get("/api/v1/presence").status_code == 401
    assert client.get("/api/v1/presence/sources").status_code == 401
