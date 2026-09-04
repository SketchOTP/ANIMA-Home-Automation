from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from anima_ha.attention import ReasoningTrigger, TriggerStatus
from anima_ha.events import DeliveryClass, EventEnvelope, EventImportance
from anima_ha.intelligence import (
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceRequestFactory,
)
from anima_ha.policy import Assurance, EvidenceType, IdentityEvidence
from anima_ha.ui_api import UIIdentity
from anima_ha.ui_runtime import SentryConversationPipeline


class MemoryIntelligenceStore:
    def __init__(self) -> None:
        self.items: list[IntelligenceRequest] = []

    def enqueue(self, request: IntelligenceRequest) -> IntelligenceRequest:
        for existing in self.items:
            if existing.idempotency_key == request.idempotency_key:
                return existing
        self.items.append(request)
        return request


class Journal:
    def position(self, event_id: str) -> int | None:
        del event_id
        return 1


class Attention:
    def __init__(self, trigger: ReasoningTrigger) -> None:
        self.trigger = trigger

    def prime_consumer_before(self, profile: Any, name: str, position: int) -> None:
        assert profile.profile_version == self.trigger.attention_profile_version
        assert name.startswith("ui-sentry-conversation:")
        assert position == 0

    def process(self, profile: Any, **kwargs: Any) -> SimpleNamespace:
        del profile, kwargs
        return SimpleNamespace(failure=None, processed=1)

    def list_triggers(self, profile_version: str) -> list[ReasoningTrigger]:
        assert profile_version == self.trigger.attention_profile_version
        return [self.trigger]


class Context:
    def __init__(self, packet_id: UUID) -> None:
        self.packet_id = packet_id

    def assemble(self, trigger: Any, **kwargs: Any) -> SimpleNamespace:
        del trigger, kwargs
        return SimpleNamespace(context_packet_id=self.packet_id, digest="context-digest")


def _identity() -> UIIdentity:
    household_id = UUID("00000000-0000-0000-0000-000000000012")
    principal_id = UUID("00000000-0000-0000-0000-000000000013")
    now = datetime.now(UTC)
    return UIIdentity(
        household_id,
        principal_id,
        "sentry-user",
        IdentityEvidence(
            uuid4(),
            household_id,
            principal_id,
            EvidenceType.AUTHENTICATED_SESSION,
            "test",
            now,
            now,
            None,
            Assurance.AUTHENTICATED,
            70,
            "test",
        ),
    )


def test_request_factory_is_stable_and_system_owned() -> None:
    trigger_id = uuid4()
    packet_id = uuid4()
    first = IntelligenceRequestFactory.for_trigger(
        trigger_id,
        household_id=_identity().household_id,
        origin=IntelligenceOrigin.DIRECT_UI_USER,
        context_packet_id=packet_id,
        context_digest="packet",
        tools=[],
        provider_id="sentry",
        provider_version="1",
        principal_id=_identity().principal_id,
    )
    second = IntelligenceRequestFactory.for_trigger(
        trigger_id,
        household_id=first.household_id,
        origin=first.origin,
        context_packet_id=packet_id,
        context_digest="packet",
        tools=[],
        provider_id="sentry",
        provider_version="1",
        principal_id=first.principal_id,
    )
    assert first.request_id == second.request_id
    assert first.idempotency_key == second.idempotency_key
    assert first.origin == IntelligenceOrigin.DIRECT_UI_USER


def test_direct_ui_request_is_queued_for_sentry_after_real_context_step() -> None:
    identity = _identity()
    event_id = str(uuid4())
    trigger = ReasoningTrigger(
        uuid4(),
        "USER_REQUEST",
        (event_id,),
        (1, 1),
        (f"household/{identity.household_id}",),
        "DIRECT_USER_REQUEST",
        90,
        datetime.now(UTC),
        "phase13.sentry.v1",
        event_id,
        TriggerStatus.CONTEXT_READY,
        TriggerStatus.CONTEXT_READY,
    )
    event = EventEnvelope.create(
        event_id=event_id,
        event_type="user.request",
        source="anima.ui",
        subject_key=f"household/{identity.household_id}",
        occurred_at=datetime.now(UTC),
        payload={"text": "Are the sense guards clear?"},
        importance=EventImportance.IMPORTANT,
        delivery_class=DeliveryClass.GUARANTEED,
    )
    store = MemoryIntelligenceStore()
    pipeline = SentryConversationPipeline(
        attention=Attention(trigger),
        context=Context(uuid4()),
        journal=Journal(),
        intelligence=store,
        tools=lambda: [],
    )

    result = pipeline.run(identity, event)

    assert result["disposition"] == "QUEUED_FOR_SENTRY"
    assert len(store.items) == 1
    assert store.items[0].origin == IntelligenceOrigin.DIRECT_UI_USER
    assert store.items[0].principal_id == identity.principal_id
    assert result["trace"]["pipeline"] == "journal_attention_context_sentry_queue"
