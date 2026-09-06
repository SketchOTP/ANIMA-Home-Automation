"""Ephemeral SENTRY result delivery across the ANIMA processes.

SENTRY result text is not written to the durable intelligence request row.
The Core service publishes a bounded notification and the UI process keeps it
only in memory for a short delivery window.  If the UI was not listening, the
response is honestly unavailable rather than reconstructed from durable
household or provider content.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg

CHANNEL = "anima_sentry_live_result"
LIVE_RESULT_TTL_SECONDS = 300.0
MAX_NOTIFY_BYTES = 7_500


def _bounded_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep the notification bounded without changing durable semantics."""

    result = {
        "request_id": str(payload.get("request_id", "")),
        "household_id": str(payload.get("household_id", "")),
        "status": str(payload.get("status", "UNKNOWN_RESULT")),
        "response": payload.get("response"),
        "detail": payload.get("detail"),
        "provider_ambiguous": bool(payload.get("provider_ambiguous", False)),
    }
    encoded = json.dumps(result, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) <= MAX_NOTIFY_BYTES:
        return result
    response = result.get("response")
    if isinstance(response, str):
        budget = min(6_500, len(response.encode("utf-8")))
        result["response"] = response.encode("utf-8")[:budget].decode("utf-8", "ignore")
        result["detail"] = "SENTRY response was bounded for live delivery"
    return result


class PostgresSentryLivePublisher:
    """Publish one response through PostgreSQL's non-durable notification bus."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def publish(self, payload: dict[str, Any]) -> None:
        bounded = _bounded_payload(payload)
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute(
                "SELECT pg_notify(%s, %s)",
                (CHANNEL, json.dumps(bounded, ensure_ascii=True, separators=(",", ":"))),
            )


class PostgresSentryLiveResultBus:
    """Receive non-durable SENTRY results for the local UI process."""

    def __init__(
        self,
        database_url: str,
        *,
        on_result: Callable[[], None] | None = None,
        ttl_seconds: float = LIVE_RESULT_TTL_SECONDS,
    ) -> None:
        self.database_url = database_url
        self.on_result = on_result
        self.ttl_seconds = ttl_seconds
        self._results: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._listen, name="anima-sentry-live-results", daemon=True
        )
        self._thread.start()

    def _listen(self) -> None:
        try:
            with psycopg.connect(self.database_url, autocommit=True) as connection:
                connection.execute(f"LISTEN {CHANNEL}")
                while not self._stop.is_set():
                    for notification in connection.notifies(timeout=0.5):
                        try:
                            payload = json.loads(notification.payload)
                            request_id = str(payload["request_id"])
                            UUID(request_id)
                            household_id = str(payload["household_id"])
                            UUID(household_id)
                        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                            continue
                        with self._lock:
                            self._results[request_id] = (
                                time.monotonic() + self.ttl_seconds,
                                payload,
                            )
                        if self.on_result is not None:
                            self.on_result()
        except (OSError, psycopg.Error):
            # A missing database/listener is a truthful live-response gap. It
            # must not make the rest of the UI unavailable or create a fake
            # response path.
            return

    def get(self, request_id: UUID, household_id: UUID) -> dict[str, Any] | None:
        key = str(request_id)
        now = time.monotonic()
        with self._lock:
            current = self._results.get(key)
            if current is None:
                return None
            expires_at, payload = current
            if expires_at <= now:
                del self._results[key]
                return None
            if payload.get("household_id") != str(household_id):
                return None
            return dict(payload)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)


def live_result_payload(
    *,
    request_id: UUID,
    household_id: UUID,
    status: str,
    response: str | None,
    detail: str | None,
    provider_ambiguous: bool,
) -> dict[str, Any]:
    """Build the cross-process payload without retaining it durably."""

    return {
        "request_id": str(request_id),
        "household_id": str(household_id),
        "status": status,
        "response": response,
        "detail": detail,
        "provider_ambiguous": provider_ambiguous,
        "published_at": datetime.now(UTC).isoformat(),
    }
