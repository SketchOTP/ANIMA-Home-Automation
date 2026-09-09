"""Private client for SENTRY's local biometric-enrollment boundary.

ANIMA never opens SENTRY's SQLite database or camera directly.  This client is
fixed to loopback HTTP, fixed routes, and a private bearer-token file.  Raw
camera previews are returned to the current authenticated UI request only and
are never written by this module.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class SentryIdentityProfileError(RuntimeError):
    """The local SENTRY identity service rejected or could not complete work."""


class SentryIdentityProfileClient:
    _POST_PATHS = {
        "start": "/v1/identity/enrollment/start",
        "capture": "/v1/identity/enrollment/capture",
        "remove_sample": "/v1/identity/enrollment/remove-sample",
        "commit": "/v1/identity/enrollment/commit",
        "cancel": "/v1/identity/enrollment/cancel",
        "delete": "/v1/identity/profiles/delete",
    }

    def __init__(self, base_url: str, token_file: Path, *, timeout: float = 8.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("SENTRY identity service must use loopback HTTP")
        if parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username:
            raise ValueError("SENTRY identity service URL must contain only scheme, host, and port")
        if timeout <= 0 or timeout > 20:
            raise ValueError("SENTRY identity timeout must be between 0 and 20 seconds")
        self.base_url = base_url.rstrip("/")
        self.token_file = token_file
        self.timeout = timeout

    @classmethod
    def from_environment(cls) -> SentryIdentityProfileClient | None:
        url = os.environ.get("ANIMA_SENTRY_IDENTITY_URL", "").strip()
        token = os.environ.get("ANIMA_SENTRY_IDENTITY_TOKEN_FILE", "").strip()
        if not url and not token:
            return None
        if not url or not token:
            raise ValueError("SENTRY identity URL and token file must be configured together")
        return cls(url, Path(token))

    def _token(self) -> str:
        path = self.token_file
        if path.is_symlink():
            raise SentryIdentityProfileError("SENTRY_IDENTITY_CREDENTIAL_UNSAFE")
        try:
            metadata = path.stat()
        except OSError as exc:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_CREDENTIAL_UNAVAILABLE") from exc
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o027:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_CREDENTIAL_UNSAFE")
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_CREDENTIAL_UNAVAILABLE") from exc
        if len(value) < 32 or len(value) > 256 or any(character.isspace() for character in value):
            raise SentryIdentityProfileError("SENTRY_IDENTITY_CREDENTIAL_INVALID")
        return value

    def _post(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._POST_PATHS[operation]
        request = Request(
            self.base_url + path,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 - fixed loopback
                raw = response.read(2_000_001)
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read(4096).decode("utf-8")).get("error")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                detail = None
            raise SentryIdentityProfileError(
                str(detail or "SENTRY_IDENTITY_REQUEST_REJECTED")
            ) from exc
        except (OSError, URLError) as exc:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_SERVICE_UNAVAILABLE") from exc
        if len(raw) > 2_000_000:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_RESPONSE_TOO_LARGE")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SentryIdentityProfileError("SENTRY_IDENTITY_RESPONSE_INVALID") from exc
        if not isinstance(value, dict):
            raise SentryIdentityProfileError("SENTRY_IDENTITY_RESPONSE_INVALID")
        return value

    def start(self, person_id: str, display_name: str) -> dict[str, Any]:
        return self._post(
            "start",
            {
                "person_id": person_id,
                "display_name": display_name,
                "target_samples": 8,
                "guided": True,
            },
        )

    def capture(self, person_id: str, session_id: str, pose: str) -> dict[str, Any]:
        return self._post(
            "capture", {"person_id": person_id, "session_id": session_id, "pose": pose}
        )

    def remove_sample(self, person_id: str, session_id: str, sample_id: str) -> dict[str, Any]:
        return self._post(
            "remove_sample",
            {"person_id": person_id, "session_id": session_id, "sample_id": sample_id},
        )

    def commit(self, person_id: str, session_id: str) -> dict[str, Any]:
        return self._post("commit", {"person_id": person_id, "session_id": session_id})

    def cancel(self, person_id: str, session_id: str) -> dict[str, Any]:
        return self._post("cancel", {"person_id": person_id, "session_id": session_id})

    def delete(self, person_id: str) -> dict[str, Any]:
        return self._post("delete", {"person_id": person_id})
