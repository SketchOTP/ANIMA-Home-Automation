"""Bounded PostgreSQL evidence for governed memory and deterministic routines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from anima_ha.events import EventEnvelope, EvidenceKind, ObservationState, TruthObservation
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.journal import PostgresRealityStore
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryService,
    MemoryStatus,
    MemoryType,
    ProvenanceKind,
    RetrievalMode,
)
from anima_ha.routines import RoutineService

DATABASE_URL = "postgresql://anima:anima_dev_only@localhost:55432/anima"


def make_memory(
    household_id: UUID,
    memory_type: MemoryType,
    content: str,
    source: str,
    *,
    now: datetime,
    subject_id: UUID | None = None,
    graph_refs: tuple[UUID, ...] = (),
    expires_at: datetime | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> MemoryRecord:
    return MemoryRecord.create(
        household_id=household_id,
        subject_id=subject_id,
        memory_type=memory_type,
        content=content,
        provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, source),
        created_at=now,
        graph_refs=graph_refs,
        expires_at=expires_at,
        valid_from=valid_from,
        valid_until=valid_until,
    )


def routine_event(
    household_id: UUID, event_id: str, active: bool, bucket: str, at: datetime
) -> EventEnvelope:
    return EventEnvelope.create(
        event_id=event_id,
        event_type="routine.activity_observation",
        source="phase3-simulator",
        subject_key=f"routine/household/{household_id}",
        occurred_at=at,
        recorded_at=at + timedelta(seconds=1),
        payload={"active": active, "bucket": bucket},
        source_event_id=event_id,
    )


def main() -> int:
    now = datetime.now(UTC).replace(microsecond=0)
    graph = PostgresHouseholdGraph(DATABASE_URL)
    graph.commission(sample_household_document())
    document = sample_household_document()
    # Use a fresh namespace so repeated evidence runs do not depend on prior
    # synthetic memory records.
    household_id = uuid4()
    alex_id = next(node.canonical_id for node in document.nodes if node.name == "Alex")
    office_id = next(node.canonical_id for node in document.nodes if node.name == "Office")
    service = MemoryService(DATABASE_URL)

    preference = service.create(
        make_memory(
            household_id,
            MemoryType.EXPLICIT_PREFERENCE,
            "Notify us about unusual overnight movement.",
            "interaction:preference",
            now=now,
            subject_id=alex_id,
            graph_refs=(office_id,),
        )
    )
    inferred = service.create(
        MemoryRecord.create(
            household_id=household_id,
            memory_type=MemoryType.INFERRED_PATTERN,
            content="Household activity is usually low overnight.",
            provenance=MemoryProvenance(ProvenanceKind.INFERRED_FROM_HISTORY, "routine:model:v1"),
            created_at=now,
            confidence=0.81,
        )
    )
    temporary = service.create(
        make_memory(
            household_id,
            MemoryType.TEMPORARY_EPISODIC,
            "The household is staying up late tonight.",
            "interaction:temporary",
            now=now,
            valid_from=now - timedelta(minutes=1),
            valid_until=now + timedelta(hours=4),
            expires_at=now + timedelta(hours=4),
        )
    )
    relevant = service.retrieve("overnight", household_id=household_id, top_k=2, now=now)
    assert relevant[0].memory.memory_id == preference.memory_id
    assert relevant[0].precedence_rank > relevant[1].precedence_rank
    assert relevant[0].memory.provenance.source_ref == "interaction:preference"
    temporary_context = service.retrieve("household", household_id=household_id, top_k=2, now=now)
    assert temporary_context[0].memory.memory_id == temporary.memory_id
    assert temporary_context[0].precedence_rank > temporary_context[1].precedence_rank

    truth_store = PostgresRealityStore(DATABASE_URL)
    truth_key = f"boundary/{household_id}/thermostat"
    truth_now = now + timedelta(seconds=2)
    truth_observation = TruthObservation(
        truth_key=truth_key,
        source="phase3-boundary",
        state=ObservationState.KNOWN,
        value=68,
        observed_at=truth_now,
        received_at=truth_now + timedelta(seconds=1),
        confidence=0.99,
        evidence_kind=EvidenceKind.DIRECT,
    )
    truth_event = EventEnvelope.create(
        event_id=f"phase3-boundary-{household_id}",
        event_type="truth.observation",
        source="phase3-boundary",
        subject_key=truth_key,
        occurred_at=truth_now,
        recorded_at=truth_now + timedelta(seconds=1),
        payload=truth_observation.to_payload(),
        source_event_id=f"phase3-boundary-{household_id}",
    )
    truth_store.ingest(truth_event)
    assert truth_store.projection.get(truth_key, now=truth_now).value == 68

    old_fact = service.create(
        make_memory(
            household_id,
            MemoryType.EXPLICIT_FACT,
            "Use thermostat at 70 degrees.",
            "interaction:thermostat",
            now=now,
        )
    )
    replacement = service.correct(
        old_fact.memory_id,
        make_memory(
            household_id,
            MemoryType.EXPLICIT_FACT,
            "Actually, use thermostat at 68 degrees.",
            "interaction:thermostat-correction",
            now=now + timedelta(seconds=1),
        ),
    )
    assert service.get(old_fact.memory_id).status == MemoryStatus.SUPERSEDED  # type: ignore[union-attr]
    assert (
        service.retrieve("thermostat", household_id=household_id, now=now)[0].memory.memory_id
        == replacement.memory_id
    )

    expiring = service.create(
        make_memory(
            household_id,
            MemoryType.TEMPORARY_EPISODIC,
            "Contractor expected this morning.",
            "interaction:contractor",
            now=now,
            expires_at=now + timedelta(minutes=1),
        )
    )
    assert expiring.memory_id in {
        item.memory.memory_id
        for item in service.retrieve("contractor", household_id=household_id, now=now)
    }
    assert not service.retrieve(
        "contractor", household_id=household_id, now=now + timedelta(minutes=2)
    )
    assert service.get(expiring.memory_id).status == MemoryStatus.EXPIRED  # type: ignore[union-attr]
    manually_expired = service.create(
        make_memory(
            household_id,
            MemoryType.TEMPORARY_EPISODIC,
            "A temporary note to expire explicitly.",
            "interaction:manual-expiry",
            now=now,
        )
    )
    service.expire(manually_expired.memory_id)
    assert service.get(manually_expired.memory_id).status == MemoryStatus.EXPIRED  # type: ignore[union-attr]
    automatically_expired = service.create(
        make_memory(
            household_id,
            MemoryType.TEMPORARY_EPISODIC,
            "Temporary note that has elapsed.",
            "interaction:elapsed",
            now=now,
            expires_at=now - timedelta(seconds=1),
        )
    )
    assert not service.retrieve("temporary note", household_id=household_id, now=now)
    assert service.get(automatically_expired.memory_id).status == MemoryStatus.EXPIRED  # type: ignore[union-attr]
    service.retract(temporary.memory_id)
    assert service.get(temporary.memory_id).status == MemoryStatus.RETRACTED  # type: ignore[union-attr]
    assert not service.retrieve("staying up late", household_id=household_id, now=now)

    assert not service.retrieve("overnight movement", household_id=uuid4(), now=now)
    assert service.retrieve(
        "unusual movement", household_id=household_id, subject_id=alex_id, now=now
    )
    assert service.retrieve(
        "unusual movement", household_id=household_id, graph_ref=office_id, now=now
    )

    indexed = service.retrieve("thermostat", household_id=household_id, now=now)
    assert indexed[0].mode == RetrievalMode.INDEXED_LEXICAL
    service.clear_index()
    degraded = service.retrieve("thermostat", household_id=household_id, now=now)
    assert degraded and degraded[0].mode == RetrievalMode.LEXICAL_FALLBACK
    rebuilt_count = service.rebuild_index()
    assert rebuilt_count == service.index_count()
    assert (
        service.retrieve("thermostat", household_id=household_id, now=now)[0].mode
        == RetrievalMode.INDEXED_LEXICAL
    )

    routine = RoutineService(DATABASE_URL)
    for index in range(4):
        routine.journal.append(
            routine_event(
                household_id,
                f"routine-low-{household_id}-{index}",
                False,
                "01:00",
                now + timedelta(days=index),
            )
        )
        routine.journal.append(
            routine_event(
                household_id,
                f"routine-high-{household_id}-{index}",
                True,
                "08:00",
                now + timedelta(days=index),
            )
        )
    model = routine.rebuild_activity_model(household_id, source="phase3-simulator", now=now)
    assert model.model["bucket_probabilities"]["01:00"] == 0.0
    assert model.model["bucket_probabilities"]["08:00"] == 1.0
    assert "01:00" in model.model["low_activity_buckets"]
    assert model.model["classification"] == "INFERRED"
    routine.journal.append(
        routine_event(
            household_id,
            f"routine-new-{household_id}",
            True,
            "01:00",
            now + timedelta(days=5),
        )
    )
    updated = routine.rebuild_activity_model(
        household_id, source="phase3-simulator", now=now + timedelta(seconds=1)
    )
    assert updated.sample_count == model.sample_count + 1
    assert routine.get(household_id).sample_count == updated.sample_count  # type: ignore[union-attr]

    audit = graph.journal.list_events(
        event_type="memory.mutation",
        source="memory_service",
        subject_key=f"household/{household_id}",
    )
    assert len(audit) >= 6
    print("PHASE3_POSTGRES_INTEGRATION_PASS")
    print(f"household_id={household_id}")
    print(
        "canonical_memory_ids="
        f"{[str(preference.memory_id), str(inferred.memory_id), str(replacement.memory_id)]}"
    )
    print("lifecycle=CORRECTION_EXPIRATION_RETRACTION_PASS")
    print("precedence=EXPLICIT_OVER_INFERRED_PASS")
    print("temporary_context_over_routine=PASS")
    print("truth_memory_boundary=PASS")
    print(f"isolation=PASS index_rebuild_count={rebuilt_count}")
    print(f"routine_model={model.model}")
    print(f"routine_rebuild=PASS sample_count={updated.sample_count}")
    print(f"memory_audit_events={len(audit)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
