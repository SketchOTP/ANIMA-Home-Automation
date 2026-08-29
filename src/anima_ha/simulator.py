"""Development simulator for deterministic Phase 1 reality-substrate scenarios."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from anima_ha.config import RuntimeConfig
from anima_ha.events import EventEnvelope, ObservationState, TruthObservation
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.journal import PostgresRealityStore
from anima_ha.logging_setup import configure_logging

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
