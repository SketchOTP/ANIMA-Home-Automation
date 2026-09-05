"""Exercise the SENTRY provider crash boundary against real PostgreSQL.

The child process uses the real ANIMA SENTRY boundary and bridge worker, then
terminates after the durable ``PROVIDER_RUNNING`` transition and before a
provider result.  The parent expires that lease and verifies that ANIMA marks
the work ambiguous rather than reclaiming it for a second model turn.
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
    PostgresIntelligenceStore,
)
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBridgeWorker

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
ROOT = Path(__file__).resolve().parents[1]
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


class EmptyManager:
    def list_tools(self) -> list[Any]:
        return []


class CrashProvider:
    def __init__(self, marker: Path) -> None:
        self.marker = marker

    def run(
        self,
        request: IntelligenceRequest,
        context_packet: dict[str, Any],
        catalogue: list[dict[str, Any]],
        boundary: CoreSentryBoundary,
    ) -> IntelligenceResult:
        del context_packet, catalogue, boundary
        self.marker.write_text(
            json.dumps(
                {
                    "request_id": str(request.request_id),
                    "model_callback_started": True,
                    "recorded_at": datetime.now(UTC).isoformat(),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        # Simulate a hard SENTRY/provider process loss after the call boundary
        # has started.  os._exit intentionally skips bridge cleanup.
        os._exit(77)


class TargetedBoundary(CoreSentryBoundary):
    __slots__ = ("request_id",)

    def __init__(self, request_id: UUID) -> None:
        super().__init__(
            manager=EmptyManager(),
            policy_service=object(),
            intelligence_store=PostgresIntelligenceStore(DATABASE_URL),
        )
        self.request_id = request_id

    def claim_request(
        self, worker_id: str, *, household_id: UUID | None = None
    ) -> IntelligenceRequest | None:
        return self.claim_specific_request(
            self.request_id,
            worker_id,
            household_id or HOUSEHOLD_ID,
        )


def boundary(request_id: UUID) -> TargetedBoundary:
    return TargetedBoundary(request_id)


def child(request_id: UUID, marker: Path) -> int:
    worker = SentryBridgeWorker(
        boundary=boundary(request_id),
        provider=CrashProvider(marker),
        worker_id="phase14-sentry-crash-worker",
    )
    worker.run_once()
    raise AssertionError("crash provider unexpectedly returned")


def transitions(request_id: UUID) -> list[str]:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT to_lifecycle
            FROM anima_intelligence_transitions
            WHERE request_id=%s
            ORDER BY transition_id
            """,
            (request_id,),
        )
        return [str(row[0]) for row in cursor.fetchall()]


def expire(request_id: UUID) -> None:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE anima_intelligence_requests
            SET lease_expires_at=now() - interval '1 second', updated_at=now()
            WHERE request_id=%s
            """,
            (request_id,),
        )
        connection.commit()


def make_request(request_id: UUID) -> IntelligenceRequest:
    return IntelligenceRequest(
        request_id=request_id,
        household_id=HOUSEHOLD_ID,
        origin=IntelligenceOrigin.DIRECT_SENTRY_INTERACTION,
        context_packet_id=uuid4(),
        context_digest="phase14-context",
        catalogue_digest="phase14-catalogue",
        provider_id="sentry",
        provider_version="1",
        idempotency_key=f"phase14-sentry-crash:{request_id}",
        request_metadata={
            "direct_context": {
                "household_id": str(HOUSEHOLD_ID),
                "request": "phase14 provider crash boundary",
            }
        },
        catalogue=(),
    )


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        return child(UUID(sys.argv[2]), Path(os.environ["ANIMA_CRASH_MARKER"]))

    migrate(DATABASE_URL, 5)
    request_id = uuid4()
    request = make_request(request_id)
    store = PostgresIntelligenceStore(DATABASE_URL)
    stored = store.enqueue(request)
    marker = Path(f"/tmp/anima-phase14-sentry-crash-{request_id}.json")
    environment = {
        **os.environ,
        "ANIMA_DATABASE_URL": DATABASE_URL,
        "ANIMA_CRASH_MARKER": str(marker),
    }
    result = subprocess.run(
        [sys.executable, __file__, "--child", str(request_id)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 77, result.stderr
    current = store.get(stored.request_id)
    assert current is not None
    assert current.lifecycle == IntelligenceLifecycle.PROVIDER_RUNNING
    assert current.provider_invocation_started is True
    assert marker.exists()
    trace = transitions(stored.request_id)
    assert trace[-2:] == ["DELIVERED_TO_PROVIDER", "PROVIDER_RUNNING"], trace

    expire(stored.request_id)
    # The queue-level reclaim pass durably reconciles every expired started
    # request before selecting new work.  It is intentionally used here
    # rather than a specific claim: claim_specific() correctly refuses an
    # expired provider-running request, while an accumulated qualification
    # database may also contain unrelated pending SENTRY work.
    reclaimer = store.claim(
        "phase14-sentry-reclaimer",
        provider_id="sentry",
        household_id=HOUSEHOLD_ID,
    )
    assert reclaimer is None or reclaimer.request_id != stored.request_id
    recovered = store.get(stored.request_id)
    assert recovered is not None
    assert recovered.lifecycle == IntelligenceLifecycle.UNKNOWN_RESULT
    assert recovered.provider_invocation_started is True
    assert transitions(stored.request_id)[-1] == "UNKNOWN_RESULT"

    print(
        json.dumps(
            {
                "scenario_id": "SENTRY_PROVIDER_STARTED_CRASH_NO_REPLAY",
                "status": "PASS",
                "evidence_level": "POSTGRES_PROCESS",
                "provider_start_before_model": True,
                "model_callback_started": True,
                "pre_crash_lifecycle": "PROVIDER_RUNNING",
                "recovered_lifecycle": recovered.lifecycle.value,
                "reclaim_result": "NONE" if reclaimer is None else "UNRELATED_PENDING_WORK",
                "provider_invocations_after_recovery": 0,
                "embedded_agent_runtime": False,
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    marker.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
