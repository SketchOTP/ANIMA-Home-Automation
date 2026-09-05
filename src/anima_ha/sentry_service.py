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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import psycopg

from anima_ha.db.migrate import migrate
from anima_ha.intelligence import (
    IntelligenceLifecycle,
    IntelligenceResult,
    IntelligenceResultStatus,
)
from anima_ha.sentry_boundary import (
    CoreSentryBoundary,
    SentryBoundaryError,
    SentryIdentityEvidenceEnvelope,
)
from anima_ha.ui_runtime import build_postgres_core

MAX_BODY = 64 * 1024
BINDING_TTL = timedelta(minutes=5)


class ServiceAuthError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SentryServicePrincipal:
    """ANIMA-owned, server-side identity for one SENTRY household client."""

    client_id: str
    household_id: UUID
    provider_id: str
    credential_generation: int
    token_digest: str
    enabled: bool = True
    allowed_origins: tuple[str, ...] = ("DIRECT_SENTRY_INTERACTION", "SENTRY_PROVIDER")

    @classmethod
    def from_secret(
        cls,
        *,
        client_id: str,
        household_id: UUID,
        provider_id: str,
        token: str,
        credential_generation: int = 1,
    ) -> SentryServicePrincipal:
        if not client_id.strip() or not provider_id.strip() or credential_generation < 1:
            raise ValueError("invalid SENTRY service-principal configuration")
        return cls(
            client_id=client_id,
            household_id=household_id,
            provider_id=provider_id,
            credential_generation=credential_generation,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
        )

    def authenticates(self, token: str) -> bool:
        return self.enabled and hmac.compare_digest(
            self.token_digest, hashlib.sha256(token.encode()).hexdigest()
        )


class PostgresSentryPrincipalRegistry:
    """Durable ANIMA-owned registration for the SENTRY service identity."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def register(self, principal: SentryServicePrincipal) -> None:
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO anima_sentry_service_principals
                    (client_id, household_id, provider_id, credential_generation,
                     token_digest, enabled, allowed_origins)
                VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (client_id) DO UPDATE SET
                    household_id=EXCLUDED.household_id,
                    provider_id=EXCLUDED.provider_id,
                    credential_generation=EXCLUDED.credential_generation,
                    token_digest=EXCLUDED.token_digest,
                    enabled=EXCLUDED.enabled,
                    allowed_origins=EXCLUDED.allowed_origins,
                    updated_at=now()
                """,
                (
                    principal.client_id,
                    principal.household_id,
                    principal.provider_id,
                    principal.credential_generation,
                    principal.token_digest,
                    principal.enabled,
                    json.dumps(list(principal.allowed_origins)),
                ),
            )
            connection.commit()

    def active(self, principal: SentryServicePrincipal, token: str) -> bool:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with psycopg.connect(self.database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM anima_sentry_service_principals
                WHERE client_id=%s AND household_id=%s AND provider_id=%s
                  AND credential_generation=%s AND token_digest=%s AND enabled
                """,
                (
                    principal.client_id,
                    principal.household_id,
                    principal.provider_id,
                    principal.credential_generation,
                    digest,
                ),
            )
            return cursor.fetchone() is not None


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

    def issue(
        self,
        request: Any,
        *,
        sentry_request_id: str,
        source_surface: str,
        principal: SentryServicePrincipal | None = None,
    ) -> str:
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
            "client_id": principal.client_id if principal else None,
            "credential_generation": principal.credential_generation if principal else None,
        }
        encoded = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = hmac.new(self.secret, encoded.encode(), hashlib.sha256).digest()
        return f"{encoded}.{_b64(signature)}"

    def verify(
        self,
        value: str,
        request: Any,
        principal: SentryServicePrincipal | None = None,
    ) -> dict[str, Any]:
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
            or (
                principal is not None
                and (
                    payload.get("client_id") != principal.client_id
                    or payload.get("credential_generation") != principal.credential_generation
                )
            )
        ):
            raise ServiceAuthError("interaction binding does not match request")
        return cast(dict[str, Any], payload)


class _UnixHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    address_family = socket.AF_UNIX
    daemon_threads = True
    service: CoreSentryHTTPService


class CoreSentryHTTPService:
    def __init__(
        self,
        boundary: CoreSentryBoundary,
        token_loader: Callable[[], str],
        *,
        service_principal: SentryServicePrincipal | None = None,
        profile_principal_resolver: Callable[[UUID, str], UUID | None] | None = None,
        principal_registry: PostgresSentryPrincipalRegistry | None = None,
    ) -> None:
        self.boundary = boundary
        self.token_loader = token_loader
        self.service_principal = service_principal
        self.profile_principal_resolver = profile_principal_resolver
        self.principal_registry = principal_registry
        self.bindings = SentryBindingCodec("unused-until-authenticated")

    def authenticate(self, headers: Any) -> SentryServicePrincipal | None:
        # Reloading on every request gives rotation/revocation semantics. A
        # rotated token also invalidates previously issued binding signatures.
        self.service_token = self.token_loader()
        self.bindings = SentryBindingCodec(self.service_token)
        provided = str(headers.get("Authorization", ""))
        if not hmac.compare_digest(provided, f"Bearer {self.service_token}"):
            raise ServiceAuthError("service authentication failed")
        if self.service_principal is not None:
            if self.service_principal.provider_id != "sentry":
                raise ServiceAuthError("service principal provider is not allowed")
            if not self.service_principal.authenticates(self.service_token):
                raise ServiceAuthError("service principal is revoked or rotated")
            if self.principal_registry is not None and not self.principal_registry.active(
                self.service_principal, self.service_token
            ):
                raise ServiceAuthError("service principal is not active")
        return self.service_principal

    def _request(
        self,
        request_id: str,
        body: dict[str, Any],
        principal: SentryServicePrincipal | None = None,
    ) -> Any:
        request = self.boundary.intelligence_store.get(UUID(request_id))
        if request is None:
            raise SentryBoundaryError("INTELLIGENCE_REQUEST_NOT_FOUND")
        binding = str(body.get("binding", ""))
        if not binding:
            raise ServiceAuthError("interaction binding required")
        if principal is not None and request.household_id != principal.household_id:
            raise ServiceAuthError("service principal household mismatch")
        self.bindings.verify(binding, request, principal)
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
        self,
        worker_id: str,
        sentry_request_id: str,
        source_surface: str,
        principal: SentryServicePrincipal | None = None,
    ) -> dict[str, Any]:
        effective_worker = principal.client_id if principal is not None else worker_id
        if principal is not None and "SENTRY_PROVIDER" not in principal.allowed_origins:
            raise ServiceAuthError("SENTRY provider work is not allowed")
        request = self.boundary.claim_request(
            effective_worker, household_id=principal.household_id if principal else None
        )
        if request is None:
            return {"status": "EMPTY"}
        binding = self.bindings.issue(
            request,
            sentry_request_id=sentry_request_id,
            source_surface=source_surface,
            principal=principal,
        )
        if not self.boundary.intelligence_store.transition(
            request.request_id,
            effective_worker,
            request.fencing_generation,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
        ):
            raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")
        return {"status": "CLAIMED", **self.request_payload(request, binding)}

    def direct_interaction(
        self,
        *,
        sentry_request_id: str,
        source_surface: str,
        user_text: str,
        principal: SentryServicePrincipal,
        identity_observation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create and bind a new direct request, independent of Attention."""
        if "DIRECT_SENTRY_INTERACTION" not in principal.allowed_origins:
            raise ServiceAuthError("direct SENTRY interaction is not allowed")
        envelope: SentryIdentityEvidenceEnvelope | None = None
        mapped: UUID | None = None
        identity_context = None
        refs: tuple[str, ...] = ()
        if identity_observation:
            observed_value = identity_observation.get("observed_at")
            observed_at = (
                datetime.fromisoformat(str(observed_value))
                if observed_value is not None
                else datetime.now(UTC)
            )
            envelope = SentryIdentityEvidenceEnvelope(
                endpoint_id=str(identity_observation.get("endpoint_id", "sentry"))[:256],
                profile_state=str(identity_observation.get("profile_state", "unknown"))[:64],
                confidence=int(identity_observation.get("confidence", 0)),
                observed_at=observed_at,
                local_proximity=bool(identity_observation.get("local_proximity", False)),
                spoken_identity_claim=(
                    str(identity_observation["spoken_identity_claim"])
                    if identity_observation.get("spoken_identity_claim") is not None
                    else None
                ),
                state=str(identity_observation.get("state", "unknown"))[:64],
            )
            mapped = (
                self.profile_principal_resolver(
                    principal.household_id, str(identity_observation.get("profile_id", ""))
                )
                if self.profile_principal_resolver is not None
                else None
            )
            evidence, identity_context = self.boundary.persist_sentry_identity(
                principal.household_id, envelope, profile_principal_id=mapped
            )
            refs = (str(evidence.evidence_id),)
        request = self.boundary.create_direct_request(
            household_id=principal.household_id,
            sentry_request_id=sentry_request_id,
            source_surface=source_surface,
            user_text=user_text,
            identity_evidence_refs=refs,
            principal_id=identity_context.principal_id if identity_context else None,
            service_client_id=principal.client_id,
            identity_context=identity_context,
        )
        claimed = self.boundary.claim_specific_request(
            request.request_id, str(principal.client_id), principal.household_id
        )
        if claimed is None or claimed.request_id != request.request_id:
            raise SentryBoundaryError("DIRECT_INTERACTION_CLAIM_FAILED")
        request = claimed
        binding = self.bindings.issue(
            request,
            sentry_request_id=sentry_request_id,
            source_surface=source_surface,
            principal=principal,
        )
        needs_delivery = request.lifecycle == IntelligenceLifecycle.CLAIMED
        if needs_delivery and not self.boundary.intelligence_store.transition(
            request.request_id,
            str(principal.client_id),
            request.fencing_generation,
            IntelligenceLifecycle.DELIVERED_TO_PROVIDER,
        ):
            raise SentryBoundaryError("INTELLIGENCE_CLAIM_LOST")
        return {"status": "CLAIMED", **self.request_payload(request, binding)}

    def dispatch(self, request: Any) -> None:
        if request.lifecycle == IntelligenceLifecycle.DELIVERED_TO_PROVIDER:
            if not self.boundary.start_provider(request, str(request.claim_owner)):
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
            principal = service.authenticate(self.headers)
            body = self._json()
            response: dict[str, Any]
            if self.path == "/v1/health":
                response = service.boundary.health().to_payload()
            elif self.path == "/v1/interactions/open":
                response = service.claim_and_bind(
                    str(body.get("worker_id", "")),
                    str(body.get("sentry_request_id", secrets.token_hex(8))),
                    str(body.get("source_surface", "sentry")),
                    principal,
                )
            elif self.path == "/v1/interactions/direct":
                if principal is None:
                    raise ServiceAuthError("direct interaction requires a scoped service principal")
                response = service.direct_interaction(
                    sentry_request_id=str(body.get("sentry_request_id", "")),
                    source_surface=str(body.get("source_surface", "sentry")),
                    user_text=str(body.get("user_text", "")),
                    principal=principal,
                    identity_observation=(
                        dict(body["identity_observation"])
                        if isinstance(body.get("identity_observation"), dict)
                        else None
                    ),
                )
            elif self.path == "/v1/requests/renew":
                request = service._request(str(body["request_id"]), body, principal)
                ok = service.boundary.renew_request(request, str(request.claim_owner))
                response = {"status": "RENEWED" if ok else "CLAIM_LOST"}
            else:
                parts = self.path.strip("/").split("/")
                if len(parts) != 4 or parts[:2] != ["v1", "requests"]:
                    self._write(404, {"error": "NOT_FOUND"})
                    return
                request = service._request(parts[2], body, principal)
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
                elif operation == "provider-start":
                    worker_id = request.claim_owner
                    response = {
                        "status": "PROVIDER_RUNNING"
                        if worker_id and service.boundary.start_provider(request, worker_id)
                        else "CLAIM_LOST"
                    }
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


def _profile_mapping(raw: str) -> dict[str, UUID]:
    """Load a bounded, server-owned SENTRY profile mapping."""
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict) or len(value) > 128:
        raise RuntimeError("SENTRY profile mapping must be a bounded object")
    result: dict[str, UUID] = {}
    for profile, principal in value.items():
        if not isinstance(profile, str) or not profile.strip() or len(profile) > 128:
            raise RuntimeError("SENTRY profile mapping key is invalid")
        result[profile] = UUID(str(principal))
    return result


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
    token = token_loader()
    client_id = os.environ.get("ANIMA_SENTRY_CLIENT_ID", "").strip()
    household_value = os.environ.get("ANIMA_SENTRY_HOUSEHOLD_ID", "").strip()
    if not client_id or not household_value:
        raise RuntimeError(
            "ANIMA Core service requires ANIMA_SENTRY_CLIENT_ID and "
            "ANIMA_SENTRY_HOUSEHOLD_ID for household-scoped registration"
        )
    principal = SentryServicePrincipal.from_secret(
        client_id=client_id,
        household_id=UUID(household_value),
        provider_id="sentry",
        token=token,
        credential_generation=int(os.environ.get("ANIMA_SENTRY_CREDENTIAL_GENERATION", "1")),
    )
    principal_registry = PostgresSentryPrincipalRegistry(database_url)
    principal_registry.register(principal)
    profile_mapping = _profile_mapping(os.environ.get("ANIMA_SENTRY_PROFILE_PRINCIPAL_MAP", ""))

    def profile_principal_resolver(household_id: UUID, profile_id: str) -> UUID | None:
        if household_id != principal.household_id:
            return None
        candidate = profile_mapping.get(profile_id)
        if candidate is None:
            return None
        if not any(
            household.canonical_id == household_id
            for household in core.graph.households_for_member(candidate)
        ):
            return None
        return candidate

    server.service = CoreSentryHTTPService(
        core.sentry_boundary(),
        token_loader,
        service_principal=principal,
        principal_registry=principal_registry,
        profile_principal_resolver=profile_principal_resolver,
    )
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
