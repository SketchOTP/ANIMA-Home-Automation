"""ANIMA-owned stdio MCP surface for the SENTRY process.

The server is intentionally a thin transport adapter.  It does not expose
PostgreSQL, Home Assistant, raw provider HTTP, secrets, shell, or arbitrary
plugin execution.  Every operation delegates to :class:`CoreSentryBoundary`.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from mcp.server import MCPServer

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceResult,
    IntelligenceResultStatus,
)
from anima_ha.sentry_boundary import CoreSentryBoundary
from anima_ha.ui_runtime import build_postgres_core

server = MCPServer(name="anima-sentry-core", version="0.1.0")
_BOUNDARY: CoreSentryBoundary | None = None


def _boundary() -> CoreSentryBoundary:
    global _BOUNDARY
    if _BOUNDARY is not None:
        return _BOUNDARY
    database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    _BOUNDARY = build_postgres_core(
        database_url,
        opa_url=os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:8181"),
    ).sentry_boundary()
    return _BOUNDARY


def _worker_id() -> str:
    configured = os.environ.get("ANIMA_SENTRY_WORKER_ID", "").strip()
    if not configured:
        raise RuntimeError("ANIMA_SENTRY_WORKER_ID is required")
    return configured


@server.tool(name="anima_health", description="Return ANIMA Core/SENTRY boundary health")
def anima_health() -> dict[str, Any]:
    return _boundary().health().to_payload()


@server.tool(
    name="anima_claim_intelligence", description="Claim one durable ANIMA reasoning request"
)
def anima_claim_intelligence() -> dict[str, Any]:
    boundary = _boundary()
    worker_id = _worker_id()
    request = boundary.claim_request(worker_id)
    if request is None:
        return {"status": "EMPTY"}
    if not boundary.intelligence_store.transition(
        request.request_id,
        worker_id,
        request.fencing_generation,
        IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
    ):
        raise RuntimeError("INTELLIGENCE_CLAIM_LOST")
    return {
        "status": "CLAIMED",
        "request_id": str(request.request_id),
        "household_id": str(request.household_id),
        "origin": request.origin.value,
        "trigger_id": str(request.trigger_id) if request.trigger_id else None,
        "context_packet_id": str(request.context_packet_id),
        "context_digest": request.context_digest,
        "catalogue_digest": request.catalogue_digest,
        "provider_id": request.provider_id,
        "provider_version": request.provider_version,
        "fencing_generation": request.fencing_generation,
        "request_metadata": request.request_metadata,
    }


@server.tool(
    name="anima_get_intelligence_context",
    description="Get the exact sparse context for a claimed request",
)
def anima_get_intelligence_context(request_id: str) -> dict[str, Any]:
    boundary = _boundary()
    request = boundary.intelligence_store.get(UUID(request_id))
    if request is None or request.claim_owner != _worker_id():
        raise ValueError("INTELLIGENCE_REQUEST_NOT_OWNED")
    return boundary.request_context(request)


@server.tool(
    name="anima_list_registered_tools",
    description="List the bounded ANIMA semantic tool catalogue",
)
def anima_list_registered_tools() -> list[dict[str, Any]]:
    return _boundary().catalogue()


@server.tool(name="anima_invoke_tool", description="Invoke one registered ANIMA semantic tool")
def anima_invoke_tool(
    request_id: str, tool_id: str, arguments: dict[str, Any], ordinal: int = 1
) -> dict[str, Any]:
    boundary = _boundary()
    request = boundary.intelligence_store.get(UUID(request_id))
    if request is None or request.claim_owner != _worker_id():
        raise ValueError("INTELLIGENCE_REQUEST_NOT_OWNED")
    if request.lifecycle == IntelligenceLifecycle.DELIVERED_TO_PROVIDER:
        if not boundary.intelligence_store.transition(
            request.request_id,
            _worker_id(),
            request.fencing_generation,
            IntelligenceLifecycle.PROVIDER_RUNNING,
        ):
            raise RuntimeError("INTELLIGENCE_CLAIM_LOST")
    return boundary.invoke_tool(request, tool_id, arguments, ordinal=ordinal)


@server.tool(
    name="anima_submit_intelligence_result",
    description="Submit a bounded structured SENTRY result",
)
def anima_submit_intelligence_result(
    request_id: str,
    status: str,
    response: str | None = None,
    detail: str | None = None,
    action_references: list[str] | None = None,
    provider_ambiguous: bool = False,
) -> dict[str, Any]:
    boundary = _boundary()
    request = boundary.intelligence_store.get(UUID(request_id))
    if request is None or request.claim_owner != _worker_id():
        raise ValueError("INTELLIGENCE_REQUEST_NOT_OWNED")
    result = IntelligenceResult(
        request.request_id,
        IntelligenceResultStatus(status),
        response_text=response,
        detail=detail,
        action_references=tuple(action_references or ()),
        provider_ambiguous=provider_ambiguous,
    )
    accepted = boundary.submit_result(request, _worker_id(), result)
    return {"status": "RECORDED" if accepted else "CLAIM_LOST", "request_id": request_id}


def main() -> int:
    database_url = os.environ.get("ANIMA_DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("ANIMA_DATABASE_URL is required")
    migrate(database_url, 5)
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
