from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import UUID

import pytest

from anima_ha.backup import BackupCoordinator, BackupError

HOUSEHOLD_A = UUID("00000000-0000-0000-0000-000000000001")
HOUSEHOLD_B = UUID("00000000-0000-0000-0000-000000000002")


def _runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
    output = Path(args[args.index("--file") + 1])
    output.write_bytes(b"synthetic pg custom archive")
    return subprocess.CompletedProcess(args, 0, b"", b"")


def test_backup_creation_keeps_household_scope_server_side(tmp_path: Path) -> None:
    coordinator = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=_runner,
    )

    record = coordinator.create(HOUSEHOLD_A)

    assert record.to_payload()["backup_id"] == record.backup_id
    assert "household_id" not in record.to_payload()
    manifest = json.loads((tmp_path / f"{record.backup_id}.json").read_text())
    assert manifest["household_id"] == str(HOUSEHOLD_A)
    assert [item.backup_id for item in coordinator.list_for_household(HOUSEHOLD_A)] == [
        record.backup_id
    ]
    assert coordinator.list_for_household(HOUSEHOLD_B) == []


def test_backup_inspect_detects_archive_tampering(tmp_path: Path) -> None:
    coordinator = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=_runner,
    )
    record = coordinator.create(HOUSEHOLD_A)
    archive = tmp_path / f"{record.backup_id}.dump"
    archive.write_bytes(b"changed")

    inspected = coordinator.inspect(HOUSEHOLD_A, record.backup_id)

    assert inspected.restorable is False
    assert inspected.sha256 != record.sha256


def test_backup_dump_never_receives_password_as_argument(tmp_path: Path) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []

    def recording_runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        output = Path(args[args.index("--file") + 1])
        output.write_bytes(b"archive")
        calls.append((args, kwargs["env"]))  # type: ignore[arg-type]
        return subprocess.CompletedProcess(args, 0, b"", b"")

    coordinator = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=recording_runner,
    )
    coordinator.create(HOUSEHOLD_A)

    args, environment = calls[0]
    assert "secret" not in " ".join(args)
    assert environment["PGPASSWORD"] == "secret"


def test_backup_restore_requires_explicit_confirmation(tmp_path: Path) -> None:
    coordinator = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=_runner,
    )
    record = coordinator.create(HOUSEHOLD_A)
    calls: list[list[str]] = []

    def restore_runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    restore = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=restore_runner,
        migrator=lambda _url, _timeout: [],
        truth_invalidator=lambda: None,
    )

    with pytest.raises(BackupError, match="explicit restore confirmation"):
        restore.restore(HOUSEHOLD_A, record.backup_id)
    assert calls == []


def test_backup_restore_is_validated_migrated_and_marks_truth_stale(tmp_path: Path) -> None:
    source = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=_runner,
    )
    record = source.create(HOUSEHOLD_A)
    calls: list[list[str]] = []
    migrations: list[tuple[str, int]] = []
    invalidations: list[bool] = []

    def restore_runner(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, b"", b"")

    restore = BackupCoordinator(
        "postgresql://anima:secret@example.test/anima",
        tmp_path,
        runner=restore_runner,
        migrator=lambda url, timeout: migrations.append((url, timeout)) or ["0010"],
        truth_invalidator=lambda: invalidations.append(True),
    )

    restored = restore.restore(HOUSEHOLD_A, record.backup_id, confirm=True)

    assert restored.backup_id == record.backup_id
    assert len(calls) == 1
    assert "--clean" in calls[0]
    assert "--single-transaction" in calls[0]
    assert "secret" not in " ".join(calls[0])
    assert migrations == [("postgresql://anima:secret@example.test/anima", 5)]
    assert invalidations == [True]
