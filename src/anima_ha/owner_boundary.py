"""Optional owner deployment of the existing SENTRY API beside the UI Core.

Shares the commissioned Core, not a second cognition/runtime composition. Only
the service client credential and Unix socket are shared with a household worker.
"""

from __future__ import annotations

import os
import secrets
import stat
import threading
from pathlib import Path
from typing import Any
from uuid import UUID


class OwnerBoundaryError(RuntimeError):
    pass


def private_client_token(path: Path) -> str:
    from anima_ha.sentry_service import read_credential_file

    if not path.exists() and not path.is_symlink():
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
            stream.flush()
            os.fsync(stream.fileno())
    return read_credential_file(str(path))


class OwnerBoundary:
    def __init__(
        self,
        core: Any,
        household_id: UUID,
        database_url: str,
        directory: Path,
        *,
        socket_group: int | None = None,
    ) -> None:
        # Late import avoids eagerly composing another UI from module imports.
        from anima_ha.sentry_autowake import PostgresAutoWakeClaims, aware_timestamp
        from anima_ha.sentry_service import (
            _Handler,
            _UnixHTTPServer,
        )

        if core.intelligence_provider.value != "sentry":
            raise OwnerBoundaryError("SENTRY_MODE_REQUIRED")
        enable_epoch = os.environ.get("ANIMA_SENTRY_AUTOWAKE_ENABLED_AT", "").strip()
        auto_wake_claims = (
            PostgresAutoWakeClaims(database_url, enabled_at=aware_timestamp(enable_epoch))
            if enable_epoch
            else None
        )
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o027:
            raise OwnerBoundaryError("BOUNDARY_DIRECTORY_UNSAFE")
        if socket_group is not None:
            if socket_group not in {*os.getgroups(), os.getgid()}:
                raise OwnerBoundaryError("BOUNDARY_SOCKET_GROUP_UNAVAILABLE")
            os.chown(directory, -1, socket_group)
            os.chmod(directory, 0o750)
        self.socket_path = directory / "core.sock"
        try:
            self.server = _UnixHTTPServer(str(self.socket_path), _Handler)
        except RuntimeError as exc:
            raise OwnerBoundaryError(str(exc)) from exc
        try:
            self._configure(
                core, household_id, database_url, directory, socket_group, auto_wake_claims
            )
        except BaseException:
            self.server.server_close()
            raise

    def _configure(
        self,
        core: Any,
        household_id: UUID,
        database_url: str,
        directory: Path,
        socket_group: int | None,
        auto_wake_claims: Any,
    ) -> None:
        from anima_ha.live_results import PostgresSentryLivePublisher
        from anima_ha.sentry_personality import SentryPersonalityStore
        from anima_ha.sentry_service import (
            CoreSentryHTTPService,
            PostgresSentryPrincipalRegistry,
            SentryServicePrincipal,
        )
        from anima_ha.sentry_voice_settings import SentryVoiceSettingsStore

        token_path = directory / "client.token"
        token = private_client_token(token_path)
        client_id = f"owner-household-{household_id}"
        principal = SentryServicePrincipal.from_secret(
            client_id=client_id,
            household_id=household_id,
            provider_id="sentry",
            token=token,
        )
        registry = PostgresSentryPrincipalRegistry(database_url)
        from anima_ha.sentry_service import ServiceAuthError

        try:
            registry.ensure_registered(principal, token)
        except ServiceAuthError as exc:
            raise OwnerBoundaryError("OWNER_CLIENT_REVOKED_OR_ROTATED") from exc
        os.chmod(self.socket_path, 0o600)
        if socket_group is not None:
            os.chown(self.socket_path, -1, socket_group)
            os.chmod(self.socket_path, 0o660)
        self.server.service = CoreSentryHTTPService(
            core.sentry_boundary(),
            lambda: private_client_token(token_path),
            service_principal=principal,
            principal_registry=registry,
            live_result_publisher=PostgresSentryLivePublisher(database_url),
            auto_wake_claims=auto_wake_claims,
            voice_settings_store=SentryVoiceSettingsStore(database_url),
            personality_store=SentryPersonalityStore(database_url),
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True, name="anima-owner-boundary"
        )
        self.thread.start()
        self.review_runner: Any | None = None
        if getattr(core, "learning_service", None) is not None:
            from anima_ha.learning_review_runner import LearningReviewRunner

            self.review_runner = LearningReviewRunner(
                core, core.learning_service, household_id, reconcile=True
            )
            self.review_runner.start()

    def close(self) -> None:
        if self.review_runner is not None:
            self.review_runner.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
