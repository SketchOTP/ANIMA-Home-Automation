"""Consolidate Phase 14 hosted evidence into one honest machine-readable ledger.

This is an evidence-audit target, not another resilience implementation. It
reads the outputs produced by the real-store qualification steps, preserves
their evidence levels, and reports coverage without treating deterministic
contract fixtures as destructive system evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

REQUIRED_FILES = (
    "phase14-r2-real-store.json",
    "phase14-backup-restore-r2.json",
    "phase14-approval-race.json",
    "phase14-approval-crash-r2.json",
    "phase14-approval-durable-r3.json",
    "phase14-policy-reauthorization-r3.json",
    "phase14-action-recovery-r2.json",
    "phase14-continuation-r2.json",
    "phase14-external-r2.json",
    "phase14-external-attack-r2.json",
    "phase14-events-plugins-r2.json",
    "phase14-plugin-process-r2.json",
    "phase14-clean-replay-r2.json",
    "phase14-sentry-bridge-restart-r2.json",
    "phase14-sentry-provider-crash-r2.json",
    "phase14-sentry-process-matrix-r3.json",
    "phase14-sentry-outage-r2.json",
    "phase14-ha-outage-r2.json",
    "phase14-ha-ambiguous-r3.json",
    "phase14-opa-outage-r2.json",
    "phase14-process-matrix-r2.json",
    "phase14-inflight-restart-r2.json",
)
CONTRACT_ONLY_FILES = ("phase14-resilience.json",)
PASS_STATUSES = frozenset(("PASS", "PASSED"))

REQUIRED_COVERAGE: dict[str, tuple[str, ...]] = {
    "provider_lifecycle": (
        "PROVIDER_PRESTART_CRASH_RECLAIM",
        "PROVIDER_STARTED_CRASH_NO_REPLAY",
        "PROVIDER_RESULT_DURABLE_NO_RERUN",
        "STALE_FENCE_ALL_PROVIDER_WRITES_REJECTED",
    ),
    "approval_continuation": (
        "APPROVAL_CONCURRENT_ONE_WINNER",
        "APPROVAL_CONTINUATION_PROCESS_CRASH_NO_REDISPATCH",
        "CONTINUATION_POST_ACTION_DURABLE_NO_DUPLICATE_RESULT",
        "CONTINUATION_STALE_FENCE_AND_PRECLAIM_CRASH",
        "POLICY_CHANGE_BEFORE_APPROVAL_NO_DISPATCH",
    ),
    "action_reality": (
        "ACTION_PRE_DISPATCH_CRASH_RECLAIM",
        "ACTION_STARTED_CRASH_NO_REPLAY",
        "ACTION_ACK_BEFORE_VERIFICATION_FAILURE",
        "ACTION_POSSIBLE_DISPATCH_UNKNOWN_NO_RETRY",
        "ACTION_RESULT_DURABLE_NO_RERUN",
        "POSSIBLE_DISPATCH_VERIFICATION_FAILED_NO_RETRY",
        "HA_OUTAGE_NO_REDISPATCH",
    ),
    "event_truth_attention": (
        "HA_DUPLICATE_EVENT_DEDUP",
        "HA_DUPLICATE_SOURCE_EVENT_DEDUP",
        "HA_OUT_OF_ORDER_TRUTH",
        "ATTENTION_DUPLICATE_DEDUP",
        "SENSEGUARD_DUPLICATE_DEDUP",
        "JOURNAL_RESTART_BEFORE_PROJECTION",
    ),
    "plugin_isolation": (
        "PLUGIN_FAILURE_ISOLATION_THREE_CLASSES",
        "PLUGIN_PROCESS_RESTART_AND_FAILURE_ISOLATION",
        "EXTERNAL_PROVIDER_FAILURE_ISOLATION",
    ),
    "external_content": (
        "EXTERNAL_TIMEOUT_FAILS_EXPLICITLY",
        "EXTERNAL_MALFORMED_RESPONSE_FAILS_EXPLICITLY",
        "EXTERNAL_5XX_FAILS_EXPLICITLY",
        "EXTERNAL_PARTIAL_PRODUCT_HONEST_UNKNOWN",
        "EXTERNAL_STALE_OFFER_NOT_CURRENT_TRUTH",
        "PROMPT_INJECTION_NO_AUTHORITY",
        "EXTERNAL_FAKE_PERMISSION_NO_ESCALATION",
        "EXTERNAL_SECRET_EXFILTRATION_TEXT_NOT_DURABLE",
        "RESTRICTED_CONTENT_ZERO_DURABLE",
        "EXTERNAL_AUDIT_DIGEST_NO_RAW_SENTINEL",
    ),
    "backup_restore_replay": (
        "BACKUP_RESTORE_CLEAN_ENVIRONMENT",
        "REAL_STORE_CLEAN_REPLAY",
    ),
    "process_restart": (
        "PROCESS_RESTART_MATRIX_SERVICE_CONTINUITY",
        "PROCESS_RESTART_INFLIGHT_DURABLE_STATES",
        "SENTRY_PROCESS_LIFECYCLE_MATRIX_NO_BLIND_REPLAY",
        "SENTRY_BRIDGE_RESTART_NO_DUPLICATE_REQUEST",
    ),
    "sentry_continuity": (
        "SENTRY_OUTAGE_LOCAL_PLATFORM_CONTINUES",
        "SENTRY_PROVIDER_STARTED_CRASH_NO_REPLAY",
    ),
    "policy_and_history": (
        "OPA_OUTAGE_FAIL_CLOSED",
        "TASK_CALENDAR_250_RECORD_PAGINATION",
    ),
}


def _iter_scenarios(
    value: Any, *, source: str, inherited: dict[str, Any]
) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        current = {
            key: value[key] for key in ("status", "evidence_level", "phase15") if key in value
        }
        current = {**inherited, **current}
        if isinstance(value.get("scenario_id"), str):
            yield {
                "scenario_id": value["scenario_id"],
                "status": current.get("status", "UNKNOWN"),
                "evidence_level": current.get("evidence_level", "UNKNOWN"),
                "phase15": current.get("phase15", False),
                "source": source,
            }
        for child in value.values():
            yield from _iter_scenarios(child, source=source, inherited=current)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_scenarios(child, source=source, inherited=inherited)


def _read_scenarios(directory: Path) -> tuple[list[dict[str, Any]], list[str]]:
    scenarios: list[dict[str, Any]] = []
    missing: list[str] = []
    for filename in REQUIRED_FILES:
        path = directory / filename
        if not path.is_file():
            missing.append(filename)
            continue
        payload = _load_payload(path)
        scenarios.extend(_iter_scenarios(payload, source=filename, inherited={}))
    for filename in CONTRACT_ONLY_FILES:
        path = directory / filename
        if path.is_file():
            scenarios.extend(_iter_scenarios(_load_payload(path), source=filename, inherited={}))
    return scenarios, missing


def _load_payload(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as full_error:
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise ValueError(f"invalid JSON evidence: {path}: {full_error}") from full_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    scenarios, missing_files = _read_scenarios(args.evidence_dir)
    by_id: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        existing = by_id.get(scenario["scenario_id"])
        if existing is None or (
            existing["status"] == "UNKNOWN" and scenario["status"] != "UNKNOWN"
        ):
            by_id[scenario["scenario_id"]] = scenario

    coverage: dict[str, dict[str, Any]] = {}
    for family, scenario_ids in REQUIRED_COVERAGE.items():
        found = [by_id[item] for item in scenario_ids if item in by_id]
        non_passing = [item["scenario_id"] for item in found if item["status"] not in PASS_STATUSES]
        coverage[family] = {
            "status": (
                "VERIFIED" if len(found) == len(scenario_ids) and not non_passing else "PARTIAL"
            ),
            "required": list(scenario_ids),
            "observed": found,
            "missing": [item for item in scenario_ids if item not in by_id],
            "non_passing": non_passing,
        }

    deterministic_only = sorted(
        {
            item["scenario_id"]
            for item in scenarios
            if item["evidence_level"] == "DETERMINISTIC_CONTRACT"
        }
    )
    source_digests = {
        filename: hashlib.sha256((args.evidence_dir / filename).read_bytes()).hexdigest()
        for filename in REQUIRED_FILES
        if (args.evidence_dir / filename).is_file()
    }
    payload = {
        "scenario_id": "PHASE14_EVIDENCE_LEDGER",
        "status": "PASS" if not missing_files else "FAIL",
        "ledger_disposition": "CONTINUE",
        "tested_sha": os.environ.get("GITHUB_SHA", "local"),
        "required_file_count": len(REQUIRED_FILES),
        "observed_file_count": len(source_digests),
        "missing_files": missing_files,
        "coverage": coverage,
        "deterministic_contract_excluded_from_destructive_evidence": deterministic_only,
        "source_digests": source_digests,
        "phase15": False,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0 if not missing_files else 1


if __name__ == "__main__":
    raise SystemExit(main())
