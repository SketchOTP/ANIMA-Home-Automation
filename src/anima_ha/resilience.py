"""Canonical Phase 14 resilience scenarios, replay, and restore safety metadata.

This module is deliberately domain-neutral. It provides a single bounded
machine-readable evidence shape for destructive tests and does not provide a
production fault-injection route, scheduler, broker, or authority store.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class EvidenceStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_RUN = "NOT RUN"
    NOT_APPLICABLE = "NOT APPLICABLE"
    BLOCKED = "BLOCKED"


class FaultPoint(StrEnum):
    JOURNAL_APPEND = "journal.append"
    TRUTH_PROJECTION = "truth.projection"
    ATTENTION_REQUEST = "attention.request"
    PROVIDER_CLAIM = "provider.claim"
    PROVIDER_START = "provider.start"
    PROVIDER_MODEL = "provider.model"
    PROVIDER_RESULT = "provider.result"
    CONFIRMATION = "confirmation"
    TOOL_GATEWAY = "tool.gateway"
    OPA = "opa"
    ACTION_LOCK = "action.lock"
    ACTION_DISPATCH = "action.dispatch"
    ACTION_VERIFY = "action.verify"
    TASK_COMMIT = "task.commit"
    CALENDAR_COMMIT = "calendar.commit"
    HA_RECONNECT = "ha.reconnect"
    PLUGIN = "plugin"
    CORE = "core"
    SENTRY_BRIDGE = "sentry.bridge"
    POSTGRES = "postgres"


class FaultInjected(RuntimeError):
    """A one-shot failure raised only by an explicitly constructed test injector."""

    def __init__(self, point: FaultPoint) -> None:
        super().__init__(f"test fault injected at {point.value}")
        self.point = point


@dataclass(slots=True)
class TestFaultInjector:
    """Bounded, one-shot fault injector for tests and replay only.

    There is no environment-variable or browser/MCP construction path. Tests
    must opt in explicitly through for_tests(), making accidental production
    activation fail closed.
    """

    _armed: set[FaultPoint] = field(default_factory=set)
    _test_mode: bool = False

    __test__ = False

    @classmethod
    def for_tests(cls, *points: FaultPoint) -> TestFaultInjector:
        return cls(set(points), True)

    def check(self, point: FaultPoint) -> None:
        if not self._test_mode:
            raise RuntimeError("fault injection is test-only")
        if point in self._armed:
            self._armed.remove(point)
            raise FaultInjected(point)


@dataclass(frozen=True, slots=True)
class FailureScenario:
    scenario_id: str
    initial_durable_state: Mapping[str, Any]
    truth_versions: Mapping[str, int]
    principal_evidence_policy: Mapping[str, Any]
    events_ordering: tuple[Mapping[str, Any], ...]
    intelligence_provider_state: Mapping[str, Any]
    fault_point: str | None
    tool_action_state: Mapping[str, Any]
    ha_provider_observations: Mapping[str, Any]
    plugin_availability: Mapping[str, Any]
    expected_terminal_state: str
    expected_side_effect_count: int
    expected_recovery_behavior: str
    resource_lock_state: Mapping[str, Any] = field(default_factory=dict)
    provider_failpoint: str | None = None
    model_failpoint: str | None = None
    tool_failpoint: str | None = None
    action_failpoint: str | None = None
    external_content_trust_class: str = "NONE"
    restart_points: tuple[str, ...] = ()
    expected_durable_record_ids: tuple[str, ...] = ()
    expected_durable_record_digests: tuple[str, ...] = ()
    tested_sha: str = ""
    process_identity: Mapping[str, Any] = field(default_factory=dict)
    policy_references: tuple[str, ...] = ()
    dispatch_metadata: Mapping[str, Any] = field(default_factory=dict)
    verification_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id.strip():
            raise ValueError("scenario_id is required")
        if self.expected_side_effect_count < 0:
            raise ValueError("side-effect count cannot be negative")
        encoded = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        if len(encoded.encode()) > 32_768:
            raise ValueError("resilience scenario exceeds bounded size")

    def to_payload(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "initial_durable_state": dict(self.initial_durable_state),
            "truth_versions": dict(self.truth_versions),
            "principal_evidence_policy": dict(self.principal_evidence_policy),
            "events_ordering": [dict(event) for event in self.events_ordering],
            "intelligence_provider_state": dict(self.intelligence_provider_state),
            "fault_point": self.fault_point,
            "tool_action_state": dict(self.tool_action_state),
            "ha_provider_observations": dict(self.ha_provider_observations),
            "plugin_availability": dict(self.plugin_availability),
            "expected_terminal_state": self.expected_terminal_state,
            "expected_side_effect_count": self.expected_side_effect_count,
            "expected_recovery_behavior": self.expected_recovery_behavior,
            "resource_lock_state": dict(self.resource_lock_state),
            "provider_failpoint": self.provider_failpoint,
            "model_failpoint": self.model_failpoint,
            "tool_failpoint": self.tool_failpoint,
            "action_failpoint": self.action_failpoint,
            "external_content_trust_class": self.external_content_trust_class,
            "restart_points": list(self.restart_points),
            "expected_durable_record_ids": list(self.expected_durable_record_ids),
            "expected_durable_record_digests": list(self.expected_durable_record_digests),
            "tested_sha": self.tested_sha,
            "process_identity": dict(self.process_identity),
            "policy_references": list(self.policy_references),
            "dispatch_metadata": dict(self.dispatch_metadata),
            "verification_metadata": dict(self.verification_metadata),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_id: str
    status: EvidenceStatus
    terminal_state: str
    side_effect_count: int
    transitions: tuple[str, ...] = ()
    recovery_behavior: str = ""
    detail: str = ""
    trace: tuple[Mapping[str, Any], ...] = ()
    evidence_level: str = "DETERMINISTIC_CONTRACT"

    def __post_init__(self) -> None:
        if self.side_effect_count < 0:
            raise ValueError("side-effect count cannot be negative")

    def to_payload(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "status": self.status.value,
            "terminal_state": self.terminal_state,
            "side_effect_count": self.side_effect_count,
            "transitions": list(self.transitions),
            "recovery_behavior": self.recovery_behavior,
            "detail": self.detail,
            "trace": [dict(item) for item in self.trace],
            "evidence_level": self.evidence_level,
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(slots=True)
class ScenarioLedger:
    """Append-only, secret-free scenario result collection."""

    results: list[ScenarioResult] = field(default_factory=list)

    def append(self, result: ScenarioResult) -> None:
        if any(item.scenario_id == result.scenario_id for item in self.results):
            raise ValueError(f"duplicate scenario result: {result.scenario_id}")
        self.results.append(result)

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "scenario_count": len(self.results),
            "results": [item.to_payload() for item in self.results],
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

    def to_json(self) -> str:
        return json.dumps(
            {**self.to_payload(), "ledger_digest": self.digest},
            sort_keys=True,
            indent=2,
        )


ScenarioExecutor = Callable[[FailureScenario, TestFaultInjector], ScenarioResult]


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    scenario_id: str
    original_digest: str
    replay_digest: str
    matched: bool
    differences: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "original_digest": self.original_digest,
            "replay_digest": self.replay_digest,
            "matched": self.matched,
            "differences": list(self.differences),
        }


class ReplayRunner:
    """Run a deterministic scenario and compare a later replay."""

    def __init__(self, executor: ScenarioExecutor) -> None:
        self._executor = executor

    def run(
        self, scenario: FailureScenario, *, faults: tuple[FaultPoint, ...] = ()
    ) -> ScenarioResult:
        injector = TestFaultInjector.for_tests(*faults)
        return self._executor(scenario, injector)

    def compare(
        self,
        scenario: FailureScenario,
        expected: ScenarioResult,
        *,
        faults: tuple[FaultPoint, ...] = (),
    ) -> ReplayComparison:
        replayed = self.run(scenario, faults=faults)
        differences: list[str] = []
        if replayed.terminal_state != expected.terminal_state:
            differences.append("terminal_state")
        if replayed.side_effect_count != expected.side_effect_count:
            differences.append("side_effect_count")
        if replayed.transitions != expected.transitions:
            differences.append("transitions")
        if replayed.recovery_behavior != expected.recovery_behavior:
            differences.append("recovery_behavior")
        return ReplayComparison(
            scenario_id=scenario.scenario_id,
            original_digest=expected.digest,
            replay_digest=replayed.digest,
            matched=not differences,
            differences=tuple(differences),
        )


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Secret-free metadata describing a database backup and safe restoration."""

    database_identity: str
    schema_version: str
    captured_at: str
    tables: tuple[str, ...]
    historical_records_retained: bool
    physical_truth_after_restore: str = "UNKNOWN_UNTIL_REOBSERVED"
    executed_effects_replayed: bool = False
    pending_work_requires_current_policy: bool = True

    def __post_init__(self) -> None:
        if not self.database_identity.strip() or not self.schema_version.strip():
            raise ValueError("backup identity and schema version are required")
        if self.executed_effects_replayed:
            raise ValueError("restoration must never replay executed effects")
        if any(secret in self.database_identity.lower() for secret in ("password", "token", "key")):
            raise ValueError("secret-like backup identity is not allowed")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "database_identity": self.database_identity,
            "source_schema_version": self.schema_version,
            "captured_at": self.captured_at,
            "tables": list(self.tables),
            "historical_records_retained": self.historical_records_retained,
            "physical_truth_after_restore": self.physical_truth_after_restore,
            "executed_effects_replayed": self.executed_effects_replayed,
            "pending_work_requires_current_policy": self.pending_work_requires_current_policy,
            "secret_free": True,
        }
