"""Deterministic H5 Core/browser-boundary evidence.

The target keeps the real ``create_app`` composition, PostgreSQL sessions and
stores, OPA, Journal, Attention, Context Broker, AgentRuntime, and Plugin
Manager.  Only the model and external HTTP transport are deterministic test
seams.  It proves the boundaries that cannot be established by CSS or a
frontend-only test: restricted-content non-retention, external audit/health,
and reuse of the original session after application reconstruction.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
import psycopg
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from anima_ha.agent import (
    CodexTurnResult,
    FinalDecision,
    ScriptedCodexAdapter,
    TokenUsage,
    ToolRequestDecision,
)
from anima_ha.fixtures import sample_household_document
from anima_ha.graph import PostgresHouseholdGraph, ProviderReference
from anima_ha.ui_api import UI_SESSION_COOKIE, create_app

DATABASE_URL = os.environ.get(
    "ANIMA_DATABASE_URL", "postgresql://anima:anima_dev_only@127.0.0.1:55432/anima"
)
OPA_URL = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
HA_SCOPE = "phase12-h5-browser"
HA_USER_ID = "test-ha-user"
RESTRICTED_SENTINEL = f"H5-RESTRICTED-{uuid4()}"


def _commission_identity(graph: PostgresHouseholdGraph) -> None:
    document = sample_household_document()
    graph.commission(document)
    person = next(node for node in document.nodes if node.name == "Sam")
    graph.map_provider_reference(
        ProviderReference(
            uuid5(NAMESPACE_URL, f"anima:{HA_SCOPE}:{HA_USER_ID}"),
            "home_assistant",
            HA_SCOPE,
            "user",
            HA_USER_ID,
            person.canonical_id,
        ),
        allow_remap=True,
    )


def _external_handler(*, fail_weather: bool = False) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.open-meteo.com":
            if fail_weather:
                return httpx.Response(503, request=request, json={"error": "synthetic outage"})
            return httpx.Response(
                200,
                request=request,
                json={
                    "timezone": "UTC",
                    "current": {"temperature_2m": 17, "weather_code": 1},
                    "current_units": {"temperature_2m": "°C"},
                    "daily": {},
                },
            )
        if request.url.host == "api.upcitemdb.com":
            items = [
                {
                    "ean": f"00000000000{i}",
                    "title": f"Synthetic H5 product {i}",
                    "brand": "ANIMA Fixture",
                    "model": f"H5-{i}",
                    "category": "household",
                    "description": RESTRICTED_SENTINEL if i == 1 else "bounded fixture data",
                    "color": "ember",
                    "offers": [],
                }
                for i in range(1, 4)
            ]
            return httpx.Response(
                200,
                request=request,
                headers={
                    "X-RateLimit-Limit": "100",
                    "X-RateLimit-Remaining": "99",
                    "X-RateLimit-Reset": "60",
                },
                json={"items": items},
            )
        return httpx.Response(404, request=request, json={"error": "not configured"})

    return httpx.MockTransport(handle)


def _app(responses: list[CodexTurnResult], transport: httpx.BaseTransport) -> Any:
    os.environ["ANIMA_DATABASE_URL"] = DATABASE_URL
    os.environ["ANIMA_OPA_URL"] = OPA_URL
    os.environ["ANIMA_HA_PROVIDER_SCOPE"] = HA_SCOPE
    return create_app(
        codex=ScriptedCodexAdapter(responses),
        external_transport=transport,
    )


def _session(app: Any) -> tuple[TestClient, dict[str, str]]:
    service = app.state.ui_service
    identity = service.map_ha_user(HA_USER_ID)
    cookie, csrf = service.issue_session(identity, "h5-browser")
    client = TestClient(app)
    client.cookies.set(UI_SESSION_COOKIE, cookie)
    return client, {"X-Anima-CSRF": csrf, "Origin": "http://testserver"}


def _conversation_turn(tool_id: str, arguments: dict[str, Any]) -> CodexTurnResult:
    return CodexTurnResult(ToolRequestDecision(tool_id, arguments), TokenUsage(), 1.0, ())


def _final(text: str) -> CodexTurnResult:
    return CodexTurnResult(FinalDecision("DONE", True, text, "done"), TokenUsage(), 1.0, ())


def _assert_success(response: Any) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("status") == "SUCCEEDED", body
    return body


def _db_sentinel_hits() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT table_name, column_name
                   FROM information_schema.columns
                   WHERE table_schema='public' AND table_name LIKE 'anima_%'
                     AND data_type IN ('text','character varying','json','jsonb')"""
            )
            for column in cursor.fetchall():
                table = str(column["table_name"])
                name = str(column["column_name"])
                cursor.execute(
                    f'SELECT count(*) AS count FROM "{table}" WHERE "{name}"::text LIKE %s',
                    (f"%{RESTRICTED_SENTINEL}%",),
                )
                row = cursor.fetchone()
                if row and int(row["count"]):
                    hits.append((table, name))
    return hits


def _latest_external_audit() -> dict[str, Any]:
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT payload FROM anima_event_journal
                   WHERE event_type='external.request.audit'
                   ORDER BY journal_position DESC LIMIT 1"""
            )
            row = cursor.fetchone()
    assert row is not None
    return dict(row["payload"])


def main() -> int:
    _commission_identity(PostgresHouseholdGraph(DATABASE_URL))

    # Restricted product content travels through the real AgentRuntime and is
    # returned live, while its unique text is projected out of durable state.
    restricted_tool = "anima.external.shopping.upcitemdb.search_products"
    restricted_app = _app(
        [
            _conversation_turn(restricted_tool, {"query": "h5 restricted sentinel", "count": 3}),
            _final(f"Live product response contains {RESTRICTED_SENTINEL}."),
        ],
        _external_handler(),
    )
    restricted_client, restricted_headers = _session(restricted_app)
    restricted = restricted_client.post(
        "/api/v1/conversation",
        json={"text": "Find products for the H5 restricted-content test."},
        headers=restricted_headers,
    )
    assert restricted.status_code == 200, restricted.text
    live_response = restricted.json()["response"]
    assert RESTRICTED_SENTINEL in live_response
    assert _db_sentinel_hits() == []
    restricted_storage = {
        "browser_persistence": (
            "separate Playwright storage inventory; restricted-response lifecycle "
            "remains a browser evidence gap"
        ),
        "postgres_sentinel_hits": [],
    }

    # External audit and health use the Core composition.  The first app sees a
    # deterministic provider outage; a reconstructed app reuses the same
    # cookie and then observes recovery from the successful audit.
    weather_tool = "anima.external.weather.get"
    outage_app = _app(
        [
            _conversation_turn(weather_tool, {"latitude": 40.0, "longitude": -74.0}),
            _final("Weather provider failed safely."),
        ],
        _external_handler(fail_weather=True),
    )
    outage_client, outage_headers = _session(outage_app)
    outage_response = outage_client.post(
        "/api/v1/conversation",
        json={"text": "Run the H5 provider failure probe."},
        headers=outage_headers,
    )
    assert outage_response.status_code == 200, outage_response.text
    outage_capabilities = outage_client.get("/api/v1/capabilities").json()["items"]
    weather_outage = next(item for item in outage_capabilities if item["id"] == "weather")
    assert weather_outage["state"] == "degraded", weather_outage
    audit = _latest_external_audit()
    assert RESTRICTED_SENTINEL not in json.dumps(audit, sort_keys=True)

    recovery_app = _app(
        [
            _conversation_turn(weather_tool, {"latitude": 40.0, "longitude": -74.0}),
            _final("Fresh weather is available."),
        ],
        _external_handler(),
    )
    recovery_client = TestClient(recovery_app)
    original_cookie = outage_client.cookies.get(UI_SESSION_COOKIE)
    assert original_cookie is not None
    recovery_client.cookies.set(UI_SESSION_COOKIE, original_cookie)
    recovered_bootstrap = recovery_client.get("/api/v1/bootstrap")
    assert recovered_bootstrap.status_code == 200, recovered_bootstrap.text
    recovery_headers = {
        "X-Anima-CSRF": recovered_bootstrap.json()["csrf_token"],
        "Origin": "http://testserver",
    }
    assert recovery_client.get("/api/v1/settings").status_code == 200
    recovery_response = recovery_client.post(
        "/api/v1/conversation",
        json={"text": "Run the H5 provider recovery probe."},
        headers=recovery_headers,
    )
    assert recovery_response.status_code == 200, recovery_response.text
    recovered_capabilities = recovery_client.get("/api/v1/capabilities").json()["items"]
    weather_recovered = next(item for item in recovered_capabilities if item["id"] == "weather")
    assert weather_recovered["state"] == "available", weather_recovered

    # The original cookie remains valid after reconstruction, and a post-restart
    # mutation uses one durable task identity rather than a replacement session.
    title = f"H5 restart task {uuid4()}"
    task = _assert_success(
        recovery_client.post(
            "/api/v1/tasks",
            json={
                "payload": {
                    "title": title,
                    "when": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                    "note": "same browser session after restart",
                }
            },
            headers=recovery_headers,
        )
    )
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM anima_durable_tasks WHERE title=%s", (title,))
        count = int(cursor.fetchone()[0])
    assert count == 1

    print(
        json.dumps(
            {
                "composition": "create_app_postgres_core",
                "restricted_live_response": True,
                "restricted_storage": restricted_storage,
                "external_audit": {
                    "event_type": "external.request.audit",
                    "sentinel_absent": RESTRICTED_SENTINEL not in json.dumps(audit, sort_keys=True),
                },
                "provider_health": {
                    "failure": weather_outage["state"],
                    "recovery": weather_recovered["state"],
                },
                "original_session_survived_reconstruction": True,
                "post_restart_mutation": {"status": task["status"], "durable_task_count": count},
                "phase13": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
