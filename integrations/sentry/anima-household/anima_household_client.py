"""Small dependency-light client for the ANIMA household service.

This file is intentionally installable without the ANIMA repository. It has
no database, HA, OPA, shell, filesystem, or generic-provider operations.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import stat
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_SERVICE_CODES = frozenset(
    {
        "NOT_FOUND",
        "INTELLIGENCE_REQUEST_NOT_FOUND",
        "INTELLIGENCE_CLAIM_LOST",
        "TOOL_UNAVAILABLE",
        "TOOL_NOT_BOUND_TO_REQUEST",
        "TOOL_BINDING_INCOMPATIBLE",
        "INVALID_TOOL_ORDINAL",
        "ACTION_COORDINATOR_UNAVAILABLE",
        "TRUSTED_ACTION_SPEC_UNAVAILABLE",
        "CONTEXT_BOUNDARY_UNAVAILABLE",
        "CONTEXT_TRIGGER_UNAVAILABLE",
        "CONTEXT_PACKET_UNAVAILABLE",
        "CONTEXT_HOUSEHOLD_MISMATCH",
        "INTELLIGENCE_RESULT_CLAIM_LOST",
        "DIRECT_INTERACTION_CLAIM_FAILED",
    }
)
# Exact literal messages from the service contract, never arbitrary error text.
_SERVICE_MESSAGES = {
    "invalid interaction binding": "INVALID_BINDING",
    "interaction binding expired": "BINDING_EXPIRED",
    "interaction binding does not match request": "BINDING_MISMATCH",
    "interaction binding required": "BINDING_REQUIRED",
    "service authentication failed": "AUTHENTICATION_FAILED",
    "service principal provider is not allowed": "PROVIDER_NOT_ALLOWED",
    "service principal is revoked or rotated": "PRINCIPAL_REVOKED",
    "service principal is not active": "PRINCIPAL_INACTIVE",
    "service principal household mismatch": "HOUSEHOLD_MISMATCH",
    "SENTRY provider work is not allowed": "PROVIDER_WORK_NOT_ALLOWED",
    "request body exceeds limit": "REQUEST_LIMIT",
    "request body must be an object": "INVALID_REQUEST_OBJECT",
}
_TRANSPORT_CODES = frozenset(
    {
        "TIMEOUT",
        "REMOTE_DISCONNECTED",
        "CONNECTION_REFUSED",
        "CONNECTION_RESET",
        "SOCKET_NOT_FOUND",
        "HTTP_PROTOCOL_ERROR",
        "OS_ERROR",
        "TRANSPORT_ERROR",
        "REDIRECT_REJECTED",
        "RESPONSE_LIMIT",
        "INVALID_JSON",
        "INVALID_RESPONSE",
        "REQUEST_LIMIT",
    }
)


class AnimaHouseholdError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        service_code: str | None = None,
        transport_code: str | None = None,
    ):
        super().__init__(message)
        self.http_status = http_status
        self.service_code = service_code
        self.transport_code = transport_code

    def safe_diagnostics(self) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if type(self.http_status) is int and 100 <= self.http_status <= 599:
            fields["http_status"] = self.http_status
        if self.service_code in _SERVICE_CODES | set(_SERVICE_MESSAGES.values()) | {"UNCLASSIFIED"}:
            fields["service_code"] = self.service_code
        if self.transport_code in _TRANSPORT_CODES:
            fields["transport_code"] = self.transport_code
        return fields


def _transport_error(exc: Exception) -> AnimaHouseholdError:
    # URLError.reason may be a nested exception or a string. Only inspect type.
    cause = exc.reason if isinstance(exc, URLError) else exc
    code = next(
        (
            label
            for cls, label in (
                (TimeoutError, "TIMEOUT"),
                (http.client.RemoteDisconnected, "REMOTE_DISCONNECTED"),
                (ConnectionRefusedError, "CONNECTION_REFUSED"),
                (ConnectionResetError, "CONNECTION_RESET"),
                (FileNotFoundError, "SOCKET_NOT_FOUND"),
                (http.client.HTTPException, "HTTP_PROTOCOL_ERROR"),
                (OSError, "OS_ERROR"),
            )
            if isinstance(cause, cls)
        ),
        "TRANSPORT_ERROR",
    )
    return AnimaHouseholdError("ANIMA transport unavailable", transport_code=code)


def _response_limit(path: str) -> int:
    # Frozen tool descriptors include schemas, not household/provider content.
    # Keep every data/result route at the original 64 KiB boundary.
    from uuid import UUID

    parts = path.split("/")
    if len(parts) == 5 and parts[:3] == ["", "v1", "requests"] and parts[4] == "tools":
        try:
            if str(UUID(parts[3])) == parts[3]:
                return 128 * 1024
        except ValueError:
            pass
    return 64 * 1024


def _decode_response(raw: bytes, status: int, *, limit: int = 64 * 1024) -> dict[str, Any]:
    if len(raw) > limit:
        raise AnimaHouseholdError(
            "ANIMA response exceeds transport limit",
            http_status=status,
            transport_code="RESPONSE_LIMIT",
        )
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise AnimaHouseholdError(
            "ANIMA service returned invalid JSON",
            http_status=status,
            transport_code="INVALID_JSON",
        ) from None
    if not isinstance(value, dict):
        raise AnimaHouseholdError(
            "ANIMA service returned an invalid response",
            http_status=status,
            transport_code="INVALID_RESPONSE",
        )
    if status >= 300 or "error" in value:
        error = value.get("error")
        code = "UNCLASSIFIED"
        if isinstance(error, str):
            code = error if error in _SERVICE_CODES else _SERVICE_MESSAGES.get(error, code)
        raise AnimaHouseholdError(
            "ANIMA service rejected request",
            http_status=status,
            service_code=code,
        )
    return value


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise AnimaHouseholdError(
            "ANIMA service redirects are not allowed",
            http_status=code,
            transport_code="REDIRECT_REJECTED",
        )


def _token(path_value: str) -> str:
    path = Path(path_value)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise AnimaHouseholdError("ANIMA client token file must be private and regular")
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32 or len(value) > 256:
        raise AnimaHouseholdError("ANIMA client token is invalid")
    return value


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float) -> None:
        super().__init__("anima-core", timeout=timeout)
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


class AnimaHouseholdClient:
    def __init__(
        self,
        endpoint: str | None = None,
        token_file: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint or os.environ.get("ANIMA_SENTRY_ENDPOINT", "")
        self.token_file = token_file or os.environ.get("ANIMA_SENTRY_CLIENT_TOKEN_FILE", "")
        self.worker_id = os.environ.get("ANIMA_SENTRY_WORKER_ID", "").strip()
        self.timeout = timeout
        if not self.endpoint or not self.token_file:
            raise AnimaHouseholdError("ANIMA service endpoint and client token are required")
        parsed = urlsplit(self.endpoint)
        if parsed.scheme in {"http", "https"}:
            if (
                parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
                or not parsed.hostname
            ):
                raise AnimaHouseholdError("ANIMA service endpoint must be an origin")
            if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
                raise AnimaHouseholdError("plain HTTP requires a loopback endpoint or SSH tunnel")
        elif parsed.scheme or not Path(self.endpoint).is_absolute():
            raise AnimaHouseholdError("ANIMA socket path must be absolute")
        self.token = _token(self.token_file)

    def call(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        response_limit = _response_limit(path)
        body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":")).encode()
        if len(body) > 64 * 1024:
            raise AnimaHouseholdError(
                "ANIMA request exceeds transport limit",
                transport_code="REQUEST_LIMIT",
            )
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        parsed = urlsplit(self.endpoint)
        request_timeout = self.timeout if timeout is None else timeout
        if parsed.scheme in {"http", "https"}:
            url = self.endpoint.rstrip("/") + path
            request = Request(url, data=body, headers=headers, method="POST")
            try:
                with build_opener(ProxyHandler({}), _NoRedirect()).open(
                    request, timeout=request_timeout
                ) as response:
                    status = response.status
                    raw = response.read(response_limit + 1)
            except HTTPError as exc:
                try:
                    status = exc.code
                    raw = exc.read(response_limit + 1)
                except Exception as read_exc:
                    raise _transport_error(read_exc) from None
                finally:
                    exc.close()
            except AnimaHouseholdError:
                raise
            except Exception as exc:
                raise _transport_error(exc) from None
        else:
            connection = _UnixConnection(self.endpoint, request_timeout)
            try:
                connection.request("POST", path, body=body, headers=headers)
                response = connection.getresponse()
                status = response.status
                raw = response.read(response_limit + 1)
            except AnimaHouseholdError:
                raise
            except Exception as exc:
                raise _transport_error(exc) from None
            finally:
                connection.close()
        return _decode_response(raw, status, limit=response_limit)

    def wait_eligible(self, payload: dict[str, Any], *, wait_seconds: int = 25) -> dict[str, Any]:
        return self.call(
            "/v1/provider/requests/wait",
            {**payload, "wait_seconds": wait_seconds},
            timeout=wait_seconds + 3,
        )

    def open_interaction(self, sentry_request_id: str, source_surface: str) -> dict[str, Any]:
        return self.call(
            "/v1/interactions/open",
            {
                "worker_id": self.worker_id,
                "sentry_request_id": sentry_request_id,
                "source_surface": source_surface,
            },
        )

    def open_direct_interaction(
        self,
        sentry_request_id: str,
        source_surface: str,
        user_text: str,
        identity_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.call(
            "/v1/interactions/direct",
            {
                "sentry_request_id": sentry_request_id,
                "source_surface": source_surface,
                "user_text": user_text,
                "identity_observation": identity_observation,
            },
        )

    def context(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/context", {"binding": binding})

    def tools(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/tools", {"binding": binding})

    def invoke(
        self,
        request_id: str,
        binding: str,
        tool_id: str,
        arguments: dict[str, Any],
        ordinal: int,
    ) -> dict[str, Any]:
        return self.call(
            f"/v1/requests/{request_id}/invoke",
            {
                "binding": binding,
                "tool_id": tool_id,
                "arguments": arguments,
                "ordinal": ordinal,
            },
        )

    def submit_result(self, request_id: str, binding: str, **payload: Any) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/result", {"binding": binding, **payload})

    def renew(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call("/v1/requests/renew", {"request_id": request_id, "binding": binding})

    def provider_start(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/provider-start", {"binding": binding})

    def status(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/status", {"binding": binding})

    def voice_settings(self) -> dict[str, Any]:
        """Read ANIMA-owned household voice settings for the SENTRY service."""
        return self.call("/v1/sentry/voice-settings", {})

    def personality_profile(self) -> dict[str, Any]:
        """Read the active ANIMA-owned presentation profile for SENTRY."""
        return self.call("/v1/sentry/personality", {})
