from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from anima_ha.owner_boundary import OwnerBoundary, OwnerBoundaryError, private_client_token
from anima_ha.ui_api import UIConfig, UIService


def test_service_token_is_private_and_restart_stable(tmp_path: Path) -> None:
    path = tmp_path / "client.token"
    first = private_client_token(path)
    assert len(first) >= 32
    assert private_client_token(path) == first
    assert path.stat().st_mode & 0o777 == 0o600


def test_service_token_symlink_is_not_followed(tmp_path: Path) -> None:
    target = tmp_path / "private"
    target.write_text("synthetic-private-token-longer-than-thirty-two")
    target.chmod(0o600)
    link = tmp_path / "client.token"
    link.symlink_to(target)
    with pytest.raises(RuntimeError, match="regular file"):
        private_client_token(link)


def test_missing_connection_does_not_disable_household_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANIMA_OWNER_BOUNDARY_DIR", str(tmp_path / "service"))
    monkeypatch.setenv("ANIMA_HA_CONNECTION_FILE", str(tmp_path / "ha.json"))
    service = UIService(config=UIConfig(test_auth_enabled=True))
    # Only the setup guard is exercised; no parallel fake Core implementation.
    service.core_runtime = object()
    service.start_owner_boundary()
    assert service.owner_boundary_status == "HA_SETUP_REQUIRED"
    assert service._owner_boundary is None
    assert service.read_model is not None


def test_owner_boundary_never_enables_embedded_cognition(tmp_path: Path) -> None:
    class ReferenceCore:
        class intelligence_provider:
            value = "embedded_reference"

    core: Any = ReferenceCore()
    with pytest.raises(OwnerBoundaryError, match="SENTRY_MODE_REQUIRED"):
        OwnerBoundary(core, UUID(int=1), "unused", tmp_path / "service")
    assert not (tmp_path / "service").exists()


@pytest.mark.parametrize("permissions", [0o770, 0o707, 0o777])
def test_owner_boundary_rejects_writable_or_public_directory(
    tmp_path: Path, permissions: int
) -> None:
    class SentryCore:
        class intelligence_provider:
            value = "sentry"

    directory = tmp_path / "service"
    directory.mkdir()
    directory.chmod(permissions)
    core: Any = SentryCore()
    with pytest.raises(OwnerBoundaryError, match="BOUNDARY_DIRECTORY_UNSAFE"):
        OwnerBoundary(core, UUID(int=1), "unused", directory)
    assert not (directory / "client.token").exists()
