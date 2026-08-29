"""Development simulator for deterministic reality, graph, and memory scenarios."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from anima_ha.config import RuntimeConfig
from anima_ha.events import EventEnvelope, ObservationState, TruthObservation
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.journal import PostgresRealityStore
from anima_ha.logging_setup import configure_logging
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryService,
    MemoryType,
    ProvenanceKind,
)
from anima_ha.routines import RoutineService

LOGGER = logging.getLogger("anima_ha.simulator")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ANIMA HA development simulator framework")
    parser.add_argument(
        "--once",
        action="store_true",
        help="report readiness and exit; no simulated household event is emitted",
    )
    parser.add_argument("--duration", type=float, default=0.0, help="optional readiness duration")
    parser.add_argument(
        "--scenario",
        choices=(
            "ready",
            "normal",
            "duplicate",
            "out-of-order",
            "stale",
            "unavailable",
            "conflict",
            "rebuild",
            "graph",
            "memory",
        ),
        default="ready",
        help="inject a bounded synthetic reality-substrate scenario",
    )
    return parser


def _event(event_id: str, observation: TruthObservation) -> EventEnvelope:
    return EventEnvelope.create(
        event_id=event_id,
        event_type="truth.observation",
        source=observation.source,
        subject_key=observation.truth_key,
        occurred_at=observation.observed_at,
        recorded_at=observation.received_at,
        source_sequence=observation.source_sequence,
        confidence=observation.confidence,
        evidence_kind=observation.evidence_kind,
        payload=observation.to_payload(),
        source_event_id=event_id,
    )


def run(*, once: bool = False, duration: float = 0.0, scenario: str = "ready") -> int:
    config = RuntimeConfig.from_environment()
    configure_logging(config.log_level)
    LOGGER.info(
        "simulator_ready",
        extra={"mode": "reality-substrate", "event_semantics": "deterministic-synthetic-only"},
    )
    if scenario == "graph":
        graph = PostgresHouseholdGraph(config.database_url, config.database_connect_timeout)
        result = graph.commission(sample_household_document())
        LOGGER.info(
            "simulator_graph_complete",
            extra={
                "nodes_created": result.created_nodes,
                "places": len(graph.list_places()),
                "exterior_entrances": len(graph.exterior_entrances()),
            },
        )
    elif scenario == "memory":
        household_id = uuid4()
        now = datetime.now(UTC).replace(microsecond=0)
        service = MemoryService(config.database_url, config.database_connect_timeout)
        service.create(
            MemoryRecord.create(
                household_id=household_id,
                memory_type=MemoryType.EXPLICIT_PREFERENCE,
                content="Notify us about unusual overnight movement.",
                provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "simulator:memory"),
                created_at=now,
            )
        )
        service.create(
            MemoryRecord.create(
                household_id=household_id,
                memory_type=MemoryType.TEMPORARY_EPISODIC,
                content="Guests are staying through tonight.",
                provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "simulator:temporary"),
                created_at=now,
                valid_from=now,
                valid_until=now + timedelta(hours=8),
                expires_at=now + timedelta(hours=8),
            )
        )
        memory_results = service.retrieve("overnight", household_id=household_id, top_k=2, now=now)
        routine = RoutineService(config.database_url, config.database_connect_timeout)
        for index in range(2):
            at = now + timedelta(days=index)
            routine.journal.append(
                EventEnvelope.create(
                    event_id=f"sim-memory-routine-low-{household_id}-{index}",
                    event_type="routine.activity_observation",
                    source="simulator-memory",
                    subject_key=f"routine/household/{household_id}",
                    occurred_at=at,
                    recorded_at=at + timedelta(seconds=1),
                    payload={"active": False, "bucket": "01:00"},
                    source_event_id=f"sim-memory-routine-low-{household_id}-{index}",
                )
            )
        model = routine.rebuild_activity_model(household_id, source="simulator-memory", now=now)
        LOGGER.info(
            "simulator_memory_complete",
            extra={
                "retrieval_mode": memory_results[0].mode.value if memory_results else "NONE",
                "retrieved_types": [item.memory.memory_type.value for item in memory_results],
                "routine_classification": model.model["classification"],
                "routine_low_activity_buckets": model.model["low_activity_buckets"],
                "authority_surface": "none",
            },
        )
    elif scenario != "ready":
        base = datetime.now(UTC).replace(microsecond=0)
        observation = TruthObservation(
            truth_key="simulator/example/value",
            source="simulator",
            value=42 if scenario != "unavailable" else None,
            state=(
                ObservationState.UNAVAILABLE
                if scenario == "unavailable"
                else ObservationState.KNOWN
            ),
            observed_at=base,
            received_at=base + timedelta(seconds=1),
            source_sequence=1,
            freshness_seconds=1 if scenario == "stale" else 60,
        )
        store = PostgresRealityStore(config.database_url, config.database_connect_timeout)
        results = [store.ingest(_event(f"sim-{scenario}-1", observation))[0].deduplicated]
        if scenario == "duplicate":
            results.append(store.ingest(_event("sim-duplicate-1", observation))[0].deduplicated)
        elif scenario == "out-of-order":
            older = replace(
                observation, value=41, source_sequence=0, observed_at=base - timedelta(minutes=1)
            )
            results.append(store.ingest(_event("sim-out-of-order-0", older))[0].deduplicated)
        elif scenario == "conflict":
            other = replace(observation, source="simulator-secondary", value=43)
            store.ingest(_event("sim-conflict-2", other))
        elif scenario == "rebuild":
            store.projection.rebuild()
        LOGGER.info(
            "simulator_scenario_complete", extra={"scenario": scenario, "deduplicated": results}
        )
    if not once and duration > 0:
        time.sleep(duration)
    LOGGER.info("simulator_stopped", extra={"reason": "baseline_exit"})
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return run(once=args.once, duration=args.duration, scenario=args.scenario)


if __name__ == "__main__":
    raise SystemExit(main())
