"""Exercise SENTRY provider process loss at each durable lifecycle boundary.

Each child is a real Python process using the production PostgreSQL intelligence
store.  The parent reconstructs the store after the child exits and applies the
same queue recovery rules used by the bridge.  No model or embedded provider is
used; this target qualifies process/lifecycle behavior only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceOrigin,
    IntelligenceRequest,
    IntelligenceResult,
    IntelligenceResultStatus,
    PostgresIntelligenceStore,
)

ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
PROVIDER = "sentry"


def make_request(household_id: UUID, label: str) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=uuid4(),
        household_id=household_id,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest=f"phase14-process-matrix:{label}:context",
        catalogue_digest=f"phase14-process-matrix:{label}:catalogue",
        provider_id=PROVIDER,
        provider_version="r3",
        idempotency_key=f"phase14-sentry-process-{label}-{uuid4()}",
        request_metadata={"phase14_label": label},
        catalogue=(),
    )


def mark_process(marker: Path, mode: str) -> None:
    marker.write_text(
        json.dumps({"pid": os.getpid(), "mode": mode}, sort_keys=True), encoding="utf-8"
    )


def child(request_id: UUID, household_id: UUID, mode: str, marker: Path) -> int:
    store = PostgresIntelligenceStore(DATABASE_URL)
    worker = f"phase14-sentry-process-{mode}"
    if mode == "before_claim":
        mark_process(marker, mode)
        return 80
    claimed = store.claim(
        worker, provider_id=PROVIDER, household_id=household_id, lease_seconds=120
    )
    if claimed is None or claimed.request_id != request_id:
        raise AssertionError(f"child did not claim its request for {mode}")
    if mode == "after_claim":
        mark_process(marker, mode)
        return 81
    if not store.transition(
        request_id,
        worker,
        claimed.fencing_generation,
        IntelligenceLifecycle.PROVIDER_RUNNING,
        {"provider_invocation_started": True},
    ):
        raise AssertionError("child could not record provider start")
    if mode == "after_provider_start":
        mark_process(marker, mode)
        return 82
    if mode == "after_result":
        if not store.record_result(
            request_id,
            worker,
            claimed.fencing_generation,
            IntelligenceResult(
                request_id,
                IntelligenceResultStatus.RESPONSE,
                response_text="durable process-matrix response",
            ),
        ):
            raise AssertionError("child could not record durable result")
        mark_process(marker, mode)
        return 83
    raise ValueError(f"unknown process-matrix mode: {mode}")


def expire(request_id: UUID) -> None:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE anima_intelligence_requests "
            "SET lease_expires_at=now()-interval '1 second', updated_at=now() "
            "WHERE request_id=%s",
            (request_id,),
        )
        connection.commit()


def run_child(request: IntelligenceRequest, mode: str, marker: Path) -> int:
    result = subprocess.run(
        [
            sys.executable,
            __file__,
            "--child",
            str(request.request_id),
            str(request.household_id),
            mode,
            str(marker),
        ],
        cwd=ROOT,
        env={**os.environ, "ANIMA_DATABASE_URL": DATABASE_URL},
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stderr:
        raise AssertionError(f"SENTRY child failed for {mode}: {result.stderr}")
    return result.returncode


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    if len(sys.argv) == 6 and sys.argv[1] == "--child":
        return child(UUID(sys.argv[2]), UUID(sys.argv[3]), sys.argv[4], Path(sys.argv[5]))

    migrate(DATABASE_URL, 5)
    store = PostgresIntelligenceStore(DATABASE_URL)
    cases: list[dict[str, Any]] = []

    pre_claim = make_request(uuid4(), "before-claim")
    store.enqueue(pre_claim)
    pre_marker = Path(f"/tmp/anima-phase14-sentry-process-{pre_claim.request_id}.json")
    if run_child(pre_claim, "before_claim", pre_marker) != 80:
        raise AssertionError("pre-claim child exit was unexpected")
    recovered = store.claim(
        "phase14-sentry-reconstructed-before-claim",
        provider_id=PROVIDER,
        household_id=pre_claim.household_id,
    )
    if recovered is None or recovered.request_id != pre_claim.request_id:
        raise AssertionError("pre-claim work was not safely claimable")
    cases.append(
        {
            "state": "PENDING",
            "child_pid": json.loads(pre_marker.read_text())["pid"],
            "recovery": "CLAIMED",
        }
    )

    after_claim = make_request(uuid4(), "after-claim")
    store.enqueue(after_claim)
    claim_marker = Path(f"/tmp/anima-phase14-sentry-process-{after_claim.request_id}.json")
    if run_child(after_claim, "after_claim", claim_marker) != 81:
        raise AssertionError("after-claim child exit was unexpected")
    expire(after_claim.request_id)
    reclaimed = store.claim(
        "phase14-sentry-reconstructed-after-claim",
        provider_id=PROVIDER,
        household_id=after_claim.household_id,
    )
    if reclaimed is None or reclaimed.request_id != after_claim.request_id:
        raise AssertionError("unstarted claimed work was not reclaimable")
    cases.append(
        {
            "state": "CLAIMED",
            "child_pid": json.loads(claim_marker.read_text())["pid"],
            "recovery": "RECLAIMED",
        }
    )

    after_start = make_request(uuid4(), "after-provider-start")
    store.enqueue(after_start)
    start_marker = Path(f"/tmp/anima-phase14-sentry-process-{after_start.request_id}.json")
    if run_child(after_start, "after_provider_start", start_marker) != 82:
        raise AssertionError("provider-start child exit was unexpected")
    expire(after_start.request_id)
    no_reclaim = store.claim(
        "phase14-sentry-reconstructed-after-start",
        provider_id=PROVIDER,
        household_id=after_start.household_id,
    )
    current = store.get(after_start.request_id)
    if (
        no_reclaim is not None
        or current is None
        or current.lifecycle != IntelligenceLifecycle.UNKNOWN_RESULT
    ):
        raise AssertionError("provider-started work was replayed instead of made unknown")
    cases.append(
        {
            "state": "PROVIDER_RUNNING",
            "child_pid": json.loads(start_marker.read_text())["pid"],
            "recovery": current.lifecycle.value,
        }
    )

    after_result = make_request(uuid4(), "after-result")
    store.enqueue(after_result)
    result_marker = Path(f"/tmp/anima-phase14-sentry-process-{after_result.request_id}.json")
    if run_child(after_result, "after_result", result_marker) != 83:
        raise AssertionError("durable-result child exit was unexpected")
    no_rerun = store.claim(
        "phase14-sentry-reconstructed-after-result",
        provider_id=PROVIDER,
        household_id=after_result.household_id,
    )
    current = store.get(after_result.request_id)
    if (
        no_rerun is not None
        or current is None
        or current.lifecycle != IntelligenceLifecycle.COMPLETED
    ):
        raise AssertionError("durable result was not reused without a new claim")
    cases.append(
        {
            "state": "RESULT_RECEIVED",
            "child_pid": json.loads(result_marker.read_text())["pid"],
            "recovery": current.lifecycle.value,
        }
    )

    print(
        json.dumps(
            {
                "scenario_id": "SENTRY_PROCESS_LIFECYCLE_MATRIX_NO_BLIND_REPLAY",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS",
                "states": cases,
                "provider_replays": 0,
                "embedded_agent_runtime_fallback": False,
                "checked_at": datetime.now(UTC).isoformat(),
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    for case in (pre_marker, claim_marker, start_marker, result_marker):
        case.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
