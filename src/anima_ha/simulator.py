"""Development simulator for deterministic reality, graph, and memory scenarios."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from anima_ha.agent import (
    AgentRuntime,
    CodexTurnResult,
    EpisodeRequest,
    FinalDecision,
    InMemoryEpisodeStore,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.attention import AttentionReplay, default_attention_profile
from anima_ha.config import RuntimeConfig
from anima_ha.events import (
    DeliveryClass,
    EventEnvelope,
    EventImportance,
    ObservationState,
    TruthObservation,
)
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph
from anima_ha.home_assistant import (
    EXPECTED_HA_VERSION,
    HAInstanceConfig,
    HomeAssistantAdapter,
    PostgresHAStore,
)
from anima_ha.journal import PostgresRealityStore
from anima_ha.logging_setup import configure_logging
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryService,
    MemoryType,
    ProvenanceKind,
)
from anima_ha.plugins import (
    CORE_VERSION,
    NATIVE_SIMULATOR_MANIFEST,
    McpRuntime,
    NativeSimulatorPlugin,
    PluginManager,
    PluginManifest,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import (
    ActionIntent,
    Assurance,
    EvidenceType,
    IdentityAggregator,
    IdentityContext,
    IdentityEvidence,
    OpaPolicyClient,
    PolicyService,
    RequestOrigin,
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
            "policy",
            "plugins",
            "home-assistant",
            "attention",
            "agent",
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
    elif scenario == "policy":
        household_id = uuid4()
        principal_id = uuid4()
        now = datetime.now(UTC).replace(microsecond=0)
        voice = IdentityEvidence(
            uuid4(),
            household_id,
            principal_id,
            EvidenceType.VOICE_CLAIM,
            "simulator-policy",
            now,
            now,
            None,
            Assurance.RECOGNIZED,
            60,
            "synthetic-policy",
        )
        identity = IdentityAggregator().aggregate(household_id, [voice], now=now)
        policy_service = PolicyService(
            OpaPolicyClient(os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181"))
        )
        unlock = ActionIntent.create(
            household_id=household_id,
            semantic_action="unlock",
            origin=RequestOrigin.DIRECT_USER,
            principal_id=principal_id,
            graph_metadata={"security_sensitive": True},
        )
        prohibited = ActionIntent.create(
            household_id=household_id,
            semantic_action="install_package",
            origin=RequestOrigin.DIRECT_USER,
            principal_id=principal_id,
        )
        unlock_decision = policy_service.evaluate(unlock, identity)
        prohibited_decision = policy_service.evaluate(prohibited, identity)
        LOGGER.info(
            "simulator_policy_complete",
            extra={
                "unlock_identity": identity.assurance.value,
                "unlock_decision": unlock_decision.decision.value,
                "unlock_reason": unlock_decision.reason_code,
                "prohibited_decision": prohibited_decision.decision.value,
                "prohibited_reason": prohibited_decision.reason_code,
                "authority_surface": "policy-evaluation-only",
            },
        )
    elif scenario == "plugins":
        manager = PluginManager()
        native = NativeSimulatorPlugin()
        manager.register(NATIVE_SIMULATOR_MANIFEST, native)
        mcp_manifest = PluginManifest(
            plugin_id="anima.simulator.mcp",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core=CORE_VERSION,
            name="Simulator MCP",
            description="Synthetic MCP capability",
            runtime_kind=RuntimeKind.MCP_STDIO,
            trust_class=TrustClass.OPTIONAL_EXTERNAL,
            capabilities=("home.simulation",),
            tools=(
                {
                    "name": "synthetic_echo",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                    "risk_class": "READ_ONLY",
                    "semantic_action": "query_plugin",
                    "read_only": True,
                    "idempotency": "IDEMPOTENT",
                    "external_content_trust": "PLUGIN_TRUSTED",
                },
            ),
        )
        manager.register(
            mcp_manifest,
            McpRuntime(
                RuntimeKind.MCP_STDIO, command=sys.executable, args=["-m", "anima_ha.mcp_reference"]
            ),
        )
        native_state = manager.enable(NATIVE_SIMULATOR_MANIFEST.plugin_id).state.value
        mcp_state = manager.enable(mcp_manifest.plugin_id).state.value
        identity = IdentityContext(uuid4(), None, Assurance.ANONYMOUS)
        policy_service = PolicyService(
            OpaPolicyClient(os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181"))
        )
        plugin_result = manager.invoke(
            "anima.simulator.mcp.synthetic_echo",
            {"message": "simulator"},
            household_id=identity.household_id,
            identity=identity,
            policy_service=policy_service,
        )
        manager.disable(mcp_manifest.plugin_id)
        LOGGER.info(
            "simulator_plugins_complete",
            extra={
                "native_state": native_state,
                "mcp_state": mcp_state,
                "invocation": plugin_result.outcome.value,
                "registry_after_disable": len(manager.list_tools()),
                "authority_surface": "policy-gated-plugin-invocation",
            },
        )
    elif scenario == "attention":
        base = datetime.now(UTC).replace(microsecond=0)
        events: list[dict[str, Any]] = [
            {
                "journal_position": index + 1,
                "event_id": f"sim-attention-motion-{index}",
                "event_type": "household.motion",
                "source": "simulator",
                "subject_key": f"room/{index % 2}/motion",
                "occurred_at": base + timedelta(seconds=index // 10),
                "recorded_at": base + timedelta(seconds=index // 10),
                "importance": EventImportance.NORMAL.value,
                "delivery_class": DeliveryClass.BEST_EFFORT.value,
                "payload": {"active": True},
                "metadata": {},
                "correlation_id": None,
                "causation_id": None,
            }
            for index in range(100)
        ]
        events.append(
            {
                "journal_position": 101,
                "event_id": "sim-attention-user-request",
                "event_type": "user.request",
                "source": "simulator",
                "subject_key": "person/synthetic",
                "occurred_at": base + timedelta(seconds=5),
                "recorded_at": base + timedelta(seconds=5),
                "importance": EventImportance.IMPORTANT.value,
                "delivery_class": DeliveryClass.GUARANTEED.value,
                "payload": {"request": "What happened?"},
                "metadata": {},
                "correlation_id": None,
                "causation_id": None,
            }
        )
        replay = AttentionReplay().evaluate(
            default_attention_profile("simulator.attention.v1"),
            events,
            flush_at=base + timedelta(minutes=2),
        )
        LOGGER.info(
            "simulator_attention_complete",
            extra={
                "source_events": len(events),
                "decisions": len(replay.decisions),
                "triggers": len(replay.triggers),
                "guaranteed_preserved": any(
                    "sim-attention-user-request" in trigger.source_event_ids
                    for trigger in replay.triggers
                ),
                "side_effects": "none",
                "authority_surface": "attention-only",
            },
        )
    elif scenario == "agent":
        household_id = uuid4()
        trigger_id = uuid4()
        context_id = uuid4()
        manager = PluginManager()
        native = NativeSimulatorPlugin()
        manager.register(NATIVE_SIMULATOR_MANIFEST, native)
        manager.enable(NATIVE_SIMULATOR_MANIFEST.plugin_id)
        descriptor = manager.list_tools()[0]
        fake_codex = ScriptedCodexAdapter(
            [
                CodexTurnResult(
                    ToolRequestDecision(descriptor.tool_id, {}),
                    TokenUsage(50, 0, 10, 3),
                    1.0,
                    ("turn.completed",),
                ),
                CodexTurnResult(
                    FinalDecision(
                        "ENOUGH_EVIDENCE",
                        True,
                        "The synthetic household runtime is ready.",
                        "Read-only status succeeded.",
                    ),
                    TokenUsage(60, 20, 15, 4),
                    1.0,
                    ("turn.completed",),
                ),
            ]
        )
        packet = {
            "context_packet_id": str(context_id),
            "schema_version": 1,
            "trigger_id": str(trigger_id),
            "selection_profile_version": "simulator.agent.v1",
            "digest": f"simulator-agent-{trigger_id}",
            "omissions": [],
            "sections": {
                "events": {
                    "status": "READY",
                    "items": [
                        {
                            "kind": "user_request",
                            "data": {"request": "Is the synthetic runtime ready?"},
                            "source_refs": ["simulator-agent-request"],
                            "trust": "LOCAL_TRUSTED",
                            "egress": "CLOUD_ALLOWED",
                        }
                    ],
                    "error_code": None,
                }
            },
        }
        episode = AgentRuntime(fake_codex, manager, InMemoryEpisodeStore()).run(
            EpisodeRequest(
                trigger_id,
                context_id,
                household_id,
                packet,
                (descriptor,),
                IdentityContext(household_id, None, Assurance.ANONYMOUS),
                PolicyService(
                    OpaPolicyClient(os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181"))
                ),
            )
        )
        LOGGER.info(
            "simulator_agent_complete",
            extra={
                "runtime": fake_codex.codex_version,
                "model": fake_codex.model,
                "disposition": episode.episode.final_disposition.value
                if episode.episode.final_disposition
                else None,
                "turns": episode.episode.codex_turn_count,
                "tool_requests": episode.episode.tool_request_count,
                "authority_surface": "phase5-tool-gateway-phase4-policy",
                "phase9_behavior": False,
            },
        )
    elif scenario == "home-assistant":
        document = sample_household_document()
        graph = PostgresHouseholdGraph(config.database_url, config.database_connect_timeout)
        graph.commission(document)
        adapter = HomeAssistantAdapter(
            HAInstanceConfig(
                instance_id=uuid4(),
                websocket_url="ws://127.0.0.1:8123/api/websocket",
                token_secret_name="ANIMA_SIMULATOR_HA_TOKEN",
                expected_version=EXPECTED_HA_VERSION,
            ),
            PostgresRealityStore(config.database_url, config.database_connect_timeout),
            graph,
            PostgresHAStore(config.database_url, config.database_connect_timeout),
        )
        event = adapter.normalize_state_event(
            {
                "entity_id": "input_boolean.synthetic_power",
                "state": "on",
                "last_changed": datetime.now(UTC).isoformat(),
                "last_updated": datetime.now(UTC).isoformat(),
                "attributes": {"friendly_name": "Synthetic Power"},
            }
        )
        LOGGER.info(
            "simulator_home_assistant_contract_complete",
            extra={
                "event_type": event.event_type,
                "provider": event.metadata["provider"],
                "truth_state": event.payload["state"],
                "external_id": event.metadata["external_id"],
                "network_connection": "not-used",
                "authority_surface": "normalization-only",
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
