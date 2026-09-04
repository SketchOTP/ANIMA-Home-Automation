"""MCP transport for the credential-isolated ANIMA household client."""

from __future__ import annotations

from typing import Any

from anima_household_client import AnimaHouseholdClient
from mcp.server import MCPServer

server = MCPServer(name="anima_household", version="0.2.0")
_CLIENT: AnimaHouseholdClient | None = None
_INTERACTION: dict[str, str] = {}


def _client() -> AnimaHouseholdClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AnimaHouseholdClient()
    return _CLIENT


@server.tool(name="anima_health", description="Return ANIMA household service health")
def anima_health() -> dict[str, Any]:
    return _client().call("/v1/health")


@server.tool(name="anima_open_interaction", description="Open one server-bound ANIMA interaction")
def anima_open_interaction(
    sentry_request_id: str, source_surface: str = "sentry"
) -> dict[str, Any]:
    value = _client().open_interaction(sentry_request_id, source_surface)
    if value.get("status") == "CLAIMED":
        _INTERACTION.update(request_id=str(value["request_id"]), binding=str(value["binding"]))
    return value


@server.tool(
    name="anima_open_direct_interaction", description="Create one direct SENTRY household request"
)
def anima_open_direct_interaction(
    sentry_request_id: str,
    user_text: str,
    source_surface: str = "sentry",
    identity_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = _client().open_direct_interaction(
        sentry_request_id, source_surface, user_text, identity_observation
    )
    if value.get("status") == "CLAIMED":
        _INTERACTION.update(request_id=str(value["request_id"]), binding=str(value["binding"]))
    return value


def _bound(request_id: str) -> str:
    if _INTERACTION.get("request_id") != request_id:
        raise RuntimeError("ANIMA interaction is not open for this request")
    return _INTERACTION["binding"]


@server.tool(name="anima_get_context", description="Get sparse context for the bound interaction")
def anima_get_context(request_id: str) -> dict[str, Any]:
    return _client().context(request_id, _bound(request_id))


@server.tool(name="anima_list_tools", description="List tools bound to this interaction")
def anima_list_tools(request_id: str) -> dict[str, Any]:
    return _client().tools(request_id, _bound(request_id))


@server.tool(name="anima_invoke", description="Invoke one request-bound semantic household tool")
def anima_invoke(
    request_id: str, tool_id: str, arguments: dict[str, Any], ordinal: int = 1
) -> dict[str, Any]:
    return _client().invoke(request_id, _bound(request_id), tool_id, arguments, ordinal)


@server.tool(name="anima_submit_result", description="Submit one bounded SENTRY result")
def anima_submit_result(
    request_id: str,
    status: str,
    response: str | None = None,
    detail: str | None = None,
    provider_ambiguous: bool = False,
) -> dict[str, Any]:
    return _client().submit_result(
        request_id,
        _bound(request_id),
        status=status,
        response=response,
        detail=detail,
        provider_ambiguous=provider_ambiguous,
    )


@server.tool(name="anima_renew", description="Renew the active ANIMA interaction lease")
def anima_renew(request_id: str) -> dict[str, Any]:
    return _client().renew(request_id, _bound(request_id))


@server.tool(
    name="anima_provider_start", description="Fence provider execution before SENTRY reasoning"
)
def anima_provider_start(request_id: str) -> dict[str, Any]:
    return _client().provider_start(request_id, _bound(request_id))


@server.tool(name="anima_status", description="Get exact bounded request status")
def anima_status(request_id: str) -> dict[str, Any]:
    return _client().status(request_id, _bound(request_id))


def main() -> int:
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
