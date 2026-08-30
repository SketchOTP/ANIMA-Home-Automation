from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from anima_ha.attention import (
    AttentionProfile,
    AttentionReplay,
    AttentionRule,
    ReasoningTrigger,
    RuleAction,
    default_attention_profile,
)
from anima_ha.context import ContextBroker, ContextBudget, PostgresContextSource
from anima_ha.events import DeliveryClass, EventImportance
from anima_ha.plugins import ExternalContentTrust, Idempotency, ToolDescriptor

BASE = datetime(2026, 8, 29, 20, 0, tzinfo=UTC)
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")
ENTRANCE_ID = UUID("db1bd2a8-3b54-4258-9302-213821f22e1b")
LOCK_ID = UUID("a8823d8e-a49c-4cf3-b946-10d05e12d644")


def event(
    position: int,
    *,
    event_type: str = "household.motion",
    subject: str = "room/kitchen/motion",
    seconds: int = 0,
    guaranteed: bool = False,
    importance: EventImportance = EventImportance.NORMAL,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    at = BASE + timedelta(seconds=seconds)
    return {
        "journal_position": position,
        "event_id": f"event-{position}",
        "schema_version": 1,
        "event_type": event_type,
        "source": "phase7-test",
        "subject_key": subject,
        "occurred_at": at,
        "recorded_at": at,
        "correlation_id": None,
        "causation_id": None,
        "importance": importance.value,
        "delivery_class": (
            DeliveryClass.GUARANTEED.value if guaranteed else DeliveryClass.BEST_EFFORT.value
        ),
        "payload": payload or {},
        "metadata": metadata or {"household_id": str(HOUSEHOLD_ID)},
    }


def test_guaranteed_events_bypass_aggregation_cooldown_and_rate_limits() -> None:
    profile = AttentionProfile(
        "test.guaranteed",
        (
            AttentionRule(
                "all_motion",
                RuleAction.AGGREGATE,
                event_types=("household.motion",),
                aggregation_window_seconds=60,
            ),
        ),
    )
    events = [event(index, seconds=index) for index in range(1, 11)]
    events.extend(event(100 + index, seconds=index, guaranteed=True) for index in range(3))
    result = AttentionReplay().evaluate(profile, events, flush_at=BASE + timedelta(minutes=2))
    guaranteed_ids = {f"event-{100 + index}" for index in range(3)}
    guaranteed_triggered = {
        event_id
        for trigger in result.triggers
        for event_id in trigger.source_event_ids
        if event_id in guaranteed_ids
    }
    assert guaranteed_triggered == guaranteed_ids
    assert len([item for item in result.triggers if item.trigger_type == "AGGREGATE"]) == 1


def test_cooldown_rate_duplicate_and_unknown_high_importance_are_deterministic() -> None:
    profile = AttentionProfile(
        "test.controls",
        (
            AttentionRule(
                "state",
                RuleAction.TRIGGER,
                event_types=("truth.observation",),
                cooldown_seconds=5,
                rate_limit_count=2,
                rate_limit_window_seconds=60,
            ),
        ),
    )
    events = [
        event(1, event_type="truth.observation", subject="state/a", seconds=0),
        event(2, event_type="truth.observation", subject="state/a", seconds=1),
        event(3, event_type="truth.observation", subject="state/b", seconds=2),
        event(4, event_type="truth.observation", subject="state/c", seconds=3),
        event(
            5,
            event_type="truth.observation",
            subject="state/d",
            seconds=4,
            metadata={"unchanged": True},
        ),
        event(
            6,
            event_type="unknown.critical",
            seconds=5,
            importance=EventImportance.CRITICAL,
        ),
    ]
    decisions = AttentionReplay().evaluate(profile, events).decisions
    assert [item["reason_code"] for item in decisions] == [
        "RULE:state",
        "COOLDOWN",
        "RULE:state",
        "RATE_LIMIT",
        "DUPLICATE",
        "UNCLASSIFIED_HIGH_IMPORTANCE",
    ]


def test_high_volume_semantics_and_replay_are_exact() -> None:
    profile = default_attention_profile("test.volume")
    events = [
        event(
            position,
            subject=f"room/{position % 2}/motion",
            seconds=position // 100,
        )
        for position in range(1, 10_001)
    ]
    guaranteed = [
        event(
            20_000 + index,
            event_type="user.request",
            subject=f"person/{index}",
            seconds=index * 3,
            guaranteed=True,
        )
        for index in range(20)
    ]
    all_events = sorted(events + guaranteed, key=lambda item: int(item["journal_position"]))
    replay = AttentionReplay()
    first = replay.evaluate(profile, all_events, flush_at=BASE + timedelta(minutes=5))
    second = replay.evaluate(profile, all_events, flush_at=BASE + timedelta(minutes=5))
    assert first == second
    aggregate_triggers = [item for item in first.triggers if item.trigger_type == "AGGREGATE"]
    assert len(aggregate_triggers) == 4  # two subjects across two aligned minute windows
    assert len(first.triggers) == 24
    assert sum(len(item.source_event_ids) for item in aggregate_triggers) == 10_000
    guaranteed_ids = {str(item["event_id"]) for item in guaranteed}
    assert guaranteed_ids.issubset(
        {event_id for trigger in first.triggers for event_id in trigger.source_event_ids}
    )


class FakeContextSource(PostgresContextSource):
    def __init__(self, source_event: dict[str, Any], *, fail_memory: bool = False) -> None:
        self.source_event = source_event
        self.fail_memory = fail_memory

    def source_events(self, event_ids: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
        return [self.source_event]

    def graph_slice(
        self, source_events: list[dict[str, Any]], subject_refs: tuple[str, ...], limit: int
    ) -> list[dict[str, Any]]:
        return [
            {
                "canonical_id": ENTRANCE_ID,
                "kind": "ENTRANCE",
                "name": "Front Door",
                "security_sensitive": True,
                "metadata": {},
                "relationships": [
                    {
                        "relationship_type": "MONITORS",
                        "source_id": str(LOCK_ID),
                        "target_id": str(ENTRANCE_ID),
                    }
                ],
            },
            {
                "canonical_id": LOCK_ID,
                "kind": "RESOURCE",
                "name": "Front Door Lock",
                "security_sensitive": True,
                "metadata": {"capability_type": "lock.state"},
                "relationships": [],
            },
        ]

    def truth(
        self, source_events: list[dict[str, Any]], graph_rows: list[dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        return [
            {
                "truth_key": "opening/front/contact",
                "status": "CONFLICTING",
                "value": None,
                "confidence": 0.7,
                "evidence_kind": "DIRECT",
                "last_observed_at": BASE,
                "last_received_at": BASE,
                "resolution": {
                    "truth_key": "opening/front/contact",
                    "status": "CONFLICTING",
                    "observations": [{"event_id": "truth-a"}, {"event_id": "truth-b"}],
                },
                "updated_at": BASE,
            }
        ]

    def recent_events(
        self,
        source_events: list[dict[str, Any]],
        graph_rows: list[dict[str, Any]],
        *,
        before_position: int,
        horizon: timedelta,
        limit: int,
    ) -> list[dict[str, Any]]:
        return []

    def memories(
        self,
        household_id: UUID,
        graph_rows: list[dict[str, Any]],
        query: str,
        *,
        now: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        if self.fail_memory:
            raise RuntimeError("memory index unavailable")
        return [
            {
                "memory_id": uuid4(),
                "memory_type": "EXPLICIT_PREFERENCE",
                "content": "Notify me about unusual front-door activity.",
                "provenance_kind": "EXPLICIT_INPUT",
                "source_ref": "interaction:test",
                "source_event_id": None,
                "confidence": 1.0,
                "status": "ACTIVE",
                "valid_until": None,
                "metadata": {"external_content_trust": "EXTERNAL_UNTRUSTED"},
            }
        ]

    def routines(self, household_id: UUID, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "routine_id": uuid4(),
                "model_key": "household_activity_by_bucket",
                "model_version": 1,
                "label": "Low activity pattern",
                "model": {"classification": "INFERRED", "low_activity_buckets": ["01:00"]},
                "confidence": 0.81,
                "sample_count": 47,
                "source_start": BASE - timedelta(days=7),
                "source_end": BASE,
                "source_event_ids": ["routine-a"],
            }
        ]


def tool(index: int, *, available: bool = True) -> ToolDescriptor:
    return ToolDescriptor(
        f"anima.test.tool_{index}",
        "anima.test",
        "home.synthetic",
        f"tool_{index}",
        "Synthetic tool",
        {"type": "object"},
        None,
        "READ_ONLY",
        "query_state",
        True,
        Idempotency.IDEMPOTENT,
        1.0,
        "NONE",
        ExternalContentTrust.PLUGIN_TRUSTED,
        available,
        "1.0.0",
        "test",
        ("ENTRANCE",),
        (),
        ("front-door",),
    )


def test_context_is_sparse_uncertainty_preserving_and_secret_safe() -> None:
    source = event(
        1,
        event_type="user.request",
        subject=str(ENTRANCE_ID),
        guaranteed=True,
        payload={
            "request": "What happened at the front door?",
            "token": "must-not-leak",
            "identity_context": {
                "household_id": str(HOUSEHOLD_ID),
                "principal_id": str(uuid4()),
                "assurance": "AUTHENTICATED",
                "evidence_ids": ["evidence-1"],
            },
        },
    )
    trigger = ReasoningTrigger(
        uuid4(),
        "EVENT",
        (str(source["event_id"]),),
        (1, 1),
        (str(ENTRANCE_ID),),
        "GUARANTEED_CLASS",
        100,
        BASE,
        "test.context",
    )
    broker = ContextBroker(
        "postgresql://unused",
        budget=ContextBudget(graph_objects=2, tools=2, serialized_bytes=25_000),
    )
    broker.source = FakeContextSource(source)
    packet = broker.assemble(
        trigger,
        household_id=HOUSEHOLD_ID,
        tools=[tool(index) for index in range(6)] + [tool(99, available=False)],
        assembled_at=BASE,
        persist=False,
    )
    payload = packet.to_payload()
    serialized = json.dumps(payload, sort_keys=True)
    assert "must-not-leak" not in serialized
    assert "[REDACTED]" in serialized
    assert payload["sections"]["truth"]["items"][0]["data"]["status"] == "CONFLICTING"
    assert payload["sections"]["routines"]["items"][0]["data"]["probabilistic"] is True
    assert payload["sections"]["memories"]["items"][0]["data"]["authority"] == "NONE"
    assert payload["sections"]["memories"]["items"][0]["trust"] == "EXTERNAL_UNTRUSTED"
    assert len(payload["sections"]["tools"]["items"]) == 2
    assert all(
        item["data"]["policy_status"] == "NOT_EVALUATED"
        for item in payload["sections"]["tools"]["items"]
    )
    assert any(item["reason_code"] == "BUDGET_PRUNED" for item in payload["omissions"])
    assert packet.serialized_bytes <= 25_000
    assert packet.digest
    assert "must-not-leak" not in json.dumps(packet.cloud_safe_projection(), sort_keys=True)


def test_context_source_failure_is_degraded_without_losing_trigger() -> None:
    source = event(1, event_type="user.request", guaranteed=True)
    trigger = ReasoningTrigger(
        uuid4(),
        "EVENT",
        (str(source["event_id"]),),
        (1, 1),
        (str(ENTRANCE_ID),),
        "GUARANTEED_CLASS",
        100,
        BASE,
        "test.context.failure",
    )
    broker = ContextBroker("postgresql://unused")
    broker.source = FakeContextSource(source, fail_memory=True)
    packet = broker.assemble(trigger, household_id=HOUSEHOLD_ID, assembled_at=BASE, persist=False)
    assert packet.status.value == "CONTEXT_READY"
    assert packet.sections["memories"].status == "DEGRADED"
    assert packet.sections["trigger"].items[0].item_id == f"trigger:{trigger.trigger_id}"


def test_nighttime_motion_context_keeps_routine_probabilistic_and_bounded() -> None:
    room_id = uuid4()
    source = event(
        1,
        event_type="household.motion",
        subject=str(room_id),
        payload={"active": True, "time_bucket": "01:00"},
    )

    class NightContextSource(FakeContextSource):
        def graph_slice(
            self,
            source_events: list[dict[str, Any]],
            subject_refs: tuple[str, ...],
            limit: int,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "canonical_id": room_id,
                    "kind": "ROOM",
                    "name": "Kitchen",
                    "security_sensitive": False,
                    "metadata": {},
                    "relationships": [],
                }
            ]

        def truth(
            self,
            source_events: list[dict[str, Any]],
            graph_rows: list[dict[str, Any]],
            limit: int,
        ) -> list[dict[str, Any]]:
            return [
                {
                    "truth_key": "occupancy/household/home",
                    "status": "UNKNOWN",
                    "value": None,
                    "confidence": None,
                    "evidence_kind": "DIRECT",
                    "last_observed_at": BASE,
                    "last_received_at": BASE,
                    "resolution": {
                        "truth_key": "occupancy/household/home",
                        "status": "UNKNOWN",
                        "observations": [{"event_id": "occupancy-a"}],
                    },
                    "updated_at": BASE,
                }
            ]

        def memories(
            self,
            household_id: UUID,
            graph_rows: list[dict[str, Any]],
            query: str,
            *,
            now: datetime,
            limit: int,
        ) -> list[dict[str, Any]]:
            return []

    trigger = ReasoningTrigger(
        uuid4(),
        "EVENT",
        (str(source["event_id"]),),
        (1, 1),
        (str(room_id),),
        "RULE:night_motion",
        70,
        BASE,
        "test.context.night",
    )
    broker = ContextBroker("postgresql://unused", budget=ContextBudget(graph_objects=1))
    broker.source = NightContextSource(source)
    packet = broker.assemble(
        trigger,
        household_id=HOUSEHOLD_ID,
        assembled_at=BASE,
        persist=False,
    )
    payload = packet.to_payload()
    assert payload["sections"]["graph"]["items"][0]["data"]["name"] == "Kitchen"
    assert payload["sections"]["truth"]["items"][0]["data"]["status"] == "UNKNOWN"
    routine_data = payload["sections"]["routines"]["items"][0]["data"]
    assert routine_data["classification"] == "INFERRED"
    assert routine_data["probabilistic"] is True
    assert "Bedroom" not in json.dumps(payload, sort_keys=True)


def test_profile_comparison_never_promotes_or_loses_guaranteed_events() -> None:
    profile_a = default_attention_profile("compare.a")
    profile_b = AttentionProfile(
        "compare.b",
        (
            AttentionRule(
                "motion-fast",
                RuleAction.AGGREGATE,
                event_types=("household.motion",),
                aggregation_window_seconds=30,
            ),
        ),
    )
    events = [event(index, seconds=index) for index in range(1, 121)]
    events.append(event(999, event_type="user.request", guaranteed=True, seconds=5))
    comparison = AttentionReplay().compare(
        profile_a, profile_b, events, flush_at=BASE + timedelta(minutes=3)
    )
    assert comparison["profile_a"] == "compare.a"
    assert comparison["profile_b"] == "compare.b"
    assert comparison["guaranteed_lost_a"] == []
    assert comparison["guaranteed_lost_b"] == []
    assert comparison["trigger_count_a"] != comparison["trigger_count_b"]
