"""Real isolated store, real policy evaluator; no owner state/model/physical calls."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from test_stage2_delivery_postgres import isolated_url as isolated_url

from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.household_event_context import HouseholdEventEvidence
from anima_ha.household_learning import (
    HOUSEHOLD_LEARNING_MANIFEST,
    HouseholdLearningError,
    HouseholdLearningNativePlugin,
    HouseholdLearningService,
    learning_request_scope,
)
from anima_ha.household_situation import HouseholdSituation, public_delivery
from anima_ha.intelligence import (
    IntelligenceOrigin,
    IntelligenceRequestFactory,
    PostgresIntelligenceStore,
)
from anima_ha.journal import PostgresEventJournal
from anima_ha.memory import MemoryService
from anima_ha.plugins import NativeRuntime, PluginManager
from anima_ha.policy import (
    Assurance,
    EvidenceType,
    IdentityEvidence,
    OpaPolicyClient,
    PolicyService,
    PostgresPolicyStore,
)
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_api import UIConfig, UIIdentity, UIService, create_app
from anima_ha.ui_runtime import CoreUICommandGateway


@pytest.fixture
def situation(isolated_url: str) -> Iterator[dict[str, Any]]:
    home, foreign, room, other_room, owner, member, sensor, other_sensor = (
        uuid4() for _ in range(8)
    )
    ids = [home, foreign, room, other_room, owner, member, sensor, other_sensor]
    with psycopg.connect(isolated_url) as conn:
        for key, kind, name, metadata in (
            (home, "HOUSEHOLD", "Isolated home", {}),
            (foreign, "HOUSEHOLD", "Other tenant", {}),
            (room, "ROOM", "Room", {}),
            (other_room, "ROOM", "Other room", {}),
            (owner, "PERSON", "Owner", {"semantic_role": "owner"}),
            (member, "PERSON", "Member", {}),
            (sensor, "RESOURCE", "Sensor", {}),
            (other_sensor, "RESOURCE", "Foreign sensor", {}),
        ):
            conn.execute(
                "INSERT INTO anima_graph_nodes(canonical_id,kind,name,metadata) "
                "VALUES(%s,%s,%s,%s::jsonb)",
                (key, kind, name, json.dumps(metadata)),
            )
        for kind, source, target in (
            ("CONTAINS", home, room),
            ("CONTAINS", foreign, other_room),
            ("MEMBER_OF", owner, home),
            ("MEMBER_OF", member, home),
            ("INSTALLED_IN", sensor, room),
            ("INSTALLED_IN", other_sensor, other_room),
        ):
            conn.execute(
                "INSERT INTO anima_graph_relationships "
                "(relationship_id,relationship_type,source_id,target_id) VALUES(%s,%s,%s,%s)",
                (uuid4(), kind, source, target),
            )
    graph = PostgresHouseholdGraph(isolated_url)
    evidence = HouseholdEventEvidence(isolated_url, graph)
    reader = HouseholdSituation(
        isolated_url,
        graph,
        evidence,
        lambda hh: {
            "status": "NOT_READY",
            "reason": "ISOLATED_SOURCE_FAULT",
            "uptime": None,
            "opportunity_denominator": None,
        },
    )
    service = HouseholdLearningService(
        MemoryService(isolated_url),
        graph,
        evidence_reader=evidence.recent_household_evidence,
        situation_reader=reader,
    )
    value = dict(
        url=isolated_url,
        home=home,
        foreign=foreign,
        owner=owner,
        member=member,
        sensor=sensor,
        other_sensor=other_sensor,
        reader=reader,
        service=service,
        graph=graph,
        journal=PostgresEventJournal(isolated_url),
    )
    try:
        yield value
    finally:
        with psycopg.connect(isolated_url) as conn:
            # Keep immutable Journal/Memory/request evidence in the disposable
            # store. Retire only this fixture's random commissioned nodes.
            conn.execute(
                "UPDATE anima_graph_nodes SET retired_at=now() WHERE canonical_id=ANY(%s)", (ids,)
            )


def observation(value: dict[str, Any], *, age: int = 1, foreign: bool = False) -> str:
    home = value["foreign"] if foreign else value["home"]
    resource = value["other_sensor"] if foreign else value["sensor"]
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        delivery_class=DeliveryClass.GUARANTEED,
        event_type="household.ring.motion",
        source="anima.ring",
        source_event_id=str(uuid4()),
        subject_key=f"resource/{resource}",
        occurred_at=datetime.now(UTC) - timedelta(seconds=age),
        payload={"resource_id": str(resource), "raw_text": "PRIVATE_RAW_SENTINEL"},
        metadata={"household_id": str(home)},
    )
    value["journal"].append(event)
    return str(event.event_id)


def active_boundary(value: dict[str, Any], *, memory_enabled: bool = True) -> tuple[Any, Any]:
    opa = os.environ.get("ANIMA_STAGE3_TEST_OPA_URL")
    if not opa:
        pytest.skip("requires explicit stateless OPA test endpoint")
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_LEARNING_MANIFEST, NativeRuntime(HouseholdLearningNativePlugin(value["service"]))
    )
    manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    store = PostgresIntelligenceStore(value["url"])
    boundary = CoreSentryBoundary(
        manager,
        PolicyService(OpaPolicyClient(opa), audit_store=PostgresPolicyStore(value["url"])),
        store,
        learning_service=value["service"],
        agent_memory_enabled=memory_enabled,
        access_level_resolver=lambda _: "LIMITED",
        reasoning_context_loader=lambda request: {
            "initiative": {
                "nearby_events": value["reader"](request.household_id)["observations"],
            }
        },
    )
    pending = replace(
        IntelligenceRequestFactory.for_direct_sentry_interaction(
            sentry_request_id=str(uuid4()),
            household_id=value["home"],
            source_surface="isolated-stage3",
            user_text="Isolated assessment",
            tools=manager.list_tools(),
            service_client_id="isolated",
        ),
        origin=IntelligenceOrigin.AUTONOMOUS_ATTENTION,
    )
    store.enqueue(pending)
    request = store.claim_specific(
        pending.request_id, "isolated-worker", household_id=value["home"], provider_id="sentry"
    )
    assert request and request.claim_owner
    assert boundary.start_provider(request, request.claim_owner)
    return boundary, store.get(request.request_id)


def test_declared_mode_owner_version_race_restart_and_isolation(situation: dict[str, Any]) -> None:
    service, home, owner = situation["service"], situation["home"], situation["owner"]
    assert service.declared_mode(home)["mode"] == "UNSET"

    def save(mode: str) -> Any:
        try:
            return service.set_household_mode(home, owner, {"mode": mode, "expected_version": None})
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ("HOME", "AWAY")))
    assert sum(item is not None for item in results) == 1
    current = service.declared_mode(home)
    reloaded = HouseholdLearningService(MemoryService(situation["url"]), situation["graph"])
    assert reloaded.declared_mode(home) == current
    for household, principal in ((home, situation["member"]), (situation["foreign"], owner)):
        with pytest.raises(ValueError):
            service.set_household_mode(
                household, principal, {"mode": "AWAY", "expected_version": None}
            )
    with pytest.raises(ValueError, match="version changed"):
        service.set_household_mode(home, owner, {"mode": "AWAY", "expected_version": None})
    changed = service.set_household_mode(
        home, owner, {"mode": "UNSET", "expected_version": current["version"]}
    )
    assert changed["declared_mode"]["version"] != current["version"]


def test_bounded_current_context_does_not_infer_identity_away_quiet_or_uptime(
    situation: dict[str, Any],
) -> None:
    event = observation(situation)
    old = observation(situation, age=601)
    foreign = observation(situation, foreign=True)
    result = situation["service"].get_situation(situation["home"])
    assert result["declared_mode"]["mode"] == "UNSET"
    assert {item["event_id"] for item in result["observations"]["items"]} == {event}
    assert all(item["physical_occurred_at"] is None for item in result["observations"]["items"])
    assert result["source_coverage"]["status"] == "NOT_READY"
    assert result["source_coverage"]["uptime"] is None
    rendered = json.dumps(result)
    assert str(situation["other_sensor"]) not in rendered
    assert (
        old not in rendered and foreign not in rendered and "PRIVATE_RAW_SENTINEL" not in rendered
    )


def test_real_frozen_boundary_incident_narrow_memory_gate_and_owner_mode_denial(
    situation: dict[str, Any],
) -> None:
    event = observation(situation)
    service, home = situation["service"], situation["home"]
    service.set_household_mode(home, situation["owner"], {"mode": "AWAY", "expected_version": None})
    boundary, request = active_boundary(situation)
    arguments = {
        "event_ids": [event],
        "assessment": "Motion reported while owner declared Away; actor unknown.",
        "unknowns": [
            "Legitimate arrival possible.",
            "Physical time and actor unverified.",
            "Other source coverage unavailable.",
        ],
    }
    tool = "anima.household-learning.record_incident_assessment"
    result = boundary.invoke_tool(request, tool, arguments)
    assert result["status"] == "SUCCEEDED", result
    assert result == boundary.invoke_tool(request, tool, arguments)
    assert result["result"]["classification"] == "SENTRY_INFERRED_ASSESSMENT"
    assert result["result"]["declared_mode"]["mode"] == "AWAY"
    assert (
        boundary.invoke_tool(
            request,
            "anima.household-learning.set_household_mode",
            {"mode": "HOME", "expected_version": service.declared_mode(home)["version"]},
            ordinal=2,
        )["status"]
        != "SUCCEEDED"
    )
    assert service.declared_mode(home)["mode"] == "AWAY"
    assert (
        boundary.invoke_tool(request, tool, {**arguments, "event_ids": [str(uuid4())]}, ordinal=3)[
            "status"
        ]
        != "SUCCEEDED"
    )
    with psycopg.connect(situation["url"]) as conn:
        policy = conn.execute(
            "SELECT reason_code,input_snapshot FROM anima_policy_decisions "
            "WHERE household_id=%s AND decision='ALLOW'",
            (home,),
        ).fetchall()
    assert policy and all(row[0] == "EXPLICIT_ANIMA_SECURE_AUTONOMY" for row in policy)
    assert all(row[1]["identity"]["principal_id"] is None for row in policy)
    boundary.agent_memory_enabled = False
    assert boundary.invoke_tool(request, tool, arguments, ordinal=4)["status"] != "SUCCEEDED"


def test_incident_response_refs_require_request_namespace_and_private_delivery_is_hidden(
    situation: dict[str, Any],
) -> None:
    event = observation(situation)
    boundary, request = active_boundary(situation)
    payload = {
        "event_ids": [event],
        "assessment": "Isolated inference.",
        "unknowns": ["Actor unknown."],
    }
    assert (
        boundary.invoke_tool(
            request, "anima.household-learning.record_incident_assessment", payload
        )["status"]
        == "SUCCEEDED"
    )
    own, wrong, foreign = uuid4(), uuid4(), uuid4()
    with psycopg.connect(situation["url"]) as conn:
        for action, household, key, effects in (
            (
                own,
                situation["home"],
                f"{request.idempotency_key}:action:1",
                [{"outcome": "VERIFIED", "source": "PROVIDER_RECEIPT"}],
            ),
            (
                wrong,
                situation["home"],
                f"unrelated-request:{uuid4()}:action:1",
                [{"outcome": "VERIFIED"}],
            ),
            (
                foreign,
                situation["foreign"],
                f"{request.idempotency_key}:action:2",
                [{"outcome": "VERIFIED"}],
            ),
        ):
            conn.execute(
                "INSERT INTO anima_actions(action_id,idempotency_key,request_digest,household_id,"
                "tool_id,arguments,status,result,created_at,updated_at) "
                "VALUES(%s,%s,'isolated',%s,'isolated','{}','SUCCEEDED',%s::jsonb,now(),now())",
                (action, key, household, json.dumps({"effects": effects})),
            )
        conn.execute(
            "UPDATE anima_intelligence_requests SET result_metadata=%s::jsonb, "
            "request_metadata=jsonb_set(request_metadata,'{required_delivery}',%s::jsonb) "
            "WHERE request_id=%s",
            (
                json.dumps({"action_references": list(map(str, (own, wrong, foreign)))}),
                json.dumps(
                    {
                        "state": "DELIVERED",
                        "token_digest": "SECRET_SENTINEL",
                        "client_id": "PRIVATE_BINDING",
                        "lease_until": "PRIVATE_LEASE",
                        "followup": {"state": "UNKNOWN", "token_digest": "FOLLOWUP_SECRET"},
                    }
                ),
                request.request_id,
            ),
        )
    incident = situation["reader"](situation["home"])["incidents"][0]
    assert [item["action_id"] for item in incident["response_ledger"]] == [str(own)]
    assert incident["required_delivery"]["state"] == "DELIVERED"
    assert incident["required_delivery"]["followup"]["state"] == "UNKNOWN"
    assert incident["required_delivery"]["human_receipt"] == "NOT_VERIFIED"
    assert incident["response_ledger"][0]["verification_basis"] == (
        "PROVIDER_RECEIPT_ACCEPTANCE_NOT_HUMAN_RECEIPT"
    )
    assert not any(
        word in json.dumps(incident) for word in ("SECRET", "PRIVATE_BINDING", "PRIVATE_LEASE")
    )


def test_incident_source_scope_stale_and_changed_payload_not_overwritten(
    situation: dict[str, Any],
) -> None:
    event = observation(situation)
    home, request = situation["home"], uuid4()
    service = situation["service"]
    payload = {
        "event_ids": [event],
        "assessment": "Unknown activity; not proof of intrusion.",
        "unknowns": [],
    }
    with learning_request_scope(request, home, [event]):
        first = service.record_incident_assessment(home, payload, request)
        service.set_household_mode(
            home, situation["owner"], {"mode": "HOME", "expected_version": None}
        )
        assert first == service.record_incident_assessment(home, payload, request)
        with pytest.raises(HouseholdLearningError, match="no overwrite"):
            service.record_incident_assessment(home, {**payload, "assessment": "Changed"}, request)
    old = observation(situation, age=601)
    stale_request = uuid4()
    with learning_request_scope(stale_request, home, [old]):
        with pytest.raises(HouseholdLearningError, match="freshness"):
            service.record_incident_assessment(home, {**payload, "event_ids": [old]}, stale_request)


def test_public_delivery_never_projects_credentials_or_process_as_audible() -> None:
    result = public_delivery(
        {
            "state": "DELIVERED",
            "credential_generation": 2,
            "evidence": {
                "playback_state": "DELIVERED",
                "raw": "SECRET",
                "actual_audible_start_at": "not observed",
            },
        }
    )
    assert result["evidence"]["actual_audible_start_at"] is None
    assert "SECRET" not in json.dumps(result) and "credential_generation" not in result


def test_owner_mode_typed_gateway_real_current_policy_no_autonomous_permission(
    situation: dict[str, Any],
) -> None:
    opa = os.environ.get("ANIMA_STAGE3_TEST_OPA_URL")
    if not opa:
        pytest.skip("requires explicit stateless OPA endpoint")
    manager = PluginManager()
    manager.register(
        HOUSEHOLD_LEARNING_MANIFEST,
        NativeRuntime(HouseholdLearningNativePlugin(situation["service"])),
    )
    manager.enable(HOUSEHOLD_LEARNING_MANIFEST.plugin_id)
    role: dict[str, str | None] = {"value": "owner"}
    gateway = CoreUICommandGateway(
        manager,
        PolicyService(OpaPolicyClient(opa), audit_store=PostgresPolicyStore(situation["url"])),
        policy_role_resolver=lambda _: role["value"],
    )
    now = datetime.now(UTC)
    evidence = IdentityEvidence(
        uuid4(),
        situation["home"],
        situation["owner"],
        EvidenceType.AUTHENTICATED_SESSION,
        "isolated-session-fixture",
        now,
        now,
        now + timedelta(minutes=5),
        Assurance.AUTHENTICATED,
        70,
        "ISOLATED_NOT_REAL_OWNER_AUTH",
    )
    identity = UIIdentity(situation["home"], situation["owner"], "isolated", evidence)
    written = gateway.learning_operation(
        identity, "set_household_mode", {"mode": "AWAY", "expected_version": None}
    )
    assert written["status"] == "SUCCEEDED" and written["result"]["status"] == "SUCCEEDED"
    version = situation["service"].declared_mode(situation["home"])["version"]
    stale = gateway.learning_operation(
        identity, "set_household_mode", {"mode": "HOME", "expected_version": None}
    )
    assert stale["status"] == "FAILED"
    role["value"] = None
    denied = gateway.learning_operation(
        identity, "set_household_mode", {"mode": "HOME", "expected_version": version}
    )
    assert denied["status"] == "DENIED"
    assert situation["service"].declared_mode(situation["home"])["mode"] == "AWAY"
    role["value"] = "owner"
    # Actual same-origin/session/CSRF API guards; authentication provider is an
    # explicit isolated fixture, not an owner HA login or real speaker identity.
    ui = UIService(
        config=UIConfig(test_auth_enabled=True),
        commands=gateway,
        ha_user_map={"test-ha-user": (situation["home"], situation["owner"])},
    )
    ui.core_runtime = SimpleNamespace(
        learning_service=situation["service"], graph=situation["graph"]
    )
    client = TestClient(create_app(ui), follow_redirects=False)
    assert client.get("/api/v1/initiative/situation").status_code == 401
    login = client.get("/auth/login")
    callback = client.get(login.headers["location"])
    csrf = callback.headers["x-anima-csrf"]
    context = client.get("/api/v1/initiative/situation")
    assert context.status_code == 200 and context.json()["can_edit"] is True
    payload = {"payload": {"mode": "HOME", "expected_version": version}}
    assert client.post("/api/v1/initiative/set_household_mode", json=payload).status_code == 403
    assert (
        client.post(
            "/api/v1/initiative/set_household_mode",
            json=payload,
            headers={"Origin": "http://testserver"},
        ).status_code
        == 403
    )
    headers = {"Origin": "http://testserver", "X-Anima-CSRF": csrf}
    saved = client.post("/api/v1/initiative/set_household_mode", json=payload, headers=headers)
    assert saved.status_code == 200 and saved.json()["result"]["status"] == "SUCCEEDED"
    stale_response = client.post(
        "/api/v1/initiative/set_household_mode", json=payload, headers=headers
    )
    assert stale_response.status_code == 200 and stale_response.json()["status"] == "FAILED"
