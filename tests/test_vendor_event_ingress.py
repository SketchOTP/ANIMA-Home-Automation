"""Bounded receiver tests; synthetic fixtures never qualify a vendor parser."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from anima_ha.android_notifications import (
    REAL_REPORT_FORMAT,
    SYNTHETIC_FORMAT,
    WANSVIEW_PACKAGE,
    RelayRegistration,
    Transport,
)
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.graph import CanonicalNode, NodeKind
from anima_ha.journal import AppendResult
from anima_ha.tapo_events import TapoLockBinding
from anima_ha.vendor_event_ingress import (
    ExactVendorAttention,
    VendorEventIngress,
    VendorIngressError,
    VendorRelayConfig,
    VendorRelaySource,
    install_vendor_event_api,
)

NOW = datetime(2026, 9, 7, 3, tzinfo=UTC)
TOKEN = "synthetic-relay-credential-for-tests-only"


class Journal:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def append(self, event: EventEnvelope) -> AppendResult:
        with self.lock:
            for index, previous in enumerate(self.events):
                if previous["event_id"] == event.event_id:
                    return AppendResult(event.event_id, index + 1, True)
            self.events.append(event.to_dict())
            return AppendResult(event.event_id, len(self.events), False)

    def list_events(self, *, after_position: int, limit: int) -> list[dict[str, Any]]:
        return self.events[after_position : after_position + limit]


class Graph:
    def __init__(self) -> None:
        self.home = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic home")
        self.camera = CanonicalNode(uuid4(), NodeKind.RESOURCE, "Synthetic camera")
        self.capability = CanonicalNode(uuid4(), NodeKind.CAPABILITY, "Synthetic lock state")
        self.nodes = {self.home.canonical_id: self.home, self.camera.canonical_id: self.camera}
        self.places = [self.home]
        self.members = {self.home.canonical_id: [self.camera]}
        self.placement = [object()]

    def get_node(self, resource: Any) -> Any:
        return self.nodes.get(resource)

    def related(self, *_: Any) -> Any:
        return self.placement

    def list_places(self) -> Any:
        return self.places

    def resources_in_place(self, home: Any) -> Any:
        return self.members.get(home, [])

    def resource_capabilities(self, _: Any) -> Any:
        return [self.capability]


def fixture(
    *,
    synthetic: bool = True,
    enabled: bool = True,
    qualified: bool = False,
    wake: bool = False,
) -> tuple[Any, ...]:
    graph, journal = Graph(), Journal()
    registration = RelayRegistration(
        graph.home.canonical_id,
        uuid4(),
        {"fixture-camera": graph.camera.canonical_id},
        frozenset({"fixture-channel"}),
    )
    source = VendorRelaySource(
        registration,
        TOKEN,
        enabled,
        True,
        True,
        producer_adapter="isolated-test-producer" if qualified else None,
        producer_version="1" if qualified else None,
        producer_qualified=qualified,
        wake_enabled=wake,
    )
    ingress = VendorEventIngress(
        VendorRelayConfig(enabled, (source,)),
        journal=journal,
        graph=graph,
        synthetic_test_mode=synthetic,
        clock=lambda: NOW,
        dispatch=lambda *_: pytest.fail("synthetic notification must never wake SENTRY"),
    )
    app = FastAPI()

    def authenticate(request: Request) -> Any:
        if request.headers.get("x-synthetic-ui") != "authenticated":
            raise HTTPException(401, "AUTHENTICATION_REQUIRED")
        return SimpleNamespace(household_id=graph.home.canonical_id)

    install_vendor_event_api(app, authenticate, lambda: ingress)
    return TestClient(app), ingress, source, journal, graph


def body(*, real: bool = False) -> dict[str, Any]:
    return {
        "package_name": WANSVIEW_PACKAGE,
        "fields": {
            "format": REAL_REPORT_FORMAT if real else SYNTHETIC_FORMAT,
            "delivery_id": str(uuid4()),
            "camera_alias": "fixture-camera",
            "channel_id": "fixture-channel",
            "kind": "motion_reported",
            "android_posted_at": NOW.isoformat(),
            "source_occurred_at": None,
            "relay_received_at": NOW.isoformat(),
            "is_group_summary": False,
            "reported_loss_count": None,
        },
    }


def post(client: TestClient, data: dict[str, Any], **extra: str) -> Any:
    return client.post(
        "/api/v1/vendor-events/receive",
        json=data,
        headers={"Authorization": f"Bearer {TOKEN}", **extra},
    )


def test_defaults_and_production_format_gate_are_not_a_synthetic_loophole() -> None:
    assert VendorRelayConfig.from_environment({}) == VendorRelayConfig()
    client, ingress, _, journal, _ = fixture(synthetic=False)
    result = post(client, body())
    assert result.status_code == 503
    assert result.json() == {"detail": "PRODUCER_UNQUALIFIED"}
    assert not journal.events
    assert ingress.status(uuid4())["configured"] is False
    assert ingress.status(uuid4())["state"] == "WAITING_APP_SETUP"


def test_status_requires_ui_identity_not_relay_token_and_discloses_no_ids() -> None:
    client, ingress, source, _, graph = fixture()
    assert client.get("/api/v1/vendor-events/status").status_code == 401
    assert (
        client.get(
            "/api/v1/vendor-events/status", headers={"Authorization": f"Bearer {TOKEN}"}
        ).status_code
        == 401
    )
    response = client.get(
        "/api/v1/vendor-events/status", headers={"x-synthetic-ui": "authenticated"}
    )
    assert response.status_code == 200
    assert response.json()["state"] == "WAITING_APP_SETUP"
    for private in (
        TOKEN,
        str(source.registration.relay_id),
        str(graph.home.canonical_id),
        str(graph.camera.canonical_id),
    ):
        assert private not in response.text + repr(source) + repr(ingress.config)
    assert "connected" not in response.json()


@pytest.mark.parametrize(
    "header", [None, "Bearer UI-token", "Bearer SENTRY-token", "Basic value", "Bearer 💣"]
)
def test_auth_first_without_parsing_or_logging_body(header: str | None, caplog: Any) -> None:
    client, _, _, journal, _ = fixture()
    headers = {} if header is None else {"authorization": header}
    if header and not header.isascii():
        # HTTPX forbids non-ASCII headers before sending; exercise core check.
        _, ingress, *_ = fixture()
        with pytest.raises(HTTPException) as failure:
            ingress.authenticate_relay(header)
        assert failure.value.status_code == 401
        return
    response = client.post(
        "/api/v1/vendor-events/receive", content=b"PRIVATE_SENTINEL_INVALID_JSON", headers=headers
    )
    assert response.status_code == 401
    assert "PRIVATE_SENTINEL" not in response.text + caplog.text
    assert not journal.events


@pytest.mark.parametrize("extra", [{"Cookie": "session=synthetic"}, {"Origin": "http://localhost"}])
def test_browser_credentials_are_rejected(extra: dict[str, str]) -> None:
    client, _, _, journal, _ = fixture()
    assert post(client, body(), **extra).status_code == 403
    assert not journal.events


def test_payload_bound_before_json_and_no_error_echo(caplog: Any) -> None:
    client, _, _, journal, _ = fixture()
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    response = client.post(
        "/api/v1/vendor-events/receive", content=b"PRIVATE_SENTINEL" * 1000, headers=headers
    )
    assert response.status_code == 413
    response2 = client.post(
        "/api/v1/vendor-events/receive", content=b"PRIVATE_SENTINEL", headers=headers
    )
    assert response2.status_code == 400
    assert "PRIVATE_SENTINEL" not in response.text + response2.text + caplog.text
    assert not journal.events


@pytest.mark.parametrize("case", ["raw", "household", "package", "camera", "summary", "nonmotion"])
def test_rejected_envelopes_never_append(case: str) -> None:
    client, _, _, journal, _ = fixture()
    data = body()
    if case == "raw":
        data["fields"]["body"] = "PRIVATE_SENTINEL"
    elif case == "household":
        data["household_id"] = str(uuid4())
    elif case == "package":
        data["package_name"] = "unrelated.application"
    elif case == "camera":
        data["fields"]["camera_alias"] = "foreign-camera"
    elif case == "summary":
        data["fields"]["is_group_summary"] = True
    else:
        data["fields"]["kind"] = "account_notice"
    response = post(client, data)
    assert response.status_code in {400, 422}
    assert not journal.events
    assert "PRIVATE_SENTINEL" not in response.text


@pytest.mark.parametrize("case", ["foreign", "ambiguous", "retired", "unplaced", "person"])
def test_graph_mapping_is_revalidated_before_append(case: str) -> None:
    client, _, _, journal, graph = fixture()
    if case == "foreign":
        graph.members.clear()
    elif case == "ambiguous":
        foreign = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Foreign")
        graph.places.append(foreign)
        graph.members[foreign.canonical_id] = [graph.camera]
    elif case == "retired":
        graph.nodes[graph.camera.canonical_id] = replace(graph.camera, retired_at=NOW)
    elif case == "unplaced":
        graph.placement.clear()
    else:
        graph.nodes[graph.camera.canonical_id] = replace(graph.camera, kind=NodeKind.PERSON)
    assert post(client, body()).status_code == 409
    assert not journal.events


def test_atomic_delivery_replay_conflict_and_no_synthetic_wake() -> None:
    client, ingress, source, journal, _ = fixture()
    data = body()
    assert post(client, data).json() == {
        "status": "RECORDED",
        "deduplicated": False,
        "attention": "NOT_ELIGIBLE",
    }
    ingress.clock = lambda: NOW + timedelta(seconds=10)
    assert post(client, data).json()["deduplicated"] is True
    data["fields"]["reported_loss_count"] = 2
    assert post(client, data).status_code == 409
    assert len(journal.events) == 1
    assert journal.events[0]["payload"]["reported_loss_count"] is None
    assert journal.events[0]["payload"]["authority"] == "NONE"
    assert ingress.status(source.registration.household_id)["last_receipt_at"] is not None
    # A fresh instance reuses journal identity/digest; no in-memory dedup claim.
    fresh = VendorEventIngress(
        ingress.config,
        journal=journal,
        graph=ingress.graph,
        synthetic_test_mode=True,
        clock=lambda: NOW,
    )
    data["fields"]["reported_loss_count"] = None
    assert fresh.receive(source, data)["deduplicated"] is True


def test_waydroid_receiver_preserves_unknown_android_timestamp() -> None:
    _, ingress, source, journal, _ = fixture()
    source = replace(
        source,
        registration=replace(
            source.registration,
            transport=Transport.WAYDROID_PRIVATE_DBUS,
            allowed_channels=frozenset(),
        ),
    )
    ingress.config = VendorRelayConfig(True, (source,))
    data = body()
    for name in ("android_posted_at", "channel_id", "is_group_summary"):
        data["fields"][name] = None
    assert ingress.receive(source, data)["attention"] == "NOT_ELIGIBLE"
    event = journal.events[0]
    assert event["payload"]["android_posted_at"] is None
    assert event["payload"]["source_occurred_at"] is None
    assert event["payload"]["timestamp_basis"] == "RELAY_RECEIPT_TIME"
    assert event["occurred_at"] == data["fields"]["relay_received_at"]
    assert event["payload"]["report_freshness"] == "UNKNOWN"


def test_concurrent_conflicting_delivery_ids_preserve_first_atomic_winner() -> None:
    _, ingress, source, journal, _ = fixture()
    first = body()
    second = json.loads(json.dumps(first))
    second["fields"]["reported_loss_count"] = 1

    def call(data: dict[str, Any]) -> int:
        try:
            ingress.receive(source, data)
            return 200
        except HTTPException as failure:
            return failure.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(call, [first, second]))
    assert sorted(outcomes) == [200, 409]
    assert len(journal.events) == 1


def test_config_is_private_and_cannot_select_synthetic_mode(tmp_path: Path) -> None:
    _, _, source, _, _ = fixture()
    config: dict[str, Any] = {
        "version": 1,
        "enabled": True,
        "sources": [
            {
                "household_id": str(source.registration.household_id),
                "relay_id": str(source.registration.relay_id),
                "camera_mappings": {
                    key: str(value) for key, value in source.registration.camera_mappings.items()
                },
                "allowed_channels": ["fixture-channel"],
                "token": TOKEN,
                "enabled": True,
                "official_app_ready": True,
                "source_privacy_qualified": True,
            }
        ],
    }
    path = tmp_path / "relay.json"
    path.write_text(json.dumps(config))
    path.chmod(0o600)
    env = {"ANIMA_VENDOR_RELAY_CONFIG": str(path)}
    loaded = VendorRelayConfig.from_environment(env)
    assert loaded.enabled
    assert not loaded.sources[0].producer_qualified and not loaded.sources[0].wake_enabled
    config["version"] = 2
    path.write_text(json.dumps(config))
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment(env)
    config["version"] = 1
    config["sources"][0].update(
        {
            "producer_adapter": "isolated-test-producer",
            "producer_version": "1",
            "producer_qualified": True,
        }
    )
    path.write_text(json.dumps(config))
    loaded = VendorRelayConfig.from_environment(env)
    assert loaded.sources[0].producer_qualified and not loaded.sources[0].wake_enabled
    config["synthetic_test_mode"] = True
    path.write_text(json.dumps(config))
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment(env)
    config.pop("synthetic_test_mode")
    path.write_text(json.dumps(config))
    path.chmod(0o644)
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment(env)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment({"ANIMA_VENDOR_RELAY_CONFIG": str(link)})
    hard = tmp_path / "hard.json"
    os.link(path, hard)
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment(env)


def test_disabled_and_bounded_rate() -> None:
    client, _, _, _, _ = fixture(enabled=False)
    assert post(client, body()).status_code == 503
    _, ingress, *_ = fixture()
    for _ in range(30):
        ingress.authenticate_relay(f"Bearer {TOKEN}")
    with pytest.raises(HTTPException) as failure:
        ingress.authenticate_relay(f"Bearer {TOKEN}")
    assert failure.value.status_code == 429


def test_config_symlink_ancestor_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "real"
    directory.mkdir()
    config = directory / "relay.json"
    config.write_text(json.dumps({"version": 1, "enabled": False, "sources": []}))
    config.chmod(0o600)
    link = tmp_path / "linked"
    link.symlink_to(directory, target_is_directory=True)
    with pytest.raises(VendorIngressError):
        VendorRelayConfig.from_environment({"ANIMA_VENDOR_RELAY_CONFIG": str(link / "relay.json")})


def test_no_runtime_status_and_invalid_config_are_safe_without_database(caplog: Any) -> None:
    app = FastAPI()

    def identity(_: Request) -> Any:
        return SimpleNamespace(household_id=uuid4())

    install_vendor_event_api(app, identity, lambda: None)
    response = TestClient(app).get("/api/v1/vendor-events/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["enabled"] is False
    assert response.json()["state"] == "WAITING_APP_SETUP"
    bad_app = FastAPI()

    def unavailable() -> Any:
        raise ValueError("PRIVATE_PATH_OR_CREDENTIAL_SENTINEL")

    install_vendor_event_api(bad_app, identity, unavailable)
    client = TestClient(bad_app)
    for response in (client.get("/api/v1/vendor-events/status"), post(client, body())):
        assert response.status_code == 503
        assert "PRIVATE_PATH_OR_CREDENTIAL_SENTINEL" not in response.text + caplog.text


def test_existing_ui_service_without_core_exposes_authenticated_disabled_status(
    monkeypatch: Any,
) -> None:
    from anima_ha.ui_api import UIConfig, UIService, create_app

    monkeypatch.delenv("ANIMA_VENDOR_RELAY_CONFIG", raising=False)
    service = UIService(config=UIConfig(test_auth_enabled=True))
    assert service.core_runtime is None
    client = TestClient(create_app(service))
    assert client.get("/api/v1/vendor-events/status").status_code == 401
    client.get("/auth/login")
    response = client.get("/api/v1/vendor-events/status")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["enabled"] is False
    assert response.json()["state"] == "WAITING_APP_SETUP"


def test_tapo_core_callback_records_only_qualified_mapped_cache_observation() -> None:
    _, ingress, _, journal, graph = fixture()
    binding = TapoLockBinding(
        graph.home.canonical_id,
        graph.camera.canonical_id,
        graph.capability.canonical_id,
        uuid4(),
        "lock.fixture",
    )
    state: dict[str, Any] = {
        "entity_id": "lock.fixture",
        "state": "locked",
        "last_updated": NOW.isoformat(),
        "attributes": {"lock_state": "locked", "used_code": "PRIVATE_SENTINEL"},
    }
    kwargs = {
        "binding": binding,
        "ha_instance_id": binding.ha_instance_id,
        "received_at": NOW,
        "snapshot": False,
    }
    with pytest.raises(VendorIngressError):
        ingress.ingest_tapo_state(state, **kwargs)
    result = ingress.ingest_tapo_state(state, source_qualified=True, **kwargs)
    assert result["attention"] == "NOT_ELIGIBLE"
    assert ingress.ingest_tapo_state(state, source_qualified=True, **kwargs)["deduplicated"]
    state["state"] = "unlocked"
    state["attributes"]["lock_state"] = "unlocked"
    with pytest.raises(HTTPException) as failure:
        ingress.ingest_tapo_state(state, source_qualified=True, **kwargs)
    assert failure.value.status_code == 409
    assert "PRIVATE_SENTINEL" not in json.dumps(journal.events)
    assert len(journal.events) == 1


def test_exact_attention_rejects_unqualified_synthetic_and_cache_events() -> None:
    dispatcher = ExactVendorAttention(None, None, None, lambda: [])
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="external.android.motion_reported.synthetic",
        source="android-notification:fixture",
        subject_key="fixture",
        occurred_at=NOW,
        payload={},
        metadata={"synthetic": True},
    )
    with pytest.raises(VendorIngressError):
        dispatcher(event, 1)


def test_exact_attention_uses_single_journal_position_and_source_id(monkeypatch: Any) -> None:
    calls = []

    class Bridge:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def run_once(self, **kwargs: Any) -> list[Any]:
            calls.append(kwargs)
            return ["synthetic-request"]

    monkeypatch.setattr("anima_ha.vendor_event_ingress.SentryAttentionBridge", Bridge)
    primes = []
    attention = SimpleNamespace(prime_consumer_before=lambda *args: primes.append(args))
    household = uuid4()
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="external.android.motion_reported",
        source=f"android-relay-report:{household}:fixture",
        subject_key="fixture",
        occurred_at=NOW,
        payload={},
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={
            "synthetic": False,
            "wake_eligible": True,
            "producer_qualified": True,
            "producer_adapter": "isolated-test-producer",
            "producer_version": "1",
            "schema_qualification": "ANIMA_OWNED_SCHEMA",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "household_id": str(household),
        },
    )
    assert ExactVendorAttention(attention, None, None, lambda: [])(event, 101) == [
        "synthetic-request"
    ]
    assert primes[0][2] == 100
    assert calls[1]["limit"] == 1 and calls[1]["source_event_id"] == event.event_id
    assert "principal_id" not in calls[1]


def test_journal_handoff_retry_uses_real_bridge_and_never_sweeps_backlog() -> None:
    from test_senseguard_attention_dispatch import Context, Store, trigger

    _, ingress, _, journal, graph = fixture()
    household = graph.home.canonical_id
    event = EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="external.android.motion_reported",
        source=f"android-relay-report:{household}:fixture",
        subject_key="fixture",
        occurred_at=NOW,
        payload={"authority": "NONE", "identity_status": "UNKNOWN"},
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={
            "synthetic": False,
            "wake_eligible": True,
            "producer_qualified": True,
            "producer_adapter": "isolated-test-producer",
            "producer_version": "1",
            "schema_qualification": "ANIMA_OWNED_SCHEMA",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "household_id": str(household),
        },
    )
    target = trigger(event.event_id, household)
    foreign = trigger(event.event_id, uuid4())
    backlog = [trigger(str(uuid4()), household) for _ in range(100)]
    primes: list[Any] = []
    attention = SimpleNamespace(
        prime_consumer_before=lambda *args: primes.append(args),
        list_triggers=lambda _: [*backlog, foreign, target],
        process=lambda *args, **kwargs: pytest.fail("retry must reuse exact durable trigger"),
    )
    context, store = Context(), Store()
    dispatcher = ExactVendorAttention(attention, context, store, lambda: [])
    failures = [True]

    def dispatch(candidate: EventEnvelope, position: int) -> list[Any]:
        if failures.pop() if failures else False:
            raise RuntimeError("synthetic failure after append before enqueue")
        return dispatcher(candidate, position)

    ingress.dispatch = dispatch
    with pytest.raises(RuntimeError):
        ingress._record(event, "synthetic-immutable-content")
    assert len(journal.events) == 1 and not store.items
    assert ingress._record(event, "synthetic-immutable-content")["deduplicated"] is True
    assert ingress._record(event, "synthetic-immutable-content")["attention"] == "QUEUED"
    assert len(journal.events) == len(store.items) == len(context.assembled) == 1
    assert context.assembled == [target.trigger_id]
    assert all(item[2] == 0 for item in primes)
    request = next(iter(store.items.values()))
    assert request.principal_id is None and request.causation_id == event.event_id
    before = len(primes)
    with pytest.raises(HTTPException) as failure:
        ingress._record(event, "conflicting-content")
    assert failure.value.status_code == 409 and len(primes) == before


def test_optin_real_postgres_http_append_dedup_conflict_without_truth() -> None:
    import psycopg

    from anima_ha.db.migrate import migrate
    from anima_ha.journal import PostgresEventJournal

    database_url = os.environ.get("ANIMA_VENDOR_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires disposable ANIMA_VENDOR_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_vendor_ingress_test",
        )
    migrate(database_url, 5)
    client, ingress, source, _, _ = fixture(synthetic=False, qualified=True)
    journal = PostgresEventJournal(database_url)
    ingress.journal = journal
    data = body(real=True)

    def counts() -> tuple[int, ...]:
        results: list[int] = []
        with psycopg.connect(database_url) as connection:
            for table in (
                "anima_truth_observations",
                "anima_truth_state",
                "anima_intelligence_requests",
            ):
                row = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
                assert row is not None
                results.append(int(row[0]))
        return tuple(results)

    before = counts()
    ingress.config = VendorRelayConfig(True, (replace(source, producer_qualified=False),))
    assert post(client, data).json() == {"detail": "PRODUCER_UNQUALIFIED"}
    ingress.config = VendorRelayConfig(True, (source,))
    response = post(client, data)
    assert response.status_code == 200
    assert response.json() == {
        "status": "RECORDED",
        "deduplicated": False,
        "attention": "NOT_ELIGIBLE",
    }
    source_name = (
        f"android-relay-report:{source.registration.household_id}:{source.registration.relay_id}"
    )
    records = journal.list_events(source=source_name)
    assert len(records) == 1
    event_id = records[0]["event_id"]
    assert records[0]["metadata"]["synthetic"] is False
    assert records[0]["metadata"]["producer_qualified"] is True
    assert records[0]["metadata"]["wake_eligible"] is False
    assert records[0]["metadata"]["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    assert records[0]["payload"]["authority"] == "NONE"
    assert records[0]["payload"]["source_occurred_at"] is None
    ingress.journal = PostgresEventJournal(database_url)  # Fresh journal instance.
    ingress.clock = lambda: NOW + timedelta(seconds=10)
    assert post(client, data).json()["deduplicated"] is True
    ingress.config = VendorRelayConfig(True, (replace(source, wake_enabled=True),))
    assert post(client, data).json()["attention"] == "NOT_ELIGIBLE"
    assert journal.list_events(source=source_name)[0]["metadata"]["wake_eligible"] is False
    data["fields"]["reported_loss_count"] = 4
    conflict = post(client, data)
    assert conflict.status_code == 409 and conflict.json() == {"detail": "DELIVERY_ID_CONFLICT"}
    remaining = journal.list_events(source=source_name)
    assert len(remaining) == 1 and remaining[0]["event_id"] == event_id
    assert remaining[0]["payload"]["reported_loss_count"] is None
    assert counts() == before  # Recording the qualified report does not create Truth or wake.
    assert TOKEN not in json.dumps(remaining, default=str)


def test_real_protocol_requires_server_qualification_and_has_no_body_override() -> None:
    client, _, _, journal, _ = fixture(synthetic=False)
    data = body(real=True)
    assert post(client, data).json() == {"detail": "PRODUCER_UNQUALIFIED"}
    data["producer_qualified"] = True
    assert post(client, data).status_code == 503
    assert not journal.events
    client, _, _, journal, _ = fixture(synthetic=False, qualified=True)
    assert post(client, data).status_code == 400
    data.pop("producer_qualified")
    data["fields"]["wake_enabled"] = True
    assert post(client, data).status_code == 422
    assert not journal.events


def test_qualified_real_protocol_records_deduplicates_and_status_is_receipt_not_connection() -> (
    None
):
    client, ingress, _, journal, graph = fixture(synthetic=False, qualified=True)
    assert ingress.status(graph.home.canonical_id)["state"] == "READY"
    data = body(real=True)
    assert post(client, data).json() == {
        "status": "RECORDED",
        "deduplicated": False,
        "attention": "NOT_ELIGIBLE",
    }
    assert post(client, data).json()["deduplicated"] is True
    event = journal.events[0]
    assert event["metadata"]["schema_qualification"] == "ANIMA_OWNED_SCHEMA"
    assert "parser_qualification" not in event["metadata"]
    assert event["payload"]["authority"] == "NONE"
    assert event["payload"]["identity_status"] == "UNKNOWN"
    status = ingress.status(graph.home.canonical_id)
    assert status["state"] == "RECEIVED" and status["last_receipt_at"]
    assert "connected" not in status
    assert len(journal.events) == 1


def test_synthetic_and_real_formats_are_not_interchangeable_even_with_wake_enabled() -> None:
    client, _, _, journal, _ = fixture(synthetic=False, qualified=True, wake=True)
    assert post(client, body()).json() == {"detail": "FORMAT_REJECTED"}
    assert not journal.events
    client, _, _, journal, _ = fixture(qualified=True, wake=True)
    assert post(client, body(real=True)).status_code == 422
    assert post(client, body()).json()["attention"] == "NOT_ELIGIBLE"
    assert journal.events[0]["metadata"]["synthetic"] is True


def test_duplicate_never_promotes_persisted_nonwake_and_producer_changes_conflict() -> None:
    client, ingress, source, journal, _ = fixture(synthetic=False, qualified=True)
    data = body(real=True)
    assert post(client, data).status_code == 200
    original = json.loads(json.dumps(journal.events[0]))
    source = replace(source, wake_enabled=True)
    ingress.config = VendorRelayConfig(True, (source,))
    assert post(client, data).json()["attention"] == "NOT_ELIGIBLE"
    assert journal.events[0] == original
    source = replace(source, producer_version="2")
    ingress.config = VendorRelayConfig(True, (source,))
    assert post(client, data).json() == {"detail": "DELIVERY_ID_CONFLICT"}
    source = replace(source, producer_qualified=False, wake_enabled=False)
    ingress.config = VendorRelayConfig(True, (source,))
    assert post(client, data).json() == {"detail": "PRODUCER_UNQUALIFIED"}
    assert journal.events == [original]


def test_explicit_server_wake_dispatches_only_real_report_and_current_revocation_stops_retry() -> (
    None
):
    client, ingress, source, journal, _ = fixture(synthetic=False, qualified=True, wake=True)
    calls = []

    def dispatch(event: EventEnvelope, position: int) -> list[Any]:
        calls.append((event, position))
        return [object()]

    ingress.dispatch = dispatch
    data = body(real=True)
    assert post(client, data).json()["attention"] == "QUEUED"
    event, position = calls[0]
    assert position == 1 and event.delivery_class == DeliveryClass.GUARANTEED
    assert event.metadata["producer_qualified"] is True
    assert event.metadata["synthetic"] is False
    ingress.config = VendorRelayConfig(True, (replace(source, wake_enabled=False),))
    assert post(client, data).json()["attention"] == "NOT_ELIGIBLE"
    assert len(calls) == len(journal.events) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"producer_qualified": True},
        {"wake_enabled": True},
        {"producer_adapter": "../untrusted"},
        {"producer_version": "v1 secret"},
        {"producer_qualified": "true"},
        {"wake_enabled": 1},
    ],
)
def test_invalid_server_producer_configuration_is_rejected(changes: dict[str, Any]) -> None:
    _, _, source, _, _ = fixture()
    with pytest.raises(VendorIngressError):
        replace(source, **changes)
