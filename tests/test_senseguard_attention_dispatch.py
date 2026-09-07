"""Event-scoped SENTRY dispatch must not drain a profile's guaranteed backlog."""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import UTC, datetime, time
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest

from anima_ha.attention import (
    AttentionProfile,
    PostgresAttentionService,
    ReasoningTrigger,
    TriggerStatus,
)
from anima_ha.context import ContextBroker
from anima_ha.db.migrate import migrate
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.intelligence import PostgresIntelligenceStore, SentryAttentionBridge
from anima_ha.journal import PostgresEventJournal
from anima_ha.senseguard_alerts import SenseGuardAlertPolicy, SenseGuardEventRouter
from anima_ha.ui_runtime import _dispatch_senseguard_attention


class Context:
    def __init__(self) -> None:
        self.loaded: list[UUID] = []
        self.assembled: list[UUID] = []
        self.packets: dict[UUID, dict[str, Any]] = {}

    def load(self, trigger_id: UUID) -> dict[str, Any] | None:
        self.loaded.append(trigger_id)
        return self.packets.get(trigger_id)

    def assemble(self, trigger: ReasoningTrigger, **kwargs: Any) -> Any:
        assert str(kwargs["household_id"]) == trigger.metadata["household_id"]
        assert kwargs["persist"] is True
        self.assembled.append(trigger.trigger_id)
        packet = {
            "context_packet_id": str(uuid4()),
            "digest": "synthetic-context",
            "trigger_id": str(trigger.trigger_id),
            "sections": {"trigger": {"items": [{"data": trigger.to_payload()}]}},
        }
        self.packets[trigger.trigger_id] = packet
        return SimpleNamespace(to_payload=lambda: packet)


class Store:
    def __init__(self) -> None:
        self.items: dict[UUID, Any] = {}

    def enqueue(self, request: Any) -> Any:
        return self.items.setdefault(request.request_id, request)


def trigger(event_id: str, household_id: UUID) -> ReasoningTrigger:
    return ReasoningTrigger(
        uuid4(),
        "GUARANTEED_CLASS",
        (event_id,),
        (101, 101),
        (),
        "GUARANTEED_CLASS",
        100,
        datetime.now(UTC),
        "phase13.senseguard.v1",
        metadata={"household_id": str(household_id)},
    )


@pytest.mark.parametrize("status", [TriggerStatus.PENDING, TriggerStatus.CONTEXT_READY])
def test_bridge_filters_before_context_and_preserves_retry_identity(status: TriggerStatus) -> None:
    household_id = uuid4()
    target = replace(trigger("matched-alert", household_id), status=status)
    unrelated = [trigger(f"plugin-health-{index}", household_id) for index in range(100)]
    foreign = trigger("matched-alert", uuid4())
    missing_scope = replace(trigger("matched-alert", household_id), metadata={})
    mixed_sources = replace(target, trigger_id=uuid4(), source_event_ids=("matched-alert", "other"))
    triggers = [*unrelated, foreign, missing_scope, mixed_sources, target]
    processed: list[Any] = []
    attention = SimpleNamespace(
        list_triggers=lambda version: triggers,
        process=lambda *args, **kwargs: processed.append(kwargs),
    )
    context, store = Context(), Store()
    bridge = SentryAttentionBridge(
        attention=attention,
        context=context,
        store=store,  # type: ignore[arg-type]
        profile=AttentionProfile("phase13.senseguard.v1", ()),
    )
    first = bridge.run_once(
        household_id=household_id, tools=[], limit=1, source_event_id="matched-alert"
    )
    second = bridge.run_once(
        household_id=household_id, tools=[], limit=1, source_event_id="matched-alert"
    )
    assert len(first) == 1 and first == second
    assert first[0].causation_id == "matched-alert"
    assert first[0].household_id == household_id
    assert context.loaded == [target.trigger_id, target.trigger_id]
    assert context.assembled == [target.trigger_id]
    assert len(store.items) == 1
    assert (
        processed == []
    )  # Existing target, including restart after append, never advances cursor.


def test_unfiltered_bridge_keeps_global_processing_contract() -> None:
    household_id = uuid4()
    triggers = [trigger("one", household_id), trigger("two", household_id)]
    calls: list[dict[str, Any]] = []

    def process(*args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs)
        return SimpleNamespace(failure=None)

    bridge = SentryAttentionBridge(
        attention=SimpleNamespace(process=process, list_triggers=lambda version: triggers),
        context=Context(),
        store=Store(),  # type: ignore[arg-type]
        profile=AttentionProfile("phase13.senseguard.v1", ()),
    )
    assert len(bridge.run_once(household_id=household_id, tools=[])) == 2
    assert calls == [{"consumer_name": "sentry-attention", "limit": 100}]


@pytest.mark.parametrize("case", ["foreign", "source", "trigger", "missing"])
def test_scoped_bridge_rejects_mismatched_cached_context(case: str) -> None:
    household_id = uuid4()
    target = trigger("matched", household_id)
    context, store = Context(), Store()
    context.assemble(target, household_id=household_id, persist=True)
    packet = context.packets[target.trigger_id]
    data = packet["sections"]["trigger"]["items"][0]["data"]
    if case == "foreign":
        data["metadata"]["household_id"] = str(uuid4())
    elif case == "source":
        data["source_event_ids"] = ["unrelated"]
    elif case == "trigger":
        packet["trigger_id"] = str(uuid4())
    else:
        packet.pop("sections")
    # Keep the trusted trigger independent from the deliberately corrupt packet.
    target = replace(target, metadata={"household_id": str(household_id)})
    bridge = SentryAttentionBridge(
        attention=SimpleNamespace(list_triggers=lambda version: [target]),
        context=context,
        store=store,  # type: ignore[arg-type]
        profile=AttentionProfile("phase13.senseguard.v1", ()),
    )
    with pytest.raises(ValueError, match="context does not match"):
        bridge.run_once(household_id=household_id, tools=[], limit=1, source_event_id="matched")
    assert not store.items


@pytest.mark.parametrize("source_id,limit", [("", 1), ("matched", 100)])
def test_scoped_bridge_rejects_empty_or_unbounded_dispatch(source_id: str, limit: int) -> None:
    bridge = SentryAttentionBridge(attention=None, context=None, store=Store(), profile=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        bridge.run_once(household_id=uuid4(), tools=[], source_event_id=source_id, limit=limit)


def event(household_id: UUID, *, source: str = "anima:senseguard-policy") -> EventEnvelope:
    return EventEnvelope.create(
        event_id=str(uuid4()),
        event_type="senseguard.opened",
        source=source,
        subject_key="senseguard/synthetic",
        occurred_at=datetime(2026, 9, 7, 1, 2, 45, 789328, tzinfo=UTC),
        payload={},
        importance=EventImportance.CRITICAL,
        delivery_class=DeliveryClass.GUARANTEED,
        metadata={"household_id": str(household_id)},
    )


@pytest.mark.parametrize("case", ["foreign", "missing", "not-policy", "not-journaled"])
def test_runtime_dispatch_fails_closed_before_attention(case: str) -> None:
    household_id = uuid4()
    alert = event(uuid4() if case == "foreign" else household_id)
    if case == "missing":
        alert = replace(alert, metadata={})
    if case == "not-policy":
        alert = replace(alert, source="anima:plugin-health")
    with pytest.raises(ValueError):
        _dispatch_senseguard_attention(
            alert=alert,
            journal_position=0 if case == "not-journaled" else 101,
            household_id=household_id,
            attention=None,
            context=None,
            store=None,
            tools=[],
        )


def test_router_scoped_callback_recovers_deduplicated_append_without_legacy_dispatch() -> None:
    household_id, resource_id = uuid4(), uuid4()
    policy = SenseGuardAlertPolicy(
        uuid4(),
        household_id,
        (resource_id,),
        "senseguard.event",
        "UTC",
        time(0),
        time(12),
    )
    source = replace(
        event(household_id),
        event_type="truth.observation",
        metadata={"external_id": "binary_sensor.synthetic"},
    )
    calls: list[Any] = []
    router = SenseGuardEventRouter(
        household_id=household_id,
        policy_store=SimpleNamespace(list_enabled=lambda household: [policy]),  # type: ignore[arg-type]
        resource_resolver=lambda external: resource_id,
        event_sink=SimpleNamespace(
            append=lambda alert: SimpleNamespace(deduplicated=True, journal_position=101)
        ),
        dispatch_attention=lambda: pytest.fail("legacy broad dispatch must not run"),
        dispatch_attention_event=lambda alert, position: calls.append((alert, position)),
    )
    first, second = router.handle(source), router.handle(source)
    assert first[0].event_id == second[0].event_id
    assert calls == [(first[0], 101), (second[0], 101)]
    assert first[0].occurred_at == source.occurred_at


def test_real_postgres_later_alert_never_drains_guaranteed_backlog() -> None:
    database_url = os.environ.get("ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires disposable ANIMA_LATE_BINDING_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_late_binding_test",
        )
    migrate(database_url, 5)
    journal = PostgresEventJournal(database_url)
    attention = PostgresAttentionService(database_url)
    store = PostgresIntelligenceStore(database_url)
    household_id = uuid4()
    profile = AttentionProfile("phase13.senseguard.event.v2", ())
    backlog = [
        replace(event(household_id), event_type="plugin.healthy", source="anima:plugins")
        for _ in range(100)
    ]
    first_position = journal.append(backlog[0]).journal_position
    for item in backlog[1:]:
        journal.append(item)
    old_consumer = f"synthetic-old-global:{household_id}"
    attention.prime_consumer_before(profile, old_consumer, first_position - 1)
    assert attention.process(profile, consumer_name=old_consumer, limit=100).processed == 100
    old_cursor = attention.cursor(old_consumer)
    foreign = event(uuid4())
    foreign_position = journal.append(foreign).journal_position
    foreign_consumer = f"synthetic-foreign:{household_id}"
    attention.prime_consumer_before(profile, foreign_consumer, foreign_position - 1)
    assert attention.process(profile, consumer_name=foreign_consumer, limit=1).processed == 1
    alert = event(household_id)
    position = journal.append(alert).journal_position
    following = journal.append(event(household_id)).journal_position
    context = ContextBroker(database_url)
    for _ in range(2):  # Retry with fresh store/service instances, as after restart.
        _dispatch_senseguard_attention(
            alert=alert,
            journal_position=position,
            household_id=household_id,
            attention=PostgresAttentionService(database_url),
            context=context,
            store=PostgresIntelligenceStore(database_url),
            tools=[],
        )
    consumer = f"senseguard-alert:{household_id}:{alert.event_id}"
    assert attention.cursor(consumer) == position < following
    assert attention.cursor(old_consumer) == old_cursor
    triggers = attention.list_triggers(profile.profile_version)
    matched = [item for item in triggers if item.source_event_ids == (alert.event_id,)]
    assert len(matched) == 1
    packet = context.load(matched[0].trigger_id)
    assert packet is not None
    packet_trigger = packet["sections"]["trigger"]["items"][0]["data"]
    assert packet_trigger["metadata"]["household_id"] == str(household_id)
    assert packet_trigger["source_event_ids"] == [alert.event_id]
    assert (
        packet["sections"]["source_events"]["items"][0]["data"]["occurred_at"]
        == alert.occurred_at.isoformat()
    )
    with store._connect() as connection:
        requests = connection.execute(
            "SELECT * FROM anima_intelligence_requests WHERE household_id = %s", (household_id,)
        ).fetchall()
    assert len(requests) == 1
    assert requests[0]["causation_id"] == alert.event_id
    assert requests[0]["trigger_id"] == matched[0].trigger_id
    assert requests[0]["lifecycle"] == "PENDING"
    persisted = journal.list_events(event_type=alert.event_type, subject_key=alert.subject_key)
    assert (
        next(item for item in persisted if item["event_id"] == alert.event_id)["occurred_at"]
        == alert.occurred_at
    )
