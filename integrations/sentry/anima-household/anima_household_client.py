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
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class AnimaHouseholdError(RuntimeError):
    pass


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
        self.token = _token(self.token_file)

    def call(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload or {}, sort_keys=True, separators=(",", ":")).encode()
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        parsed = urlsplit(self.endpoint)
        if parsed.scheme in {"http", "https"}:
            url = self.endpoint.rstrip("/") + path
            request = Request(url, data=body, headers=headers, method="POST")
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read(64 * 1024)
            except Exception as exc:
                raise AnimaHouseholdError("ANIMA service unavailable") from exc
        else:
            connection = _UnixConnection(self.endpoint, self.timeout)
            try:
                connection.request("POST", path, body=body, headers=headers)
                response = connection.getresponse()
                raw = response.read(64 * 1024)
                if response.status >= 400:
                    raise AnimaHouseholdError(f"ANIMA service rejected request: {response.status}")
            except AnimaHouseholdError:
                raise
            except Exception as exc:
                raise AnimaHouseholdError("ANIMA service unavailable") from exc
            finally:
                connection.close()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AnimaHouseholdError("ANIMA service returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise AnimaHouseholdError("ANIMA service returned an invalid response")
        if "error" in value:
            raise AnimaHouseholdError(str(value["error"]))
        return value

    def open_interaction(self, sentry_request_id: str, source_surface: str) -> dict[str, Any]:
        return self.call(
            "/v1/interactions/open",
            {
                "worker_id": self.worker_id,
                "sentry_request_id": sentry_request_id,
                "source_surface": source_surface,
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

    def status(self, request_id: str, binding: str) -> dict[str, Any]:
        return self.call(f"/v1/requests/{request_id}/status", {"binding": binding})
