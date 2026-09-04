"""ANIMA-owned service boundary for the SENTRY household client.

The process launched by ANIMA owns the database, OPA, HA and provider
credentials.  SENTRY receives only an authenticated, short-lived binding and
the sparse request-scoped data returned by this service.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import http.server
import json
import os
import secrets
import socket
import socketserver
import stat
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceResult,
    IntelligenceResultStatus,
)
from anima_ha.sentry_boundary import CoreSentryBoundary, SentryBoundaryError
from anima_ha.ui_runtime import build_postgres_core

MAX_BODY = 64 * 1024
BINDING_TTL = timedelta(minutes=5)


class ServiceAuthError(RuntimeError):
    pass


def read_credential_file(path_value: str) -> str:
    """Read a service credential only from a private, non-symlink regular file."""
    path = Path(path_value)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ServiceAuthError("service credential must be a regular file")
    if info.st_mode & 0o077:
        raise ServiceAuthError("service credential permissions must be 0600 or stricter")
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 32 or len(value) > 256:
        raise ServiceAuthError("service credential length is invalid")
    return value


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class SentryBindingCodec:
    def __init__(self, secret: str) -> None:
        self.secret = secret.encode("utf-8")

    def issue(self, request: Any, *, sentry_request_id: str, source_surface: str) -> str:
        now = datetime.now(UTC)
        payload = {
            "request_id": str(request.request_id),
            "household_id": str(request.household_id),
            "sentry_request_id": sentry_request_id[:256],
            "source_surface": source_surface[:64],
            "correlation_id": request.correlation_id,
            "expires_at": (now + BINDING_TTL).isoformat(),
            "provider_id": request.provider_id,
            "provider_version": request.provider_version,
            "catalogue_digest": request.catalogue_digest,
            "identity_evidence_refs": [
                ref
                for ref in (request.request_metadata.get("identity_evidence_refs") or [])
                if isinstance(ref, str)
            ][:16],
            "worker_id": request.claim_owner,
            "generation": request.fencing_generation,
        }
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = hmac.new(self.secret, encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{_b64(signature)}"

    def verify(self, value: str, request: Any) -> dict[str, Any]:
        try:
            encoded, signature = value.split(".", 1)
            expected = hmac.new(self.secret, encoded.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(signature)):
                raise ServiceAuthError("invalid interaction binding")
            payload = json.loads(_unb64(encoded))
            expires = datetime.fromisoformat(str(payload["expires_at"]))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ServiceAuthError("invalid interaction binding") from exc
        if expires <= datetime.now(UTC):
            raise ServiceAuthError("interaction binding expired")
        if (
            payload.get("request_id") != str(request.request_id)
            or payload.get("household_id") != str(request.household_id)
            or payload.get("provider_id") != request.provider_id
            or payload.get("provider_version") != request.provider_version
            or payload.get("catalogue_digest") != request.catalogue_digest
            or payload.get("generation") != request.fencing_generation
            or payload.get("worker_id") != request.claim_owner
        ):
            raise ServiceAuthError("interaction binding does not match request")
        return cast(dict[str, Any], payload)


class _UnixHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    address_family = socket.AF_UNIX
    daemon_threads = True
    service: CoreSentryHTTPService


class CoreSentryHTTPService:
    def __init__(self, boundary: CoreSentryBoundary, token_loader: Callable[[], str]) -> None:
        self.boundary = boundary
        self.token_loader = token_loader
        self.service_token = ""
        self.bindings = SentryBindingCodec("unused-until-authenticated")

    def authenticate(self, headers: Any) -> None:
        # Reloading on every request gives rotation/revocation semantics. A
        # rotated token also invalidates previously issued binding signatures.
        self.service_token = self.token_loader()
        self.bindings = SentryBindingCodec(self.service_token)
        provided = str(headers.get("Authorization", ""))
        if not hmac.compare_digest(provided, f"Bearer {self.service_token}"):
            raise ServiceAuthError("service authentication failed")

    def _request(self, request_id: str, body: dict[str, Any]) -> Any:
        request = self.boundary.intelligence_store.get(UUID(request_id))
        if request is None:
            raise SentryBoundaryError("INTELLIGENCE_REQUEST_NOT_FOUND")
        binding = str(body.get("binding", ""))
        if not binding:
            raise ServiceAuthError("interaction binding required")
        self.bindings.verify(binding, request)
        self.boundary._assert_active(request)
        return request

    @staticmethod
    def request_payload(request: Any, binding: str) -> dict[str, Any]:
        return {
            "request_id": str(request.request_id),
            "household_id": str(request.household_id),
            "origin": request.origin.value,
            "context_packet_id": str(request.context_packet_id),
            "context_digest": request.context_digest,
            "catalogue_digest": request.catalogue_digest,
            "provider_id": request.provider_id,
            "provider_version": request.provider_version,
            "fencing_generation": request.fencing_generation,
            "binding": binding,
        }

    def claim_and_bind(
        self, worker_id: str, sentry_request_id: str, source_surface: str
    ) -> dict[str, Any]:
        request = self.boundary.claim_request(worker_id)
        if request is None:
            return {"status": "EMPTY"}
        binding = self.bindings.issue(
            request, sentry_request_id=sentry_request_id, source_surface=source_surface
        )
        if not self.boundary.intelligence_store.transition(
            request.request_id,
            worker_id,
            request.fencing_generation,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
        ):
            raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")
        return {"status": "CLAIMED", **self.request_payload(request, binding)}

    def dispatch(self, request: Any) -> None:
        if (
            request.lifecycle == IntelligenceLifecycle.DELIVERED_TO_PROVIDER
            and not self.boundary.intelligence_store.transition(
                request.request_id,
                str(request.claim_owner),
                request.fencing_generation,
                IntelligenceLifecycle.PROVIDER_RUNNING,
            )
        ):
            raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")


class _Handler(http.server.BaseHTTPRequestHandler):
    server: _UnixHTTPServer

    def _service(self) -> CoreSentryHTTPService:
        return self.server.service

    def _json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > MAX_BODY:
            raise ValueError("request body exceeds limit")
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _write(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        try:
            self._service().authenticate(self.headers)
            if self.path != "/v1/health":
                self._write(404, {"error": "NOT_FOUND"})
                return
            self._write(200, self._service().boundary.health().to_payload())
        except ServiceAuthError as exc:
            self._write(401, {"error": str(exc)})

    def do_POST(self) -> None:  # noqa: N802
        try:
            service = self._service()
            service.authenticate(self.headers)
            body = self._json()
            response: dict[str, Any]
            if self.path == "/v1/health":
                response = service.boundary.health().to_payload()
            elif self.path == "/v1/interactions/open":
                response = service.claim_and_bind(
                    str(body.get("worker_id", "")),
                    str(body.get("sentry_request_id", secrets.token_hex(8))),
                    str(body.get("source_surface", "sentry")),
                )
            elif self.path == "/v1/requests/renew":
                request = service._request(str(body["request_id"]), body)
                ok = service.boundary.renew_request(request, str(request.claim_owner))
                response = {"status": "RENEWED" if ok else "CLAIM_LOST"}
            else:
                parts = self.path.strip("/").split("/")
                if len(parts) != 4 or parts[:2] != ["v1", "requests"]:
                    self._write(404, {"error": "NOT_FOUND"})
                    return
                request = service._request(parts[2], body)
                operation = parts[3]
                if operation == "context":
                    response = service.boundary.request_context(request)
                elif operation == "tools":
                    response = {"tools": service.boundary.catalogue(request)}
                elif operation == "invoke":
                    service.dispatch(request)
                    response = service.boundary.invoke_tool(
                        request,
                        str(body["tool_id"]),
                        dict(body.get("arguments") or {}),
                        ordinal=int(body.get("ordinal", 1)),
                    )
                elif operation == "result":
                    result = IntelligenceResult(
                        request.request_id,
                        IntelligenceResultStatus(str(body["status"])),
                        response_text=(
                            str(body["response"]) if body.get("response") is not None else None
                        ),
                        detail=(str(body["detail"]) if body.get("detail") is not None else None),
                        action_references=tuple(str(x) for x in body.get("action_references", [])),
                        provider_ambiguous=bool(body.get("provider_ambiguous", False)),
                    )
                    response = {
                        "status": "RECORDED"
                        if service.boundary.submit_result(request, str(request.claim_owner), result)
                        else "CLAIM_LOST"
                    }
                elif operation == "status":
                    response = {
                        "request_id": str(request.request_id),
                        "lifecycle": request.lifecycle.value,
                        "attempt_count": request.attempt_count,
                        "provider_invocation_started": request.provider_invocation_started,
                    }
                else:
                    self._write(404, {"error": "NOT_FOUND"})
                    return
            self._write(200, response)
        except (KeyError, ValueError, ServiceAuthError, SentryBoundaryError) as exc:
            code = (
                401
                if isinstance(exc, ServiceAuthError)
                else 409
                if isinstance(exc, SentryBoundaryError)
                else 400
            )
            self._write(code, {"error": str(exc)})

    def log_message(self, format: str, *args: Any) -> None:
        return


def serve(database_url: str, socket_path: str, token_path: str, opa_url: str) -> None:
    def token_loader() -> str:
        return read_credential_file(token_path)

    migrate(database_url, 5)
    core = build_postgres_core(database_url, opa_url=opa_url)
    path = Path(socket_path)
    if path.exists():
        if not stat.S_ISSOCK(path.lstat().st_mode):
            raise RuntimeError("ANIMA Core socket path is not a socket")
        path.unlink()
    server = _UnixHTTPServer(str(path), _Handler)  # type: ignore[arg-type]
    os.chmod(path, 0o600)
    server.service = CoreSentryHTTPService(core.sentry_boundary(), token_loader)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ANIMA-owned SENTRY Core service")
    parser.add_argument("--database-url", default=os.environ.get("ANIMA_DATABASE_URL", ""))
    parser.add_argument(
        "--socket", default=os.environ.get("ANIMA_SENTRY_SOCKET", "/run/anima/core.sock")
    )
    parser.add_argument(
        "--token-file", default=os.environ.get("ANIMA_SENTRY_SERVICE_TOKEN_FILE", "")
    )
    parser.add_argument(
        "--opa-url", default=os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:8181")
    )
    args = parser.parse_args()
    if not args.database_url or not args.token_file:
        parser.error("ANIMA Core service requires database URL and service token file")
    serve(args.database_url, args.socket, args.token_file, args.opa_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
