from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from anima_ha.owner_boundary import OwnerBoundary, OwnerBoundaryError
from anima_ha.sentry_service import (
    PostgresSentryPrincipalRegistry,
    SentryServicePrincipal,
    ServiceAuthError,
    _Handler,
    _UnixHTTPServer,
    serve,
)


def test_duplicate_owner_cannot_unlink_live_socket(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "core.sock"
    with _UnixHTTPServer(str(path), _Handler) as first:
        inode = path.stat().st_ino
        monkeypatch.setattr(
            "anima_ha.sentry_service.migrate", lambda *_: pytest.fail("duplicate migrated")
        )
        with pytest.raises(RuntimeError, match="BOUNDARY_ALREADY_RUNNING"):
            serve("unused", str(path), "unused", "unused")
        assert path.stat().st_ino == inode
        with socket.socket(socket.AF_UNIX) as probe:
            probe.connect(str(path))
        assert first.fileno() >= 0
    assert not path.exists()
    # Persistent lock inode is reused, not deleted on shutdown.
    assert Path(str(path) + ".lock").exists()
    with _UnixHTTPServer(str(path), _Handler):
        assert path.exists()


def test_noncooperating_listener_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "core.sock"
    with socket.socket(socket.AF_UNIX) as other:
        other.bind(str(path))
        other.listen(1)
        inode = path.stat().st_ino
        with pytest.raises(RuntimeError, match="BOUNDARY_ALREADY_RUNNING"):
            _UnixHTTPServer(str(path), _Handler)
        assert path.stat().st_ino == inode


def test_close_never_removes_replacement_inode(tmp_path: Path) -> None:
    path = tmp_path / "core.sock"
    first = _UnixHTTPServer(str(path), _Handler)
    path.unlink()
    with socket.socket(socket.AF_UNIX) as replacement:
        replacement.bind(str(path))
        inode = path.stat().st_ino
        first.server_close()
        first.server_close()
        assert path.stat().st_ino == inode


def test_abandoned_socket_recoverable_but_symlink_rejected(tmp_path: Path) -> None:
    path = tmp_path / "core.sock"
    with socket.socket(socket.AF_UNIX) as stale:
        stale.bind(str(path))
    with _UnixHTTPServer(str(path), _Handler):
        assert path.exists()
    target = tmp_path / "protected"
    target.write_text("preserve")
    path.symlink_to(target)
    with pytest.raises(RuntimeError, match="BOUNDARY_SOCKET_PATH_UNSAFE"):
        _UnixHTTPServer(str(path), _Handler)
    assert target.read_text() == "preserve"


def test_owner_boundary_checks_collision_before_token_or_registration(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    core = SimpleNamespace(intelligence_provider=SimpleNamespace(value="sentry"))
    with _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler):
        with pytest.raises(OwnerBoundaryError, match="BOUNDARY_ALREADY_RUNNING"):
            OwnerBoundary(core, UUID(int=1), "unused", tmp_path)
    assert not (tmp_path / "client.token").exists()


def test_external_ui_never_provisions_or_binds_even_with_foreign_uid_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from anima_ha.ui_api import UIConfig, UIService

    lock = tmp_path / "core.sock.lock"
    lock.write_text("preserve")
    lock.chmod(0)
    monkeypatch.setenv("ANIMA_OWNER_BOUNDARY_MODE", "external")
    monkeypatch.setenv("ANIMA_OWNER_BOUNDARY_DIR", str(tmp_path))
    service = UIService(config=UIConfig(test_auth_enabled=True))
    service.core_runtime = object()
    service.start_owner_boundary()
    assert service.owner_boundary_status == "EXTERNAL_UNVERIFIED"
    assert service._owner_boundary is None
    assert not (tmp_path / "client.token").exists()
    assert not (tmp_path / "core.sock").exists()


def test_restart_registration_is_insert_only_and_never_reenables_revocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Mock()
    connection.__enter__ = Mock(return_value=connection)
    connection.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("anima_ha.sentry_service.psycopg.connect", Mock(return_value=connection))
    principal = SentryServicePrincipal.from_secret(
        client_id="test",
        household_id=UUID(int=1),
        provider_id="sentry",
        token="fixture",
    )
    registry = PostgresSentryPrincipalRegistry("unused")
    monkeypatch.setattr(registry, "active", Mock(return_value=False))
    with pytest.raises(ServiceAuthError, match="revoked or rotated"):
        registry.ensure_registered(principal, "fixture")
    sql = connection.execute.call_args.args[0]
    assert "ON CONFLICT (client_id) DO NOTHING" in sql
    assert "DO UPDATE" not in sql


def test_owner_revocation_classification_and_failed_initialization_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    core = SimpleNamespace(intelligence_provider=SimpleNamespace(value="sentry"))
    monkeypatch.setattr(
        PostgresSentryPrincipalRegistry,
        "ensure_registered",
        Mock(side_effect=ServiceAuthError("revoked or rotated")),
    )
    with pytest.raises(OwnerBoundaryError, match="OWNER_CLIENT_REVOKED_OR_ROTATED"):
        OwnerBoundary(core, UUID(int=1), "unused", tmp_path)
    assert not (tmp_path / "core.sock").exists()
    with _UnixHTTPServer(str(tmp_path / "core.sock"), _Handler):
        pass


def test_core_normal_stop_closes_socket_and_watcher_without_serving_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    watcher = Mock()
    core = SimpleNamespace(
        journal_event_watcher=watcher, learning_service=None, sentry_boundary=lambda: Mock()
    )
    token = tmp_path / "token"
    token.write_text("synthetic-test-token-longer-than-thirty-two")
    token.chmod(0o600)
    monkeypatch.setenv("ANIMA_SENTRY_CLIENT_ID", "fixture")
    monkeypatch.setenv("ANIMA_SENTRY_HOUSEHOLD_ID", str(UUID(int=1)))
    monkeypatch.delenv("ANIMA_SENTRY_AUTOWAKE_ENABLED_AT", raising=False)
    monkeypatch.setattr("anima_ha.sentry_service.migrate", Mock())
    monkeypatch.setattr("anima_ha.sentry_service.build_postgres_core", Mock(return_value=core))
    monkeypatch.setattr(PostgresSentryPrincipalRegistry, "ensure_registered", Mock())
    stopped = threading.Event()
    stopped.set()
    path = tmp_path / "core.sock"
    serve("unused", str(path), str(token), "unused", stop_event=stopped)
    assert not path.exists()
    watcher.stop.assert_called_once_with()
