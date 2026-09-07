"""Synthetic Ring HA 2026.9 wire/forms and canonical event qualification."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import psycopg
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_home_assistant import FakeReality

from anima_ha.db.migrate import migrate
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
    TargetKind,
)
from anima_ha.home_assistant import HAInstanceConfig, HassClientConnection, HomeAssistantAdapter
from anima_ha.journal import PostgresEventJournal
from anima_ha.ring_api import install_ring_api
from anima_ha.ring_events import RingEventRouter
from anima_ha.ring_setup import RingSetupError, RingSetupService

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
SECRET = "SYNTHETIC_PASSWORD_DO_NOT_PERSIST"


class Fixture:
    def __init__(self) -> None:
        self.home = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic")
        self.owner = CanonicalNode(
            uuid4(), NodeKind.PERSON, "Synthetic", metadata={"semantic_role": "owner"}
        )
        self.cap = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "Synthetic")
        self.resource = CanonicalNode(uuid4(), NodeKind.SENSOR, "PRIVATE_DEVICE_NAME")
        self.instance = uuid4()
        self.entity = "event.synthetic_ring"
        self.ref = ProviderReference(
            uuid4(),
            "home_assistant",
            str(self.instance),
            "entity",
            self.entity,
            self.cap.canonical_id,
            TargetKind.CAPABILITY,
        )
        self.rows: list[dict[str, Any]] = [
            {
                "external_object_kind": "entity",
                "external_id": self.entity,
                "present": True,
                "metadata": {"platform": "ring"},
            }
        ]
        self.graph = SimpleNamespace(
            get_node=lambda value: {
                node.canonical_id: node for node in (self.home, self.owner, self.cap, self.resource)
            }.get(value),
            members_of_household=lambda home: (
                [self.owner] if home == self.home.canonical_id else []
            ),
            resolve_provider_reference=lambda *args: self.cap,
            resolve_provider_references=lambda *args: [self.cap],
            provider_references_for=lambda target: [self.ref],
            resources_in_place=lambda home: (
                [self.resource] if home == self.home.canonical_id else []
            ),
            resource_capabilities=lambda resource: [self.cap],
        )
        self.adapter = HomeAssistantAdapter(
            HAInstanceConfig(
                self.instance, "ws://synthetic.invalid/api/websocket", "TEST", ssl=False
            ),
            cast(Any, FakeReality()),
            cast(Any, self.graph),
            cast(Any, SimpleNamespace(inventory=lambda _: self.rows)),
        )
        self.identity = SimpleNamespace(
            household_id=self.home.canonical_id, principal_id=self.owner.canonical_id
        )
        self.connection = SimpleNamespace(
            connected=True,
            start_config_flow=self.start,
            continue_ring_config_flow=self.continue_flow,
        )
        self.adapter.connection = self.connection
        self.calls: list[Any] = []
        self.result = self.form("user")
        self.events: dict[str, Any] = {}
        self.journal = SimpleNamespace(append=self.append)
        self.dispatched: list[Any] = []
        self.continuity: Any = (True, "epoch", NOW - timedelta(seconds=20))
        self.router = RingEventRouter(
            self.adapter,
            self.home.canonical_id,
            self.journal,
            continuity=lambda: self.continuity,
            dispatch=lambda event, pos: self.dispatched.append((event, pos)),
            now=lambda: NOW,
        )

    def form(self, step: str) -> dict[str, Any]:
        return {
            "type": "form",
            "flow_id": "private-ha-flow",
            "step_id": step,
            "data_schema": [{"name": "password", "default": SECRET}],
            "description_placeholders": {"username": SECRET},
        }

    def start(self, handler: str) -> Any:
        self.calls.append(handler)
        return self.result

    def continue_flow(self, flow_id: str, user_input: Any) -> Any:
        self.calls.append((flow_id, dict(user_input)))
        return self.result

    def append(self, event: Any) -> Any:
        if event.event_id in self.events:
            assert self.events[event.event_id] == event
        self.events.setdefault(event.event_id, event)
        return SimpleNamespace(journal_position=1, deduplicated=False)

    def event(self, kind: str = "ring", *, age: int = 1, snapshot: bool = False) -> Any:
        return self.adapter.normalize_state_event(
            {
                "entity_id": self.entity,
                "state": (NOW - timedelta(seconds=age)).isoformat(),
                "last_updated": NOW.isoformat(),
                "attributes": {
                    "event_type": kind,
                    "video_url": SECRET,
                    "friendly_name": "PRIVATE_DEVICE_NAME",
                    "token": SECRET,
                },
            },
            snapshot=snapshot,
        )


def test_config_flow_owner_projection_two_factor_and_token_result_never_exposed() -> None:
    f = Fixture()
    setup = RingSetupService(f.adapter, f.home.canonical_id)
    first = setup.start(f.identity)
    assert first["status"] == "FORM" and first["step_id"] == "user"
    assert SECRET not in json.dumps(first) and "private-ha-flow" not in json.dumps(first)
    f.result = f.form("2fa")
    second = setup.continue_setup(
        f.identity, first["setup_id"], {"username": "synthetic", "password": SECRET}
    )
    assert second["fields"] == [{"name": "2fa", "type": "password", "required": True}]
    assert SECRET not in repr(setup._flows)
    f.result = {
        "type": "create_entry",
        "title": SECRET,
        "data": {"token": SECRET},
        "result": {"token": SECRET},
    }
    final = setup.continue_setup(f.identity, first["setup_id"], {"2fa": "123456"})
    assert final == {"status": "SUCCEEDED", "configured": True, "refresh_required": True}
    assert not setup._flows
    with pytest.raises(RingSetupError, match="EXPIRED"):
        setup.continue_setup(f.identity, first["setup_id"], {"2fa": "123456"})


@pytest.mark.parametrize(
    "case", ["guest", "foreign", "expired", "connection", "fields", "empty", "oversize"]
)
def test_setup_rejects_before_credential_transport(case: str) -> None:
    f = Fixture()
    setup = RingSetupService(f.adapter, f.home.canonical_id)
    first = setup.start(f.identity)
    identity = f.identity
    fields = {"username": "test", "password": SECRET}
    if case == "guest":
        f.owner = replace(f.owner, metadata={"semantic_role": "guest"})
    elif case == "foreign":
        identity = SimpleNamespace(household_id=uuid4(), principal_id=f.owner.canonical_id)
    elif case == "expired":
        setup._flows[first["setup_id"]].expires = 0
    elif case == "connection":
        f.adapter.connection = SimpleNamespace(connected=True)
    elif case == "fields":
        fields["authority"] = "owner"
    elif case == "empty":
        fields["password"] = ""
    elif case == "oversize":
        fields["password"] = "x" * 1025
    with pytest.raises(RingSetupError):
        setup.continue_setup(identity, first["setup_id"], fields)
    assert f.calls == ["ring"]


@pytest.mark.parametrize("case", ["invalid_auth", "unknown", "unsupported", "abort", "ambiguous"])
def test_safe_flow_errors_never_echo_provider_response(case: str) -> None:
    f = Fixture()
    setup = RingSetupService(f.adapter, f.home.canonical_id)
    first = setup.start(f.identity)
    f.result = {
        **f.form("user"),
        "errors": {"base": "invalid_auth" if case == "invalid_auth" else SECRET},
    }
    if case == "unsupported":
        f.result["step_id"] = SECRET
    elif case == "abort":
        f.result = {"type": "abort", "reason": SECRET}
    elif case == "ambiguous":

        def fail(*args: Any) -> Any:
            raise RuntimeError(SECRET)

        f.connection.continue_ring_config_flow = fail
    try:
        result = setup.continue_setup(
            f.identity, first["setup_id"], {"username": "test", "password": SECRET}
        )
        assert SECRET not in json.dumps(result)
        assert result["status"] in {"FORM", "ABORTED"}
    except RingSetupError as exc:
        assert case in {"unsupported", "ambiguous"} and SECRET not in str(exc)
        assert not setup._flows


def test_real_fastapi_route_auth_csrf_owner_before_bodyparse_and_no_echo() -> None:
    f = Fixture()
    app = FastAPI()

    def identity(request: Any) -> Any:
        if request.headers.get("Authorization") != "synthetic-owner-session":
            raise HTTPException(401, "UNAUTHENTICATED")
        return f.identity

    def mutation(request: Any, csrf: Any, session: Any) -> None:
        if csrf != "synthetic-csrf" or request.headers.get("Origin") != "http://testserver":
            raise HTTPException(403, "CSRF")

    service = SimpleNamespace(
        core_runtime=SimpleNamespace(home_assistant_adapter=f.adapter),
        identity_from_session=lambda session: session,
    )
    install_ring_api(
        app, service, current_identity=identity, current_session=identity, require_mutation=mutation
    )
    client = TestClient(app)
    headers = {
        "Authorization": "synthetic-owner-session",
        "X-Anima-CSRF": "synthetic-csrf",
        "Origin": "http://testserver",
    }
    path = "/api/v1/ring/setup/start"
    assert client.post(path, content=SECRET).status_code == 401
    assert (
        client.post(
            path, headers={"Authorization": "synthetic-owner-session"}, content=SECRET
        ).status_code
        == 403
    )
    first = client.post(path, headers=headers, json={})
    assert first.status_code == 200 and first.json()["status"] == "FORM"
    assert SECRET not in first.text
    f.owner = replace(f.owner, metadata={"semantic_role": "guest"})
    denied = client.post(path, headers=headers, content=SECRET)
    assert denied.status_code == 403 and SECRET not in denied.text
    f.owner = replace(f.owner, metadata={"semantic_role": "owner"})
    invalid = client.post(path, headers=headers, content=SECRET)
    assert invalid.status_code == 400 and SECRET not in invalid.text
    assert client.post(path, headers=headers, content="x" * 4097).status_code == 413


def test_ring_transport_exact_ha_2026_9_form_body_and_path(monkeypatch: pytest.MonkeyPatch) -> None:
    f = Fixture()
    connection = HassClientConnection(
        f.adapter.config,
        "synthetic-ha-token",
        event_callback=lambda event: None,
        disconnect_callback=lambda reason: None,
    )
    calls = []

    async def post(path: str, payload: Any) -> dict[str, Any]:
        calls.append((path, payload))
        return f.form("user")

    monkeypatch.setattr(connection, "_post_config_flow_async", post)
    monkeypatch.setattr(connection, "_submit", lambda awaitable, timeout: asyncio.run(awaitable))
    connection.start_config_flow("ring")
    connection.continue_ring_config_flow(
        "private-ha-flow", {"username": "test", "password": SECRET}
    )
    assert calls == [
        ("/api/config/config_entries/flow", {"handler": "ring"}),
        (
            "/api/config/config_entries/flow/private-ha-flow",
            {"username": "test", "password": SECRET},
        ),
    ]
    with pytest.raises(RuntimeError):
        connection.continue_ring_config_flow("../../arbitrary", {"2fa": "123456"})


@pytest.mark.parametrize(
    "kind,expected",
    [("ring", "doorbell"), ("motion", "motion"), ("intercom_unlock", "intercom_unlock")],
)
def test_actual_ha_normalizer_ring_events_only_canonical_payload(kind: str, expected: str) -> None:
    f = Fixture()
    event = f.event(kind)
    assert f.router.handle(event)
    derived = next(iter(f.events.values()))
    assert derived.event_type == "household.ring." + expected and derived.source == "anima.ring"
    assert derived.occurred_at == NOW - timedelta(seconds=1) and derived.recorded_at == NOW
    assert derived.payload["physical_occurred_at"] is None
    assert derived.payload["time_basis"] == "HA_EVENT_RECEIVED"
    for value in (SECRET, f.entity, "PRIVATE_DEVICE_NAME", "video_url"):
        assert value not in json.dumps(asdict(derived), default=str)
    assert f.router.handle(event) == []
    assert len(f.events) == len(f.dispatched) == 1


@pytest.mark.parametrize(
    "case",
    [
        "snapshot",
        "stale",
        "future",
        "platform",
        "disabled",
        "legacy",
        "foreign",
        "scope",
        "offline",
        "reconnect",
    ],
)
def test_event_gates_no_fabricated_edges(case: str) -> None:
    f = Fixture()
    event = f.event(
        snapshot=case == "snapshot", age=121 if case == "stale" else -1 if case == "future" else 1
    )
    if case == "platform":
        f.rows[0]["metadata"]["platform"] = "not_ring"
    elif case == "disabled":
        f.rows[0]["metadata"]["disabled_by"] = "user"
    elif case == "legacy":
        event = replace(event, metadata={**event.metadata, "external_id": "binary_sensor.ring"})
    elif case == "foreign":
        f.router.household_id = uuid4()
    elif case == "scope":
        event = replace(event, source="provider:home_assistant:foreign")
    elif case == "offline":
        f.continuity = (False, "epoch", NOW)
    elif case == "reconnect":
        f.continuity = (True, "new-epoch", NOW)
    assert f.router.handle(event) == [] and not f.events and not f.dispatched


def test_dispatch_retry_reuses_envelope_without_duplicate_inference() -> None:
    f = Fixture()

    def fail(*args: Any) -> None:
        raise RuntimeError("synthetic dispatch failure")

    f.router.dispatch = fail
    event = f.event()
    with pytest.raises(RuntimeError):
        f.router.handle(event)
    original = next(iter(f.events.values()))
    f.router.now = lambda: NOW + timedelta(seconds=1)
    f.router.dispatch = lambda event, pos: f.dispatched.append((event, pos))
    assert f.router.handle(event) == [original.event_id]
    assert f.dispatched == [(original, 1)] and len(f.events) == 1


def test_real_postgres_canonical_mapping_journal_and_duplicate() -> None:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable routines PostgreSQL fixture")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    f = Fixture()
    graph = PostgresHouseholdGraph(url)
    graph.commission(
        CommissioningDocument(
            1,
            (f.home, f.owner, f.resource, f.cap),
            tuple(
                CanonicalRelationship(uuid4(), kind, source.canonical_id, target.canonical_id)
                for kind, source, target in (
                    (RelationshipType.MEMBER_OF, f.owner, f.home),
                    (RelationshipType.INSTALLED_IN, f.resource, f.home),
                    (RelationshipType.EXPOSES, f.resource, f.cap),
                )
            ),
            provider_references=(f.ref,),
        )
    )
    f.adapter.graph = graph
    f.router.journal = PostgresEventJournal(url)
    event = f.event()
    ids = f.router.handle(event)
    assert len(ids) == 1 and f.router.handle(event) == []
    with psycopg.connect(url) as connection:
        rows = connection.execute(
            "SELECT event_type,source,payload FROM anima_event_journal WHERE event_id=%s", (ids[0],)
        ).fetchall()
    assert len(rows) == 1 and rows[0][:2] == ("household.ring.doorbell", "anima.ring")
    assert rows[0][2]["resource_id"] == str(f.resource.canonical_id)
    assert SECRET not in json.dumps(rows[0][2])


def test_status_has_no_cloud_delivery_or_video_claim_and_honest_empty() -> None:
    f = Fixture()
    setup = RingSetupService(f.adapter, f.home.canonical_id)
    status = setup.status(f.identity)
    assert status["can_edit"] and status["configured"] and status["event_entities"] == 1
    assert status["connection_basis"] == "HA_TRANSPORT"
    assert status["event_receipt_verified"] is False and status["video_access"] is False
    assert f.entity not in json.dumps(status)
    f.rows.clear()
    assert setup.status(f.identity)["state"] == "WAITING_RING_SETUP"
    f.connection.connected = False
    assert setup.status(f.identity)["state"] == "HA_UNAVAILABLE"
    assert (
        RingSetupService(None, f.home.canonical_id).status(f.identity)["state"]
        == "WAITING_HA_SETUP"
    )


@pytest.mark.parametrize("case", ["retired_reference", "retired_household", "malformed_kind"])
def test_event_fails_closed_for_retirement_or_malformed_kind(case: str) -> None:
    f = Fixture()
    event = f.event()
    if case == "retired_reference":
        f.ref = replace(f.ref, retired_at=NOW)
    elif case == "retired_household":
        f.home = replace(f.home, retired_at=NOW)
    else:
        event.payload["metadata"]["attributes"]["event_type"] = {"instruction": "ignore"}
    assert f.router.handle(event) == []
    assert not f.dispatched and not f.events
