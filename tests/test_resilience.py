from __future__ import annotations

from dataclasses import replace

import pytest

from anima_ha.resilience import (
    BackupManifest,
    EvidenceStatus,
    FailureScenario,
    FaultInjected,
    FaultPoint,
    ReplayRunner,
    ScenarioLedger,
    ScenarioResult,
    TestFaultInjector,
)


def scenario() -> FailureScenario:
    return FailureScenario(
        scenario_id="PROVIDER_STARTED_CRASH_NO_REPLAY",
        initial_durable_state={"lifecycle": "PROVIDER_RUNNING"},
        truth_versions={"light": 4},
        principal_evidence_policy={"principal": "fixture", "policy": "allow"},
        events_ordering=({"event": "request.created", "sequence": 1},),
        intelligence_provider_state={
            "provider": "sentry",
            "invocation_started": True,
        },
        fault_point="provider.model",
        tool_action_state={"dispatches": 0},
        ha_provider_observations={"light": "unknown"},
        plugin_availability={"sentry": "available"},
        expected_terminal_state="UNKNOWN_RESULT",
        expected_side_effect_count=0,
        expected_recovery_behavior="do_not_blindly_replay",
    )


def execute(item: FailureScenario, faults: TestFaultInjector) -> ScenarioResult:
    transitions = ["PENDING", "CLAIMED", "PROVIDER_RUNNING"]
    try:
        faults.check(FaultPoint.PROVIDER_MODEL)
    except FaultInjected as exc:
        return ScenarioResult(
            item.scenario_id,
            EvidenceStatus.PASSED,
            "UNKNOWN_RESULT",
            0,
            tuple(transitions + [f"FAULT:{exc.point.value}"]),
            "do_not_blindly_replay",
            "model work may have started; recovery is explicit",
        )
    return ScenarioResult(
        item.scenario_id,
        EvidenceStatus.PASSED,
        item.expected_terminal_state,
        item.expected_side_effect_count,
        tuple(transitions + ["COMPLETED"]),
        item.expected_recovery_behavior,
    )


def test_canonical_scenario_contains_all_required_fields() -> None:
    payload = scenario().to_payload()
    assert {
        "scenario_id",
        "initial_durable_state",
        "truth_versions",
        "principal_evidence_policy",
        "events_ordering",
        "intelligence_provider_state",
        "fault_point",
        "tool_action_state",
        "ha_provider_observations",
        "plugin_availability",
        "expected_terminal_state",
        "expected_side_effect_count",
        "expected_recovery_behavior",
    } <= payload.keys()


def test_fault_injection_requires_explicit_test_construction_and_is_one_shot() -> None:
    injector = TestFaultInjector.for_tests(FaultPoint.OPA)
    with pytest.raises(FaultInjected):
        injector.check(FaultPoint.OPA)
    injector.check(FaultPoint.OPA)
    with pytest.raises(RuntimeError):
        TestFaultInjector().check(FaultPoint.OPA)


def test_replay_matches_and_detects_regression() -> None:
    runner = ReplayRunner(execute)
    item = scenario()
    expected = runner.run(item, faults=(FaultPoint.PROVIDER_MODEL,))
    comparison = runner.compare(item, expected, faults=(FaultPoint.PROVIDER_MODEL,))
    assert comparison.matched is True

    def regressed(current: FailureScenario, faults: TestFaultInjector) -> ScenarioResult:
        result = execute(current, faults)
        return replace(result, side_effect_count=1)

    regressed_comparison = ReplayRunner(regressed).compare(
        item, expected, faults=(FaultPoint.PROVIDER_MODEL,)
    )
    assert regressed_comparison.matched is False
    assert "side_effect_count" in regressed_comparison.differences


def test_ledger_is_append_only_and_secret_free() -> None:
    ledger = ScenarioLedger()
    result = ScenarioResult(
        "OPA_OUTAGE_FAIL_CLOSED",
        EvidenceStatus.PASSED,
        "DENIED",
        0,
        recovery_behavior="retry_after_opa_recovery",
    )
    ledger.append(result)
    with pytest.raises(ValueError):
        ledger.append(result)
    encoded = ledger.to_json()
    assert "secret_free" not in encoded
    assert ledger.digest in encoded


def test_backup_manifest_forces_safe_restore_semantics() -> None:
    manifest = BackupManifest(
        database_identity="isolated-anima",
        schema_version="phase14",
        captured_at="2026-09-05T00:00:00Z",
        tables=("events", "truth", "tasks", "calendar", "audit"),
        historical_records_retained=True,
    )
    payload = manifest.to_payload()
    assert payload["secret_free"] is True
    assert payload["physical_truth_after_restore"] == "UNKNOWN_UNTIL_REOBSERVED"
    assert payload["executed_effects_replayed"] is False
    with pytest.raises(ValueError):
        BackupManifest(
            database_identity="database-password-secret",
            schema_version="phase14",
            captured_at="now",
            tables=(),
            historical_records_retained=False,
        )
