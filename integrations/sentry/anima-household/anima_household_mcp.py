"""MCP transport for the credential-isolated ANIMA household client."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Annotated, Any
from uuid import UUID

from anima_household_client import AnimaHouseholdClient
from mcp.types import ToolAnnotations
from pydantic import Field

_READ_ANNOTATIONS = ToolAnnotations.model_validate(
    {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}
)
_INVOKE_ANNOTATIONS = ToolAnnotations.model_validate(
    {"readOnlyHint": False, "destructiveHint": True, "openWorldHint": True}
)

try:
    # MCP 2.x renamed the v1 FastMCP server to MCPServer.
    from mcp.server import MCPServer as _MCPServer

    server = _MCPServer(name="anima_household", version="0.2.0")
except ImportError:
    # SENTRY's currently installed host runtime still exposes the v1 name.
    from mcp.server.fastmcp import FastMCP as _MCPServer  # type: ignore[attr-defined,no-redef]

    server = _MCPServer(name="anima_household")

_CLIENT: AnimaHouseholdClient | None = None
_INTERACTION: dict[str, str] = {}
_PREBOUND_PATH = os.environ.get("ANIMA_PREBOUND_FILE")
_PREBOUND: dict[str, Any] | None = None
_CALLS: dict[int, tuple[str, dict[str, Any] | None]] = {}
_CATALOGUE: dict[str, Any] | None = None
_LOCK = RLock()
_RESTRICTED = "EPHEMERAL_RESTRICTED"
_STATUS_RANK = {
    "READY": 0,
    "SUCCEEDED": 1,
    "PARTIAL": 2,
    "UNAVAILABLE": 3,
    "FAILED": 4,
    "WAITING_CONFIRMATION": 5,
    "WAITING_STRONGER_AUTH": 6,
    "UNKNOWN_RESULT": 7,
}


def _private_json(path: Path, *, maximum_bytes: int = 65536) -> dict[str, Any]:
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)) as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_uid != os.geteuid()
                or info.st_size > maximum_bytes
            ):
                raise ValueError
            raw = stream.read(maximum_bytes + 1)
        value = json.loads(raw)
        if len(raw.encode()) > maximum_bytes or not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, UnicodeError):
        raise RuntimeError("ANIMA_PREBOUND_FILE_INVALID") from None


def _prebound() -> dict[str, Any]:
    global _PREBOUND
    try:
        path = Path(_PREBOUND_PATH or "")
        if not path.is_absolute():
            raise ValueError
        value = _private_json(path)
        required = {
            "version",
            "request_id",
            "binding",
            "sentry_request_id",
            "source_surface",
            "endpoint",
            "token_file",
            "worker_id",
            "expires_at",
            "persistent_thread",
            "workspace_root",
        }
        if set(value) != required or type(value["version"]) is not int or value["version"] != 1:
            raise ValueError
        if value["persistent_thread"] is not True:
            raise ValueError
        for key in required - {"version", "persistent_thread"}:
            if not isinstance(value[key], str) or not value[key] or len(value[key]) > 8192:
                raise ValueError
        UUID(value["request_id"])
        workspace = Path(value["workspace_root"])
        token = Path(value["token_file"])
        if not workspace.is_absolute() or not token.is_absolute():
            raise ValueError
        if path.resolve().is_relative_to(workspace.resolve()) or token.resolve().is_relative_to(
            workspace.resolve()
        ):
            raise ValueError
        parent = path.parent.stat()
        if stat.S_IMODE(parent.st_mode) != 0o700 or parent.st_uid != os.geteuid():
            raise ValueError
        expires = datetime.fromisoformat(value["expires_at"])
        if expires.tzinfo is None or expires <= datetime.now(UTC):
            raise ValueError
        if _PREBOUND is not None and value != _PREBOUND:
            raise ValueError
        _PREBOUND = value
        return value
    except (OSError, ValueError, TypeError):
        raise RuntimeError("ANIMA_PREBOUND_FILE_INVALID") from None


def _metadata() -> dict[str, Any]:
    _prebound()
    value = _private_json(Path(str(_PREBOUND_PATH)).with_name("metadata.json"))
    if (
        set(value) != {"version", "status", "calls"}
        or type(value["version"]) is not int
        or value["version"] != 1
        or value["status"] not in _STATUS_RANK
        or type(value["calls"]) is not int
        or not 0 <= value["calls"] <= 8
    ):
        raise RuntimeError("ANIMA_PREBOUND_METADATA_INVALID")
    return value


def _write_metadata(status: str, calls: int) -> None:
    _metadata()  # Refuse missing, replaced, or unsafe host-created state.
    target = Path(str(_PREBOUND_PATH)).with_name("metadata.json")
    fd, temporary = tempfile.mkstemp(prefix=".metadata-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"version": 1, "status": status, "calls": calls}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _restricted(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            (key in {"content_persistence", "content_class"} and item == _RESTRICTED)
            or _restricted(item)
            for key, item in value.items()
        )
    return isinstance(value, list) and any(_restricted(item) for item in value)


def _product_tool(tool_id: str) -> bool:
    return tool_id in {
        "anima.external.shopping.search_products",
        "anima.external.shopping.bestbuy.search_products",
        "anima.external.shopping.upcitemdb.search_products",
    }


def _filtered_catalogue(value: dict[str, Any]) -> dict[str, Any]:
    tools, unavailable = [], []
    for item in value.get("tools", []):
        if not isinstance(item, dict) or not isinstance(item.get("tool_id"), str):
            raise RuntimeError("ANIMA_PREBOUND_CATALOGUE_INVALID")
        if _product_tool(item["tool_id"]) or _restricted(item):
            unavailable.append(
                {
                    "tool_id": item["tool_id"],
                    "availability": False,
                    "unavailable_reason": "PERSISTENT_THREAD_RESTRICTED_CONTENT",
                }
            )
        else:
            tools.append(item)
    return {"tools": tools, "unavailable_tools": unavailable}


def _safe_result(value: dict[str, Any]) -> dict[str, Any]:
    if _PREBOUND_PATH is not None and _restricted(value):
        with _LOCK:
            metadata = _metadata()
            status = max((metadata["status"], "UNAVAILABLE"), key=_STATUS_RANK.__getitem__)
            _write_metadata(status, metadata["calls"])
        return {"status": "UNAVAILABLE", "reason": "PERSISTENT_THREAD_RESTRICTED_CONTENT"}
    return value


def _lifecycle_tool(**kwargs: Any) -> Callable[..., Any]:
    # A prebound model must not even discover host-owned lifecycle tools.
    if _PREBOUND_PATH is not None:
        return lambda function: function
    return server.tool(**kwargs)


def _host_lifecycle() -> None:
    if _PREBOUND_PATH is not None:
        raise RuntimeError("ANIMA_PREBOUND_HOST_OWNS_LIFECYCLE")


def _client() -> AnimaHouseholdClient:
    global _CLIENT
    bound = _prebound() if _PREBOUND_PATH is not None else None
    if _CLIENT is None:
        _CLIENT = (
            AnimaHouseholdClient(endpoint=bound["endpoint"], token_file=bound["token_file"])
            if bound
            else AnimaHouseholdClient()
        )
    return _CLIENT


def _preloaded(name: str, *, maximum_bytes: int = 512 * 1024) -> dict[str, Any] | None:
    if _PREBOUND_PATH is None:
        return None
    bound = _prebound()
    target = Path(_PREBOUND_PATH).with_name(f"{name}.json")
    # Direct voice bindings intentionally use live Core reads. Only the
    # autonomous host prepares request-frozen preload siblings.
    if not os.path.lexists(target):
        return None
    value = _private_json(target, maximum_bytes=maximum_bytes)
    if (
        set(value) != {"version", "request_id", "value"}
        or value.get("version") != 1
        or value.get("request_id") != bound["request_id"]
        or not isinstance(value.get("value"), dict)
    ):
        raise RuntimeError("ANIMA_PREBOUND_PRELOAD_INVALID")
    return deepcopy(value["value"])


@server.tool(
    name="anima_health",
    description="Return ANIMA household service health",
    annotations=_READ_ANNOTATIONS,
)
def anima_health() -> dict[str, Any]:
    value = _preloaded("health") or _client().call("/v1/health")
    if _PREBOUND_PATH is not None:
        value = {**_safe_result(value), "request_id": _prebound()["request_id"]}
    return value


@_lifecycle_tool(
    name="anima_open_interaction", description="Open one server-bound ANIMA interaction"
)
def anima_open_interaction(
    sentry_request_id: str, source_surface: str = "sentry"
) -> dict[str, Any]:
    _host_lifecycle()
    value = _client().open_interaction(sentry_request_id, source_surface)
    if value.get("status") == "CLAIMED":
        _INTERACTION.update(request_id=str(value["request_id"]), binding=str(value["binding"]))
    return value


@_lifecycle_tool(
    name="anima_open_direct_interaction", description="Create one direct SENTRY household request"
)
def anima_open_direct_interaction(
    sentry_request_id: str,
    user_text: str,
    source_surface: str = "sentry",
    identity_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _host_lifecycle()
    value = _client().open_direct_interaction(
        sentry_request_id, source_surface, user_text, identity_observation
    )
    if value.get("status") == "CLAIMED":
        _INTERACTION.update(request_id=str(value["request_id"]), binding=str(value["binding"]))
    return value


def _bound(request_id: str) -> str:
    if _PREBOUND_PATH is not None:
        value = _prebound()
        if request_id != value["request_id"]:
            raise RuntimeError("ANIMA_PREBOUND_REQUEST_MISMATCH")
        return str(value["binding"])
    if _INTERACTION.get("request_id") != request_id:
        raise RuntimeError("ANIMA interaction is not open for this request")
    return _INTERACTION["binding"]


@server.tool(
    name="anima_get_context",
    description="Get sparse context for the bound interaction",
    annotations=_READ_ANNOTATIONS,
)
def anima_get_context(request_id: str) -> dict[str, Any]:
    _bound(request_id)
    value = _preloaded("context") or _client().context(request_id, _bound(request_id))
    return _safe_result(value)


@server.tool(
    name="anima_list_tools",
    description="List tools bound to this interaction",
    annotations=_READ_ANNOTATIONS,
)
def anima_list_tools(request_id: str) -> dict[str, Any]:
    global _CATALOGUE
    if _PREBOUND_PATH is not None:
        with _LOCK:
            binding = _bound(request_id)
            if _CATALOGUE is None:
                value = _preloaded("tools") or _client().tools(request_id, binding)
                _CATALOGUE = deepcopy(_filtered_catalogue(value))
            return deepcopy(_CATALOGUE)
    value = _client().tools(request_id, _bound(request_id))
    return value


@server.tool(
    name="anima_invoke",
    description=(
        "Invoke one request-bound semantic household tool. Calls are 1-based: "
        "omit ordinal for the first call, then use 2 through 8 in order."
    ),
    annotations=_INVOKE_ANNOTATIONS,
)
def anima_invoke(
    request_id: str,
    tool_id: str,
    arguments: dict[str, Any],
    ordinal: Annotated[int, Field(ge=1, le=8)] = 1,
) -> dict[str, Any]:
    if _PREBOUND_PATH is not None:
        with _LOCK:
            _bound(request_id)
            # The binding inode is stable for the turn. Cross-process retries
            # serialize on it; only content-free ordinal counts are persisted.
            with os.fdopen(os.open(str(_PREBOUND_PATH), os.O_RDONLY | os.O_NOFOLLOW)) as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                metadata = _metadata()
                if type(ordinal) is not int or not 1 <= ordinal <= 8:
                    raise RuntimeError("ANIMA_PREBOUND_ORDINAL_INVALID")
                signature = json.dumps([tool_id, arguments], sort_keys=True, allow_nan=False)
                if ordinal in _CALLS:
                    previous, result = _CALLS[ordinal]
                    if previous == signature and result is not None:
                        return deepcopy(result)
                    raise RuntimeError("ANIMA_PREBOUND_ORDINAL_ALREADY_DISPATCHED")
                if metadata["status"] not in {"READY", "SUCCEEDED"}:
                    raise RuntimeError("ANIMA_PREBOUND_TURN_BLOCKED")
                if ordinal != metadata["calls"] + 1:
                    raise RuntimeError("ANIMA_PREBOUND_ORDINAL_INVALID")
                catalogue = anima_list_tools(request_id)
                matches = [item for item in catalogue["tools"] if item["tool_id"] == tool_id]
                if len(matches) != 1 or matches[0].get("availability") is not True:
                    status = max((metadata["status"], "UNAVAILABLE"), key=_STATUS_RANK.__getitem__)
                    _write_metadata(status, metadata["calls"])
                    return {
                        "status": "UNAVAILABLE",
                        "reason": "TOOL_UNAVAILABLE_IN_PERSISTENT_THREAD",
                    }
                _CALLS[ordinal] = (signature, None)
                _write_metadata("UNKNOWN_RESULT", ordinal)
                # Re-check revocation immediately before dispatch. An exception
                # leaves the ordinal spent and the host status conservative.
                result = _safe_result(
                    _client().invoke(request_id, _bound(request_id), tool_id, arguments, ordinal)
                )
                status = str(result.get("status", "UNKNOWN_RESULT"))
                status = {
                    "REQUIRE_CONFIRMATION": "WAITING_CONFIRMATION",
                    "REQUIRE_STRONGER_AUTH": "WAITING_STRONGER_AUTH",
                    "DENIED": "FAILED",
                    "POLICY_DENIED": "FAILED",
                    "VERIFICATION_FAILED": "PARTIAL",
                }.get(status, status)
                if status not in _STATUS_RANK or status == "READY":
                    status = "UNKNOWN_RESULT"
                status = max((metadata["status"], status), key=_STATUS_RANK.__getitem__)
                _write_metadata(status, ordinal)
                _CALLS[ordinal] = (signature, deepcopy(result))
                return result
    return _client().invoke(request_id, _bound(request_id), tool_id, arguments, ordinal)


@_lifecycle_tool(name="anima_submit_result", description="Submit one bounded SENTRY result")
def anima_submit_result(
    request_id: str,
    status: str,
    response: str | None = None,
    detail: str | None = None,
    provider_ambiguous: bool = False,
) -> dict[str, Any]:
    _host_lifecycle()
    return _client().submit_result(
        request_id,
        _bound(request_id),
        status=status,
        response=response,
        detail=detail,
        provider_ambiguous=provider_ambiguous,
    )


@_lifecycle_tool(name="anima_renew", description="Renew the active ANIMA interaction lease")
def anima_renew(request_id: str) -> dict[str, Any]:
    _host_lifecycle()
    return _client().renew(request_id, _bound(request_id))


@_lifecycle_tool(
    name="anima_provider_start", description="Fence provider execution before SENTRY reasoning"
)
def anima_provider_start(request_id: str) -> dict[str, Any]:
    _host_lifecycle()
    return _client().provider_start(request_id, _bound(request_id))


@server.tool(
    name="anima_status",
    description="Get exact bounded request status",
    annotations=_READ_ANNOTATIONS,
)
def anima_status(request_id: str) -> dict[str, Any]:
    return _safe_result(_client().status(request_id, _bound(request_id)))


def main() -> int:
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
