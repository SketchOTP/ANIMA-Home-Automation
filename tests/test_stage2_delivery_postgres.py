"""Actual isolated PostgreSQL; no owner store, model, or physical actions."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_action import AllowEvaluator, DenyEvaluator
from test_sentry_autowake import Harness

from anima_ha.alert_delivery import PostgresRequiredDelivery, initialize_required_delivery
from anima_ha.attention import AttentionProfile, PostgresAttentionService
from anima_ha.context import ContextBroker
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope
from anima_ha.intelligence import PostgresIntelligenceStore, SentryAttentionBridge
from anima_ha.journal import PostgresEventJournal
from anima_ha.policy import PolicyService
from anima_ha.sentry_voice_settings import SentryVoiceSettingsStore
from anima_ha.ui_runtime import JournalEventWatcher, _dispatch_senseguard_attention
from anima_ha.vendor_event_ingress import ExactVendorAttention


@pytest.fixture(scope="module")
def isolated_url() -> str:
    url = os.environ.get("ANIMA_STAGE2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("requires explicit isolated Stage2 PostgreSQL")
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT current_database(),current_user").fetchone() == (
            "anima_vendor_ingress_test",
            "stage2",
        )
    migrate(url, 5)
    return url


def policy(request: Any) -> dict[str, Any]:
    # No authority claim: test-only canonical disposition, not runtime rules.
    return {
        "allowed": True,
        "required": True,
        "reason": "ALWAYS_NOTIFY",
        "announcement": {
            "event_id": request.causation_id,
            "occurred_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
            "text": "Isolated canonical alert.",
        },
    }


@pytest.fixture
def fixture(isolated_url: str, tmp_path: Path) -> Iterator[Harness]:
    value = Harness(isolated_url, tmp_path)
    value.store.delivery_initializer = lambda request: initialize_required_delivery(
        request, policy(request)
    )
    try:
        yield value
    finally:
        value.close()


def claim(delivery: PostgresRequiredDelivery, home: UUID, **changes: Any) -> dict[str, Any]:
    return delivery.next(
        household_id=home,
        client_id="isolated-client",
        not_before=datetime.now(UTC) - timedelta(seconds=1),
        disposition=policy,
        **changes,
    )


def transition(
    delivery: PostgresRequiredDelivery,
    home: UUID,
    value: dict[str, Any],
    outcome: str,
    **changes: Any,
) -> dict[str, Any]:
    return delivery.transition(
        UUID(value["request_id"]),
        household_id=home,
        client_id="isolated-client",
        token=value["delivery_token"],
        generation=value["generation"],
        outcome=outcome,
        disposition=policy,
        phase=value["phase"],
        **changes,
    )


def test_retained_obligation_outage_new_epoch_and_no_historical_adoption(fixture: Harness) -> None:
    managed = fixture.enqueue()
    fixture.store.delivery_initializer = None
    historical = fixture.enqueue()
    with psycopg.connect(fixture.url) as conn:
        conn.execute(
            "UPDATE anima_intelligence_requests SET created_at=now()-interval '180 seconds' "
            "WHERE request_id IN (%s,%s)",
            (managed, historical),
        )
    delivery = PostgresRequiredDelivery(fixture.url)
    value = claim(delivery, fixture.home)
    assert value["request_id"] == str(managed) and value["predates_enable_epoch"] is True
    assert delivery.state(historical) == {}
    assert delivery.state(managed)["execution_kind"] == "SENTRY_REQUIRED_SPEECH"
    with psycopg.connect(fixture.url) as conn:
        assert conn.execute(
            "SELECT provider_invocation_started FROM anima_intelligence_requests "
            "WHERE request_id=%s",
            (managed,),
        ).fetchone() == (False,)


def test_busy_retry_lost_started_receipt_and_terminal_rows_do_not_starve(fixture: Harness) -> None:
    delivery = PostgresRequiredDelivery(fixture.url)
    for _ in range(34):
        request = fixture.enqueue()
        with psycopg.connect(fixture.url) as conn:
            conn.execute(
                "UPDATE anima_intelligence_requests SET request_metadata=jsonb_set("
                "request_metadata,'{required_delivery,state}','\"DELIVERED\"') "
                "WHERE request_id=%s",
                (request,),
            )
    request = fixture.enqueue()
    value = claim(delivery, fixture.home)
    assert value["request_id"] == str(request)
    assert transition(delivery, fixture.home, value, "UNSTARTED")["delivery_status"] == "PENDING"
    assert claim(delivery, fixture.home)["status"] == "EMPTY"
    future = datetime.now(UTC) + timedelta(seconds=4)
    value = claim(delivery, fixture.home, now=future)
    assert (
        transition(delivery, fixture.home, value, "PLAYBACK_INTENT", now=future)["status"]
        == "RECORDED"
    )
    assert claim(delivery, fixture.home, now=future + timedelta(seconds=61))["status"] == "EMPTY"
    assert delivery.state(request)["state"] == "UNKNOWN"
    another = fixture.enqueue()
    assert claim(delivery, fixture.home)["request_id"] == str(another)
    assert delivery.state(request)["state"] == "UNKNOWN"


def test_expiry_reconciliation_without_worker_and_metadata_preservation(fixture: Harness) -> None:
    request = fixture.enqueue()
    with psycopg.connect(fixture.url) as conn:
        conn.execute(
            "UPDATE anima_intelligence_requests SET created_at=now()-interval '601 seconds', "
            'request_metadata=request_metadata || \'{"concurrent_model_field":"preserved"}\' '
            "WHERE request_id=%s",
            (request,),
        )
    delivery = PostgresRequiredDelivery(fixture.url)
    assert claim(delivery, fixture.home)["status"] == "EMPTY"
    assert delivery.state(request)["state"] == "ESCALATED"
    with psycopg.connect(fixture.url) as conn:
        assert conn.execute(
            "SELECT request_metadata->>'concurrent_model_field' "
            "FROM anima_intelligence_requests WHERE request_id=%s",
            (request,),
        ).fetchone() == ("preserved",)


def test_cancelled_context_request_keeps_explicit_delivery_disposition(fixture: Harness) -> None:
    request = fixture.enqueue()
    with psycopg.connect(fixture.url) as conn:
        conn.execute(
            "UPDATE anima_intelligence_requests SET lifecycle='CANCELLED' WHERE request_id=%s",
            (request,),
        )
    delivery = PostgresRequiredDelivery(fixture.url)
    assert claim(delivery, fixture.home)["status"] == "EMPTY"
    assert delivery.state(request)["state"] == "ESCALATED"
    assert delivery.state(request)["reason"] == "CONTEXT_REQUEST_CANCELLED"


def test_authenticated_current_sleep_instance_opa_and_generation(fixture: Harness) -> None:
    fixture.enqueue()
    delivery = PostgresRequiredDelivery(fixture.url)
    fixture.service.required_delivery = delivery
    boundary = fixture.service.boundary
    boundary.policy_service = PolicyService(AllowEvaluator())
    boundary.notification_context_loader = lambda request: {
        "status": "AVAILABLE",
        "notification": policy(request),
    }
    settings = SentryVoiceSettingsStore(fixture.url)
    fixture.service.voice_settings_store = settings
    settings.update(fixture.home, {"sleep_enabled": False, "active_instance_id": "office"})
    status, denied = fixture.post(
        "/v1/provider/alerts/next",
        fixture.body(active_instance_id="office"),
        token="isolated-invalid",
    )
    assert status == 401
    assert (
        fixture.post("/v1/provider/alerts/next", fixture.body(active_instance_id="living_room"))[1][
            "status"
        ]
        == "EMPTY"
    )
    status, value = fixture.post(
        "/v1/provider/alerts/next", fixture.body(active_instance_id="office")
    )
    assert status == 200 and value["status"] == "CLAIMED"
    receipt = {
        key: value[key]
        for key in (
            "request_id",
            "delivery_token",
            "generation",
            "active_instance_id",
            "phase",
        )
    }
    receipt.update(outcome="PLAYBACK_INTENT", evidence={})
    for key, invalid in [("generation", value["generation"] + 1), ("delivery_token", "rotated")]:
        code, _ = fixture.post("/v1/provider/alerts/receipt", {**receipt, key: invalid})
        assert code != 200
    settings.update(fixture.home, {"sleep_enabled": True, "active_instance_id": "office"})
    assert fixture.post("/v1/provider/alerts/receipt", receipt)[0] != 200
    settings.update(fixture.home, {"sleep_enabled": False, "active_instance_id": "office"})
    boundary.policy_service = PolicyService(DenyEvaluator())
    assert fixture.post("/v1/provider/alerts/receipt", receipt)[0] != 200
    boundary.policy_service = PolicyService(AllowEvaluator())
    assert (
        fixture.post("/v1/provider/alerts/receipt", receipt)[1]["delivery_status"]
        == "PLAYBACK_INTENT"
    )
    assert delivery.state(UUID(value["request_id"]))["state"] == "PLAYBACK_INTENT"


def test_completion_is_not_audible_start_followup_accountable_after_first(fixture: Harness) -> None:
    request = fixture.enqueue()
    delivery = PostgresRequiredDelivery(fixture.url)
    assert delivery.queue_followup(request, "Different useful context.", policy)
    assert not delivery.queue_followup(request, "Another context.", policy)
    following = delivery.state(request)["followup"]
    assert delivery.ready_followup(request, fixture.home, following["response_digest"])
    value = claim(delivery, fixture.home)
    assert value["phase"] == "CANONICAL"
    transition(delivery, fixture.home, value, "PLAYBACK_INTENT")
    with pytest.raises(ValueError, match="COMPLETION_EVIDENCE"):
        transition(
            delivery, fixture.home, value, "DELIVERED", evidence={"playback_state": "STARTED"}
        )
    evidence = {
        "playback_state": "DELIVERED",
        "timing_source": "LOCAL_PLAYBACK_PROCESS",
        "playback_completed_at": datetime.now(UTC).isoformat(),
        "actual_audible_start_at": None,
    }
    transition(delivery, fixture.home, value, "DELIVERED", evidence=evidence)
    assert delivery.state(request)["evidence"]["actual_audible_start_at"] is None
    next_value = claim(delivery, fixture.home)
    assert next_value["phase"] == "FOLLOWUP"
    assert (
        transition(delivery, fixture.home, next_value, "CONTENT_UNAVAILABLE")["delivery_status"]
        == "ESCALATED"
    )


def source_event(home: UUID, kind: str) -> EventEnvelope:
    source, name = {
        "presence": ("anima.household_presence", "household.presence.connection_changed"),
        "ring": ("anima.ring", "household.ring.motion"),
        "senseguard": ("anima:senseguard-policy", "senseguard.opened"),
        "vendor": (f"android-relay-report:{home}:{uuid4()}", "external.android.motion_reported"),
    }[kind]
    return EventEnvelope.create(
        event_id=str(uuid4()),
        source=source,
        event_type=name,
        subject_key="isolated/source",
        occurred_at=datetime.now(UTC) - timedelta(seconds=1),
        delivery_class=DeliveryClass.GUARANTEED,
        payload={},
        metadata={
            "household_id": str(home),
            "synthetic": False,
            "producer_qualified": True,
            "wake_eligible": True,
            "schema_qualification": "ANIMA_OWNED_SCHEMA",
            "producer_adapter": "isolated-qualified",
            "producer_version": "1",
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "delivery_mode": "SENTRY_COGNITION",
            "provenance": "anima.senseguard.alert_policy",
        },
    )


@pytest.mark.parametrize("kind", ["vendor", "ring", "senseguard", "presence"])
def test_actual_journal_interruption_and_after_dispatch_before_cursor_crash(
    isolated_url: str,
    kind: str,
) -> None:
    home = uuid4()
    journal = PostgresEventJournal(isolated_url)
    attention, context, store = (
        PostgresAttentionService(isolated_url),
        ContextBroker(isolated_url),
        PostgresIntelligenceStore(isolated_url),
    )
    succeeded: list[UUID] = []

    def dispatch(event: EventEnvelope, position: int) -> None:
        if kind == "vendor":
            requests = ExactVendorAttention(attention, context, store, lambda: [])(event, position)
        elif kind == "senseguard":
            requests = _dispatch_senseguard_attention(
                alert=event,
                journal_position=position,
                household_id=home,
                attention=attention,
                context=context,
                store=store,
                tools=[],
            )
        else:
            profile = AttentionProfile(f"household.{kind}.event.v1", ())
            consumer = f"household-{kind}:{home}:{event.event_id}"
            attention.prime_consumer_before(profile, consumer, position - 1)
            requests = SentryAttentionBridge(
                attention=attention, context=context, store=store, profile=profile
            ).run_once(
                household_id=home,
                tools=[],
                consumer_name=consumer,
                limit=1,
                source_event_id=event.event_id,
            )
        succeeded.extend(request.request_id for request in requests)

    watcher = JournalEventWatcher(journal, dispatch, home)
    watcher.recover_pending()  # Establish pre-assignment history boundary.
    with psycopg.connect(isolated_url) as conn:
        for index in range(300):
            journal.append(
                EventEnvelope.create(
                    event_id=str(uuid4()),
                    source="isolated.unrelated",
                    event_type=f"unrelated.{index}",
                    subject_key="unrelated",
                    occurred_at=datetime.now(UTC),
                    payload={},
                )
            )
        original = conn.execute(
            "SELECT last_position FROM anima_projection_checkpoints WHERE projection_name=%s",
            (watcher.CHECKPOINT,),
        ).fetchone()
    event = source_event(home, kind)
    position = journal.append(event).journal_position

    def failed_before(event: EventEnvelope, position: int) -> None:
        raise RuntimeError("isolated interruption before handoff")

    watcher.dispatch = failed_before
    with pytest.raises(RuntimeError):
        watcher.recover_pending()
    assert watcher.delivery_state == "HANDOFF_FAILED"
    with psycopg.connect(isolated_url) as conn:
        assert (
            conn.execute(
                "SELECT last_position FROM anima_projection_checkpoints WHERE projection_name=%s",
                (watcher.CHECKPOINT,),
            ).fetchone()
            == original
        )

    def failed_after(event: EventEnvelope, position: int) -> None:
        dispatch(event, position)
        raise RuntimeError("isolated crash after dispatch before cursor")

    watcher.dispatch = failed_after
    with pytest.raises(RuntimeError):
        watcher.recover_pending()
    watcher.dispatch = dispatch
    assert watcher.recover_pending() == 1
    assert watcher.recover_pending() == 0
    with psycopg.connect(isolated_url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM anima_intelligence_requests WHERE "
            "household_id=%s AND causation_id=%s",
            (home, event.event_id),
        ).fetchone() == (1,)
        assert conn.execute(
            "SELECT last_position FROM anima_projection_checkpoints WHERE projection_name=%s",
            (watcher.CHECKPOINT,),
        ).fetchone() == (position,)
    assert len(succeeded) >= 1


def test_new_unhanded_source_expiry_is_durable_not_hidden(isolated_url: str) -> None:
    home = uuid4()
    journal = PostgresEventJournal(isolated_url)
    now = datetime.now(UTC)
    dispatched: list[str] = []
    watcher = JournalEventWatcher(
        journal, lambda event, position: dispatched.append(event.event_id), home, clock=lambda: now
    )
    watcher.recover_pending()
    event = source_event(home, "ring")
    position = journal.append(event).journal_position
    resumed = JournalEventWatcher(
        journal, watcher.dispatch, home, clock=lambda: now + timedelta(seconds=601)
    )
    assert resumed.recover_pending() == 1
    assert dispatched == [] and resumed.delivery_state == "DEGRADED_EXPIRED_HANDOFF"
    with psycopg.connect(isolated_url) as conn:
        assert conn.execute(
            "SELECT last_position,last_error FROM anima_projection_checkpoints "
            "WHERE projection_name=%s",
            (resumed.CHECKPOINT + ":expired:" + event.event_id,),
        ).fetchone() == (
            position,
            "EXPIRED_UNHANDED_REQUIRED_SOURCE",
        )
    assert resumed.recover_pending() == 0
    assert resumed.delivery_state == "DEGRADED_EXPIRED_HANDOFF"
