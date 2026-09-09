"""Real isolated PostgreSQL + authenticated Unix HTTP, synthetic Core events only.

No model, production principal, owner event or live activation is exercised.
"""

from __future__ import annotations

import http.client
import json
import os
import secrets
import socket
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest

from anima_ha.attention import AttentionProfile, PostgresAttentionService
from anima_ha.context import ContextBroker
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.intelligence import PostgresIntelligenceStore, SentryAttentionBridge
from anima_ha.journal import PostgresEventJournal
from anima_ha.owner_boundary import OwnerBoundary
from anima_ha.plugins import PluginManager
from anima_ha.sentry_autowake import PostgresAutoWakeClaims
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.sentry_service import (
    CoreSentryHTTPService,
    PostgresSentryPrincipalRegistry,
    SentryServicePrincipal,
    _Handler,
    _UnixHTTPServer,
    read_credential_file,
)

ELIGIBLE = "/v1/provider/requests/eligible"
EXACT = "/v1/provider/claims/exact"


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires disposable routines PostgreSQL fixture")
    with psycopg.connect(url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(url, 5)
    return url


class Harness:
    def __init__(self, url: str, tmp_path: Path, *, owner_core: Any | None = None) -> None:
        self.url = url
        self.home = uuid4()
        self.epoch = datetime.now(UTC) - timedelta(seconds=30)
        self.store = PostgresIntelligenceStore(url)
        self.owner_boundary: OwnerBoundary | None = None
        if owner_core is not None:
            self.owner_boundary = OwnerBoundary(owner_core, self.home, url, tmp_path / "o")
            self.server = self.owner_boundary.server
            self.thread = self.owner_boundary.thread
            self.service = self.server.service
            self.path = str(self.owner_boundary.socket_path)
            self.credential = tmp_path / "o" / "client.token"
            self.token = read_credential_file(str(self.credential))
            assert self.service.service_principal is not None
            self.principal = self.service.service_principal
            return
        self.token = secrets.token_urlsafe(40)
        self.credential = tmp_path / "credential"
        self.credential.write_text(self.token)
        self.credential.chmod(0o600)
        self.principal = SentryServicePrincipal.from_secret(
            client_id=f"synthetic-autowake-{uuid4()}",
            household_id=self.home,
            provider_id="sentry",
            token=self.token,
        )
        registry = PostgresSentryPrincipalRegistry(url)
        registry.register(self.principal)
        self.service = CoreSentryHTTPService(
            CoreSentryBoundary(PluginManager(), None, self.store),
            lambda: read_credential_file(str(self.credential)),
            service_principal=self.principal,
            principal_registry=registry,
            auto_wake_claims=PostgresAutoWakeClaims(url, enabled_at=self.epoch),
        )
        self.path = str(tmp_path / "s")
        self.server = _UnixHTTPServer(self.path, _Handler)  # type: ignore[arg-type]
        self.server.service = self.service
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.owner_boundary is not None:
            self.owner_boundary.close()
            return
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def body(self, **updates: Any) -> dict[str, Any]:
        return {
            "origin": "AUTONOMOUS_ATTENTION",
            "not_before": self.epoch.isoformat(),
            "max_age_seconds": 120,
            **updates,
        }

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        token: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        connection = http.client.HTTPConnection("localhost", timeout=8)
        connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.sock.settimeout(8)
        connection.sock.connect(self.path)
        try:
            connection.request(
                "POST",
                path,
                json.dumps(body),
                {
                    "Authorization": f"Bearer {self.token if token is None else token}",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def claim(self, request_id: UUID, **updates: Any) -> tuple[int, dict[str, Any]]:
        return self.post(
            EXACT,
            self.body(
                request_id=str(request_id),
                worker_id="untrusted-worker-name",
                sentry_request_id=str(uuid4()),
                source_surface="anima_attention",
                **updates,
            ),
        )

    def enqueue(self, *, kind: str = "senseguard", **changes: Any) -> UUID:
        event = EventEnvelope.create(
            event_id=str(uuid4()),
            event_type="senseguard.opened",
            source="anima:senseguard-policy",
            subject_key="synthetic/private",
            occurred_at=datetime.now(UTC) - timedelta(seconds=1),
            delivery_class=DeliveryClass.GUARANTEED,
            payload={"sentinel": "SYNTHETIC_PRIVATE_CONTENT"},
            metadata={
                "household_id": str(self.home),
                "provenance": "anima.senseguard.alert_policy",
                "delivery_mode": "SENTRY_COGNITION",
            },
        )
        if kind == "presence":
            event = replace(
                event,
                source="anima.household_presence",
                event_type="household.presence.connection_changed",
                payload={
                    "household_id": str(self.home),
                    "signal_kind": "ROUTER_WIFI",
                    "transition": "RECONNECTED",
                    "is_authentication": False,
                    "door_actor_verified": False,
                },
            )
        if kind == "vendor":
            event = replace(
                event,
                source=f"android-relay-report:{self.home}:{uuid4()}",
                event_type="external.android.lock_reported",
                payload={
                    "resource_id": str(uuid4()),
                    "event_kind": "unlocked",
                    "authority": "NONE",
                },
                metadata={
                    "household_id": str(self.home),
                    "schema_qualification": "ANIMA_OWNED_SCHEMA",
                    "external_content_trust": "EXTERNAL_UNTRUSTED",
                    "synthetic": False,
                    "producer_qualified": True,
                    "wake_eligible": True,
                },
            )
        event = replace(event, **changes)
        position = PostgresEventJournal(self.url).append(event).journal_position
        profile = AttentionProfile(f"synthetic-autowake-{uuid4()}", ())
        attention = PostgresAttentionService(self.url)
        consumer = f"synthetic-autowake-{uuid4()}"
        attention.prime_consumer_before(profile, consumer, position - 1)
        requests = SentryAttentionBridge(
            attention=attention,
            context=ContextBroker(self.url),
            store=self.store,
            profile=profile,
        ).run_once(
            household_id=self.home,
            tools=[],
            consumer_name=consumer,
            limit=1,
            source_event_id=event.event_id,
        )
        assert len(requests) == 1
        return requests[0].request_id


@pytest.fixture
def harness(database_url: str, tmp_path: Path) -> Iterator[Harness]:
    value = Harness(database_url, tmp_path)
    try:
        yield value
    finally:
        value.close()


@pytest.mark.parametrize("kind", ["senseguard", "presence", "vendor"])
def test_authenticated_exact_claim_actual_journal_attention_and_no_replay(
    harness: Harness,
    kind: str,
) -> None:
    h = harness
    request_id = h.enqueue(kind=kind)
    code, response = h.post(ELIGIBLE, h.body(limit=1))
    assert code == 200 and response["status"] == "AVAILABLE"
    assert len(response["items"]) == 1
    item = response["items"][0]
    assert set(item) == {"request_id", "household_id", "provider_id", "origin", "created_at"}
    assert item["request_id"] == str(request_id)
    assert "SYNTHETIC_PRIVATE_CONTENT" not in json.dumps(response)
    code, result = h.claim(request_id)
    assert code == 200 and result["status"] == "CLAIMED"
    assert result["provider_started"] is False and result["created_at"] == item["created_at"]
    request = h.store.get(request_id)
    assert request is not None and request.claim_owner == h.principal.client_id
    assert request.lifecycle.value == "DELIVERED_TO_PROVIDER"
    assert not request.provider_invocation_started and request.attempt_count == 1
    h.service.bindings.verify(result["binding"], request, h.principal)
    assert h.claim(request_id) == (200, {"status": "EMPTY"})
    assert h.post(ELIGIBLE, h.body()) == (200, {"status": "EMPTY", "items": []})
    with psycopg.connect(h.url) as connection:
        assert connection.execute(
            "SELECT to_lifecycle FROM anima_intelligence_transitions WHERE request_id=%s "
            "AND from_lifecycle IS NOT NULL ORDER BY transition_id",
            (request_id,),
        ).fetchall() == [("CLAIMED",), ("DELIVERED_TO_PROVIDER",)]


@pytest.mark.parametrize(
    "change",
    [
        "origin",
        "household",
        "provider",
        "started",
        "attempt",
        "fence",
        "claimed",
        "unknown",
        "completed",
        "old",
        "principal",
        "context",
        "causation",
    ],
)
def test_ineligible_requests_never_list_or_claim(harness: Harness, change: str) -> None:
    h = harness
    request_id = h.enqueue()
    clauses = {
        "origin": "origin='DIRECT_UI_USER'",
        "household": "household_id='" + str(uuid4()) + "'",
        "provider": "provider_id='diagnostic'",
        "started": "provider_invocation_started=true",
        "attempt": "attempt_count=1",
        "fence": "fencing_generation=1",
        "claimed": "lifecycle='CLAIMED'",
        "unknown": "lifecycle='UNKNOWN_RESULT'",
        "completed": "lifecycle='COMPLETED'",
        "old": "created_at=now()-interval '5 minutes'",
        "principal": "principal_id='" + str(uuid4()) + "'",
        "context": "context_digest='wrong'",
        "causation": "causation_id='unrelated'",
    }
    with psycopg.connect(h.url) as connection:
        connection.execute(
            "UPDATE anima_intelligence_requests SET " + clauses[change] + " WHERE request_id=%s",
            (request_id,),
        )
    before = h.store.get(request_id)
    assert h.post(ELIGIBLE, h.body()) == (200, {"status": "EMPTY", "items": []})
    assert h.claim(request_id) == (200, {"status": "EMPTY"})
    assert h.store.get(request_id) == before


@pytest.mark.parametrize("case", ["source", "type", "provenance", "mode", "old_event"])
def test_event_provenance_and_event_age_not_just_new_request(harness: Harness, case: str) -> None:
    h = harness
    changes: dict[str, Any] = {}
    if case == "source":
        changes["source"] = "anima:diagnostic"
    elif case == "type":
        changes["event_type"] = "plugin.healthy"
    elif case == "old_event":
        changes["occurred_at"] = datetime.now(UTC) - timedelta(minutes=5)
    else:
        changes["metadata"] = {
            "household_id": str(h.home),
            "provenance": "anima.senseguard.alert_policy" if case == "mode" else "synthetic",
            "delivery_mode": "NOTIFICATION" if case == "mode" else "SENTRY_COGNITION",
        }
    request_id = h.enqueue(**changes)
    assert h.post(ELIGIBLE, h.body()) == (200, {"status": "EMPTY", "items": []})
    assert h.claim(request_id) == (200, {"status": "EMPTY"})


def test_concurrent_exact_claim_has_one_winner_and_late_race_rechecks(harness: Harness) -> None:
    h = harness
    request_id = h.enqueue()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: h.claim(request_id), range(8)))
    assert sum(result[1]["status"] == "CLAIMED" for result in results) == 1
    assert sum(result == (200, {"status": "EMPTY"}) for result in results) == 7
    other = h.enqueue()
    assert h.post(ELIGIBLE, h.body())[1]["status"] == "AVAILABLE"
    with psycopg.connect(h.url) as connection:
        connection.execute(
            "UPDATE anima_intelligence_requests SET provider_invocation_started=true "
            "WHERE request_id=%s",
            (other,),
        )
    assert h.claim(other) == (200, {"status": "EMPTY"})


def test_auth_disabled_scope_and_epoch_bounds(harness: Harness) -> None:
    h = harness
    request_id = h.enqueue()
    assert h.post(ELIGIBLE, h.body(), token="invalid")[0] == 401
    assert h.post(EXACT, {"request_id": str(request_id)}, token="invalid")[0] == 401
    for update in (
        {"limit": 11},
        {"limit": True},
        {"max_age_seconds": 121},
        {"origin": "TESTING"},
        {"not_before": "2026-09-07"},
        {"household_id": str(uuid4())},
    ):
        assert h.post(ELIGIBLE, h.body(**update))[0] == 400
    future = datetime.now(UTC) + timedelta(seconds=10)
    assert h.claim(request_id, not_before=future.isoformat()) == (200, {"status": "EMPTY"})
    h.service.auto_wake_claims = PostgresAutoWakeClaims(h.url, enabled_at=future)
    assert h.post(ELIGIBLE, h.body()) == (200, {"status": "EMPTY", "items": []})
    h.service.auto_wake_claims = None
    assert h.post(ELIGIBLE, h.body()) == (200, {"status": "EMPTY", "items": []})
    assert h.claim(request_id) == (200, {"status": "EMPTY"})
    h.service.service_principal = None
    assert h.post(ELIGIBLE, h.body())[0] == 401
    assert h.store.get(request_id).lifecycle.value == "PENDING"  # type: ignore[union-attr]


def test_freshness_independent_of_epoch_and_late_trigger_scope_change(harness: Harness) -> None:
    h = harness
    h.epoch = datetime.now(UTC) - timedelta(hours=1)
    h.service.auto_wake_claims = PostgresAutoWakeClaims(h.url, enabled_at=h.epoch)
    old = h.enqueue(occurred_at=datetime.now(UTC) - timedelta(seconds=121))
    assert h.claim(old) == (200, {"status": "EMPTY"})
    fresh = h.enqueue()
    assert h.post(ELIGIBLE, h.body())[1]["items"][0]["request_id"] == str(fresh)
    with psycopg.connect(h.url) as connection:
        connection.execute(
            "UPDATE anima_reasoning_triggers SET metadata='{}'::jsonb WHERE trigger_id="
            "(SELECT trigger_id FROM anima_intelligence_requests WHERE request_id=%s)",
            (fresh,),
        )
    assert h.claim(fresh) == (200, {"status": "EMPTY"})


def test_revoked_principal_and_credential_rotation_do_not_claim(harness: Harness) -> None:
    h = harness
    request_id = h.enqueue()
    registry = PostgresSentryPrincipalRegistry(h.url)
    registry.register(replace(h.principal, enabled=False))
    assert h.post(ELIGIBLE, h.body())[0] == 401
    assert h.claim(request_id)[0] == 401
    registry.register(h.principal)
    h.credential.write_text(secrets.token_urlsafe(40))
    assert h.claim(request_id)[0] == 401
    assert h.store.get(request_id).attempt_count == 0  # type: ignore[union-attr]


def test_database_failure_is_unavailable_not_empty_or_raw_error(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise psycopg.OperationalError("SYNTHETIC_PRIVATE_DATABASE_ERROR")

    monkeypatch.setattr(PostgresAutoWakeClaims, "eligible", fail)
    assert harness.post(ELIGIBLE, harness.body()) == (503, {"error": "AUTOWAKE_UNAVAILABLE"})
    monkeypatch.setattr(PostgresAutoWakeClaims, "claim", fail)
    assert harness.claim(uuid4()) == (503, {"error": "AUTOWAKE_UNAVAILABLE"})


@pytest.mark.parametrize("configuration", ["missing", "blank", "enabled"])
def test_actual_owner_boundary_core_composition_opt_in_unix_endpoint(
    database_url: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configuration: str,
) -> None:
    from anima_ha.ui_runtime import build_postgres_core

    # Compose production Core only against the supplied disposable database;
    # no inherited HA connection, vault, model invocation or external request.
    monkeypatch.setenv("ANIMA_INTELLIGENCE_PROVIDER", "sentry")
    monkeypatch.setenv("ANIMA_HA_WEBSOCKET_URL", "")
    monkeypatch.setenv("ANIMA_HA_INSTANCE_ID", "")
    monkeypatch.setenv("ANIMA_KNOWLEDGE_ROOT", "")
    monkeypatch.setenv("ANIMA_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("ANIMA_SENTRY_AUTOWAKE_ENABLED_AT", raising=False)
    epoch = datetime.now(UTC) - timedelta(seconds=20)
    if configuration != "missing":
        monkeypatch.setenv(
            "ANIMA_SENTRY_AUTOWAKE_ENABLED_AT",
            epoch.isoformat() if configuration == "enabled" else "  ",
        )
    core = build_postgres_core(
        database_url,
        opa_url=os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_OPA_URL", "http://127.0.0.1:18181"),
    )
    h = Harness(database_url, tmp_path, owner_core=core)
    try:
        request_id = h.enqueue()
        assert h.post(ELIGIBLE, h.body(), token="invalid")[0] == 401
        code, listed = h.post(ELIGIBLE, h.body())
        assert code == 200
        if configuration != "enabled":
            assert h.service.auto_wake_claims is None
            assert listed == {"status": "EMPTY", "items": []}
            assert h.claim(request_id) == (200, {"status": "EMPTY"})
        else:
            assert h.service.auto_wake_claims is not None
            assert h.service.auto_wake_claims.enabled_at == epoch
            assert listed["status"] == "AVAILABLE"
            assert listed["items"][0]["request_id"] == str(request_id)
            # The earlier client epoch cannot override the server epoch.
            old = h.enqueue(occurred_at=epoch - timedelta(seconds=1))
            assert h.claim(old) == (200, {"status": "EMPTY"})
            code, claimed = h.claim(request_id)
            assert code == 200 and claimed["status"] == "CLAIMED"
            assert claimed["provider_started"] is False
            assert h.claim(request_id) == (200, {"status": "EMPTY"})
        assert core.intelligence_store is not None
        persisted = core.intelligence_store.get(request_id)
        assert persisted is not None and not persisted.provider_invocation_started
        assert persisted.attempt_count == (1 if configuration == "enabled" else 0)
    finally:
        h.close()
    assert not h.owner_boundary.socket_path.exists()  # type: ignore[union-attr]
