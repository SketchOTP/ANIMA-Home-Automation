"""ANIMA-owned, server-side backup snapshot management.

The browser receives only bounded backup metadata.  PostgreSQL credentials,
archive paths, and the backup process remain inside Core.  This module does
not restore an active database; restore is deliberately a separate,
maintenance-window operation until the process-lifecycle contract is defined.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from psycopg.conninfo import conninfo_to_dict

from anima_ha.db.migrate import migrate
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    PluginManifest,
    RuntimeKind,
    TrustClass,
)

BACKUP_SCHEMA_VERSION = "1"
BACKUP_PLUGIN_ID = "anima.system.backup"


class BackupError(RuntimeError):
    """Raised when a backup cannot be created or inspected safely."""


@dataclass(frozen=True, slots=True)
class BackupRecord:
    """Secret-free metadata for one server-owned PostgreSQL archive."""

    backup_id: str
    household_id: UUID
    captured_at: str
    size_bytes: int
    sha256: str
    schema_version: str = BACKUP_SCHEMA_VERSION
    restorable: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "captured_at": self.captured_at,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "schema_version": self.schema_version,
            "restorable": self.restorable,
        }


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


class BackupCoordinator:
    """Create, inspect, and restore backups without exposing database administration."""

    def __init__(
        self,
        database_url: str,
        backup_dir: str | Path,
        *,
        runner: Runner = subprocess.run,
        migrator: Callable[[str, int], list[str]] = migrate,
        truth_invalidator: Callable[[], None] | None = None,
        connect_timeout: int = 5,
    ) -> None:
        if not database_url.strip():
            raise BackupError("database URL is required")
        path = Path(backup_dir)
        if not path.is_absolute():
            raise BackupError("backup directory must be absolute")
        self.database_url = database_url
        self.backup_dir = path
        self.runner = runner
        self.migrator = migrator
        self.truth_invalidator = truth_invalidator
        self.connect_timeout = connect_timeout

    def _prepare_dir(self) -> None:
        self.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.backup_dir, 0o700)

    def _pg_dump_command(self) -> tuple[list[str], dict[str, str]]:
        try:
            values = conninfo_to_dict(self.database_url)
        except Exception as exc:  # pragma: no cover - psycopg owns parsing
            raise BackupError("database URL cannot be parsed") from exc
        password = values.pop("password", None)
        command = [
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-privileges",
        ]
        supported = {
            "host": "--host",
            "port": "--port",
            "user": "--username",
            "dbname": "--dbname",
        }
        for key, option in supported.items():
            value = values.get(key)
            if value not in (None, ""):
                command.extend([option, str(value)])
        if not any(item in command for item in ("--dbname", "--host")):
            raise BackupError("database URL has no usable connection target")
        environment = dict(os.environ)
        if password is not None:
            environment["PGPASSWORD"] = str(password)
        return command, environment

    def create(self, household_id: UUID) -> BackupRecord:
        self._prepare_dir()
        backup_id = str(uuid4())
        archive = self.backup_dir / f"{backup_id}.dump"
        manifest = self.backup_dir / f"{backup_id}.json"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.backup_dir,
                prefix=f".{backup_id}.",
                suffix=".dump.tmp",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                command, environment = self._pg_dump_command()
                completed = self.runner(
                    [*command, "--file", str(temporary)],
                    check=False,
                    env=environment,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
            if completed.returncode != 0:
                detail = completed.stderr.decode("utf-8", "replace")[:240]
                raise BackupError(f"pg_dump failed: {detail or 'unknown error'}")
            os.chmod(temporary, 0o600)
            temporary.replace(archive)
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            captured_at = datetime.now(UTC).isoformat()
            record = BackupRecord(
                backup_id=backup_id,
                household_id=household_id,
                captured_at=captured_at,
                size_bytes=archive.stat().st_size,
                sha256=digest,
            )
            self._write_manifest(manifest, record)
            return record
        except OSError as exc:
            raise BackupError("backup storage is unavailable") from exc
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _write_manifest(self, path: Path, record: BackupRecord) -> None:
        temporary = path.with_suffix(".json.tmp")
        # Household scope is server-side metadata.  It is deliberately not
        # returned by ``to_payload`` but must be present in the manifest so a
        # caller cannot make another household's archive appear to be theirs.
        payload = {**record.to_payload(), "household_id": str(record.household_id)}
        temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(path)
        os.chmod(path, 0o600)

    def list_for_household(self, household_id: UUID) -> list[BackupRecord]:
        if not self.backup_dir.exists():
            return []
        records: list[BackupRecord] = []
        for path in sorted(self.backup_dir.glob("*.json"), reverse=True):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                record = BackupRecord(
                    backup_id=str(payload["backup_id"]),
                    household_id=UUID(str(payload["household_id"])),
                    captured_at=str(payload["captured_at"]),
                    size_bytes=int(payload["size_bytes"]),
                    sha256=str(payload["sha256"]),
                    schema_version=str(payload.get("schema_version", BACKUP_SCHEMA_VERSION)),
                    restorable=bool(payload.get("restorable", True)),
                )
            except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
                continue
            if (
                record.household_id == household_id
                and (self.backup_dir / f"{record.backup_id}.dump").is_file()
            ):
                records.append(record)
        return records

    def inspect(self, household_id: UUID, backup_id: str) -> BackupRecord:
        if not backup_id or Path(backup_id).name != backup_id:
            raise BackupError("invalid backup reference")
        record = next(
            (item for item in self.list_for_household(household_id) if item.backup_id == backup_id),
            None,
        )
        if record is None:
            raise BackupError("backup is not available for this household")
        archive = self.backup_dir / f"{backup_id}.dump"
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return BackupRecord(
            backup_id=record.backup_id,
            household_id=record.household_id,
            captured_at=record.captured_at,
            size_bytes=archive.stat().st_size,
            sha256=digest,
            schema_version=record.schema_version,
            restorable=digest == record.sha256,
        )

    def _pg_restore_command(self) -> tuple[list[str], dict[str, str]]:
        try:
            values = conninfo_to_dict(self.database_url)
        except Exception as exc:  # pragma: no cover - psycopg owns parsing
            raise BackupError("database URL cannot be parsed") from exc
        password = values.pop("password", None)
        command = [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--no-privileges",
        ]
        supported = {
            "host": "--host",
            "port": "--port",
            "user": "--username",
            "dbname": "--dbname",
        }
        for key, option in supported.items():
            value = values.get(key)
            if value not in (None, ""):
                command.extend([option, str(value)])
        if not any(item in command for item in ("--dbname", "--host")):
            raise BackupError("database URL has no usable connection target")
        environment = dict(os.environ)
        if password is not None:
            environment["PGPASSWORD"] = str(password)
        return command, environment

    def _mark_truth_stale(self) -> None:
        if self.truth_invalidator is not None:
            self.truth_invalidator()
            return
        # Restored observations describe the database at backup time. They
        # must not be presented as current physical reality until HA performs
        # a fresh reconciliation.
        import psycopg

        with psycopg.connect(self.database_url, connect_timeout=self.connect_timeout) as connection:
            with connection.cursor() as cursor:
                cursor.execute("UPDATE anima_truth_state SET status='STALE', updated_at=now()")
            connection.commit()

    def restore(self, household_id: UUID, backup_id: str, *, confirm: bool = False) -> BackupRecord:
        """Restore one validated archive into the configured ANIMA database.

        This is an explicitly confirmed, Core-only maintenance mutation. The
        archive is restored with PostgreSQL's cleanup and single-transaction
        safeguards, current migrations are applied, and all restored Truth is
        invalidated until a provider performs fresh observation.
        """
        if not confirm:
            raise BackupError("explicit restore confirmation is required")
        record = self.inspect(household_id, backup_id)
        if not record.restorable:
            raise BackupError("backup integrity validation failed")
        archive = self.backup_dir / f"{record.backup_id}.dump"
        command, environment = self._pg_restore_command()
        completed = self.runner(
            [*command, str(archive)],
            check=False,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            detail = completed.stderr.decode("utf-8", "replace")[:240]
            raise BackupError(f"pg_restore failed: {detail or 'unknown error'}")
        try:
            self.migrator(self.database_url, self.connect_timeout)
            self._mark_truth_stale()
        except Exception as exc:
            raise BackupError("restore completed but recovery reconciliation failed") from exc
        return record


class BackupNativePlugin:
    """Typed Core operations for owner-visible backup snapshots."""

    def __init__(self, coordinator: BackupCoordinator) -> None:
        self.coordinator = coordinator

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in BACKUP_MANIFEST.tools]

    def _invoke_scoped(self, name: str, arguments: dict[str, Any], household_id: UUID) -> Any:
        if name == "list_backups":
            return {
                "status": "SUCCEEDED",
                "items": [
                    item.to_payload() for item in self.coordinator.list_for_household(household_id)
                ],
            }
        if name == "create_backup":
            return {
                "status": "SUCCEEDED",
                "backup": self.coordinator.create(household_id).to_payload(),
            }
        if name == "inspect_backup":
            return {
                "status": "SUCCEEDED",
                "backup": self.coordinator.inspect(
                    household_id, str(arguments["backup_id"])
                ).to_payload(),
            }
        if name == "restore_backup":
            return {
                "status": "SUCCEEDED",
                "operation": "backup.restore",
                "backup": self.coordinator.restore(
                    household_id,
                    str(arguments["backup_id"]),
                    confirm=bool(arguments["confirm"]),
                ).to_payload(),
                "physical_truth": "UNKNOWN_UNTIL_REOBSERVED",
                "reobserve_required": True,
            }
        raise BackupError("unknown backup operation")

    def invoke_for_household(
        self, name: str, arguments: dict[str, Any], timeout: float, household_id: UUID
    ) -> Any:
        del timeout
        return self._invoke_scoped(name, arguments, household_id)

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise BackupError("household scope is required")


BACKUP_MANIFEST = PluginManifest(
    plugin_id=BACKUP_PLUGIN_ID,
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="ANIMA backup",
    description="Create and validate server-owned ANIMA database snapshots",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.backup",),
    tools=(
        {
            "name": "list_backups",
            "description": "List server-owned backup snapshots for the current household",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "items"],
                "properties": {"status": {"const": "SUCCEEDED"}, "items": {"type": "array"}},
                "additionalProperties": False,
            },
            "semantic_action": "backup.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "LOCAL_TRUSTED",
        },
        {
            "name": "restore_backup",
            "description": (
                "Restore a validated server-owned snapshot after explicit owner confirmation"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "backup_id": {"type": "string", "maxLength": 64},
                    "confirm": {"type": "boolean", "const": True},
                },
                "required": ["backup_id", "confirm"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "operation", "backup", "physical_truth"],
                "properties": {
                    "status": {"const": "SUCCEEDED"},
                    "operation": {"const": "backup.restore"},
                    "backup": {"type": "object"},
                    "physical_truth": {"const": "UNKNOWN_UNTIL_REOBSERVED"},
                    "reobserve_required": {"type": "boolean"},
                },
                "additionalProperties": False,
            },
            "semantic_action": "backup.restore",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": "NONE",
            "external_content_trust": "LOCAL_TRUSTED",
        },
        {
            "name": "create_backup",
            "description": "Create a server-owned ANIMA PostgreSQL backup snapshot",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "backup"],
                "properties": {"status": {"const": "SUCCEEDED"}, "backup": {"type": "object"}},
                "additionalProperties": False,
            },
            "semantic_action": "backup.create",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": "NONE",
            "external_content_trust": "LOCAL_TRUSTED",
        },
        {
            "name": "inspect_backup",
            "description": "Validate one server-owned backup snapshot without restoring it",
            "input_schema": {
                "type": "object",
                "properties": {
                    "backup_id": {"type": "string", "maxLength": 64},
                },
                "required": ["backup_id"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "backup"],
                "properties": {"status": {"const": "SUCCEEDED"}, "backup": {"type": "object"}},
                "additionalProperties": False,
            },
            "semantic_action": "backup.inspect",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "LOCAL_TRUSTED",
        },
    ),
    source="builtin:anima_ha.backup",
)
