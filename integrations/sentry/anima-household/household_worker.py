"""Persistent queue consumer. Only the authenticated ANIMA client claims work."""

from __future__ import annotations

import argparse
import json
import signal
import threading
import time
from typing import Any
from uuid import uuid4

from anima_household_client import AnimaHouseholdClient, AnimaHouseholdError
from codex_model import (
    FINAL_SCHEMA,
    MODEL,
    CodexHouseholdModel,
    CodexUnavailable,
    diagnostic_error,
)
from sentry_turn import TURN_SECONDS, SentryHouseholdTurn


class ActiveLease:
    """Called only by an active model subprocess, never an idle keepalive."""

    def __init__(self, client: AnimaHouseholdClient, opened: dict[str, Any], stop: threading.Event):
        self.client = client
        self.opened = opened
        self.stop = stop
        self.next_renewal = 0.0

    def __call__(self) -> None:
        if self.stop.is_set():
            raise CodexUnavailable("WORKER_STOPPED")
        if time.monotonic() < self.next_renewal:
            return
        try:
            result = self.client.renew(self.opened["request_id"], self.opened["binding"])
        except AnimaHouseholdError:
            raise CodexUnavailable("ANIMA_LEASE_UNAVAILABLE") from None
        if result.get("status") != "RENEWED":
            raise CodexUnavailable("ANIMA_LEASE_LOST")
        self.next_renewal = time.monotonic() + 20


class HouseholdWorker:
    def __init__(
        self,
        client: AnimaHouseholdClient,
        model: CodexHouseholdModel,
        *,
        stop: threading.Event | None = None,
    ):
        self.client = client
        self.model = model
        self.stop = stop if stop is not None else threading.Event()

    def run_once(self) -> dict[str, Any]:
        # No claims while authentication is known unavailable. Login status
        # does not prove that the server will accept the next model request.
        if not self.model.check_auth():
            raise CodexUnavailable("CODEX_AUTH_UNAVAILABLE")
        if self.stop.is_set():
            return {"status": "STOPPED"}
        correlation = f"anima-household-{uuid4()}"
        deadline = time.monotonic() + TURN_SECONDS
        opened = self.client.open_interaction(correlation, "anima-household-worker")
        if opened.get("status") == "EMPTY":
            return {"status": "IDLE"}
        if (
            opened.get("status") != "CLAIMED"
            or opened.get("provider_id") != "sentry"
            or not opened.get("request_id")
            or not opened.get("binding")
        ):
            raise CodexUnavailable("ANIMA_INVALID_CLAIM")
        self.model.heartbeat = ActiveLease(self.client, opened, self.stop)
        turn = SentryHouseholdTurn(
            self.client,
            self.model,
            sentry_request_id=correlation,
            source_surface="anima-household-worker",
            deadline=deadline,
        )
        try:
            result = turn.run(opened)
            if result.get("status") != "RECORDED":
                raise CodexUnavailable("ANIMA_RESULT_UNCONFIRMED")
            # Never log or persist context, tool results, binding or response.
            return {"status": "RECORDED"}
        except Exception as exc:
            code = str(exc) if isinstance(exc, CodexUnavailable) else "ANIMA_TURN_UNAVAILABLE"
            stage = turn.diagnostic_stage
            if stage in {"MODEL_PLAN", "MODEL_FINAL"}:
                stage = getattr(self.model, "diagnostic_stage", stage)
            error = diagnostic_error(exc, stage, code)
            diagnostic = {
                "status": "TURN_DIAGNOSTIC",
                "stage": error.diagnostic_stage,
                "exception_type": error.exception_type,
            }
            if code == "CODEX_AUTH_UNAVAILABLE":
                invalidate = getattr(self.model, "invalidate_auth_cache", None)
                if callable(invalidate):
                    invalidate()
            if isinstance(exc, AnimaHouseholdError):
                diagnostic.update(exc.safe_diagnostics())
            # Emit before the one-shot terminal submission, which may fail.
            # No exception message/args, request data, output, or traceback.
            print(json.dumps(diagnostic), flush=True)
            auth_only = code == "CODEX_AUTH_UNAVAILABLE" and not turn.tool_invocation_started
            turn.finalize_failure_journal(code)
            # One bounded submission only. A lost lease or failed delivery is
            # left to Core expiry; never replay provider calls or tool invocations.
            try:
                if not turn.result_submission_started:
                    self.client.submit_result(
                        opened["request_id"],
                        opened["binding"],
                        status="UNAVAILABLE" if auth_only else "UNKNOWN_RESULT",
                        detail=code
                        + ";"
                        + ";".join(
                            f"{key}={value}" for key, value in diagnostic.items() if key != "status"
                        ),
                        provider_ambiguous=not auth_only,
                    )
            except Exception as delivery_exc:
                delivery = diagnostic_error(delivery_exc, "FAILURE_SUBMIT", code)
                delivery_fields = (
                    delivery_exc.safe_diagnostics()
                    if isinstance(delivery_exc, AnimaHouseholdError)
                    else {}
                )
                print(
                    json.dumps(
                        {
                            "status": "TURN_DIAGNOSTIC",
                            "stage": delivery.diagnostic_stage,
                            "exception_type": delivery.exception_type,
                            **delivery_fields,
                        }
                    ),
                    flush=True,
                )
            raise error from None
        finally:
            self.model.heartbeat = lambda: None
            setter = getattr(self.model, "set_deadline", None)
            if callable(setter):
                setter(None)


def main() -> int:
    parser = argparse.ArgumentParser(description="SENTRY host worker for ANIMA queued requests")
    parser.add_argument("--once", action="store_true", help="claim at most one queued request")
    parser.add_argument(
        "--check", action="store_true", help="check CLI auth and Core health without claiming"
    )
    parser.add_argument(
        "--auth-smoke",
        action="store_true",
        help="one synthetic no-tools model call; no Core request",
    )
    parser.add_argument("--poll-seconds", type=float, default=2)
    parser.add_argument("--model-timeout", type=float, default=90)
    args = parser.parse_args()
    if not 0.5 <= args.poll_seconds <= 60 or not 1 <= args.model_timeout <= 300:
        parser.error("poll must be 0.5-60 seconds; model timeout must be 1-300 seconds")
    if sum((args.check, args.once, args.auth_smoke)) > 1:
        parser.error("choose at most one of --check, --once, --auth-smoke")
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda _signum, _frame: stop.set())
    try:
        model = CodexHouseholdModel(timeout=args.model_timeout)
        if not model.check_auth():
            raise CodexUnavailable("CODEX_AUTH_UNAVAILABLE")
        if args.auth_smoke:

            def cancelled() -> None:
                if stop.is_set():
                    raise CodexUnavailable("WORKER_STOPPED")

            model.heartbeat = cancelled
            model.run(
                "Synthetic read-only authentication check. Return response: ready.", FINAL_SCHEMA
            )
            print(json.dumps({"status": "MODEL_AUTH_OBSERVED", "model": MODEL}))
            return 0
        client = AnimaHouseholdClient(timeout=10)
        if args.check:
            health = client.call("/v1/health")
            if health.get("state") != "available":
                raise CodexUnavailable("ANIMA_CORE_UNAVAILABLE")
            print(
                json.dumps({"status": "READY", "auth": "CHATGPT_LOGIN_STATUS_ONLY", "model": MODEL})
            )
            return 0
        worker = HouseholdWorker(client, model, stop=stop)
        print(json.dumps({"status": "WORKER_STARTED", "model": MODEL}), flush=True)
        consecutive_failures = 0
        while not stop.is_set():
            try:
                result = worker.run_once()
            except CodexUnavailable as exc:
                if args.once:
                    raise
                consecutive_failures += 1
                print(
                    json.dumps(
                        {
                            "status": "WORKER_RECOVERING",
                            "reason": str(exc),
                            "attempt": min(consecutive_failures, 10),
                        }
                    ),
                    flush=True,
                )
                stop.wait(min(30.0, max(args.poll_seconds, 2 ** min(consecutive_failures, 4))))
                continue
            except (AnimaHouseholdError, OSError):
                if args.once:
                    raise
                consecutive_failures += 1
                print(
                    json.dumps(
                        {
                            "status": "WORKER_RECOVERING",
                            "reason": "ANIMA_CLIENT_UNAVAILABLE",
                            "attempt": min(consecutive_failures, 10),
                        }
                    ),
                    flush=True,
                )
                stop.wait(min(30.0, max(args.poll_seconds, 2 ** min(consecutive_failures, 4))))
                continue
            consecutive_failures = 0
            if result["status"] != "IDLE":
                print(json.dumps(result), flush=True)
            if args.once:
                return 0
            stop.wait(args.poll_seconds)
        return 0
    except CodexUnavailable as exc:
        print(json.dumps({"status": "UNAVAILABLE", "reason": str(exc)}), flush=True)
        return 2
    except (AnimaHouseholdError, OSError):
        print(
            json.dumps({"status": "UNAVAILABLE", "reason": "ANIMA_CLIENT_UNAVAILABLE"}), flush=True
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
