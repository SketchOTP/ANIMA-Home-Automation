"""Owner-authorized HA commissioning and private connection persistence.

Only the server-side OAuth exchange supplies VerifiedHAOwner. No browser/model
payload can select a household role, provider identity, credential or endpoint.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    ProviderReference,
    RelationshipType,
)


class HASetupError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedHAOwner:
    user_id: str
    name: str
    household_name: str
    timezone: str
    token: str = field(repr=False)


class HAConnectionStore:
    """Small private credential file, separate from PostgreSQL backup/evidence."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, Any] | None:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise HASetupError("HA_CREDENTIAL_FILE_UNSAFE") from exc
        with os.fdopen(fd, "r", encoding="utf-8") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o077
                or info.st_uid != os.geteuid()
                or info.st_size > 16_384
            ):
                raise HASetupError("HA_CREDENTIAL_FILE_UNSAFE")
            try:
                value = json.loads(stream.read(16_385))
                if not isinstance(value, dict) or value.get("version") != 1:
                    raise ValueError
                for key in ("token", "user_id", "instance_id", "household_id", "base_url"):
                    if not isinstance(value.get(key), str) or not value[key]:
                        raise ValueError
                UUID(value["instance_id"])
                UUID(value["household_id"])
            except (ValueError, TypeError, KeyError) as exc:
                raise HASetupError("HA_CREDENTIAL_FILE_INVALID") from exc
            return value

    def save_new(self, value: dict[str, Any]) -> None:
        existing = self.read()
        if existing is not None:
            if any(existing[key] != value[key] for key in ("user_id", "instance_id", "base_url")):
                raise HASetupError("HA_CONNECTION_ALREADY_COMMISSIONED")
            return
        parent = self.path.parent
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid != os.geteuid():
            raise HASetupError("HA_CREDENTIAL_DIRECTORY_UNSAFE")
        fd, temporary = tempfile.mkstemp(prefix=".ha-", dir=parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            # Exclusive link: concurrent owner callbacks cannot replace one another.
            try:
                os.link(temporary, self.path, follow_symlinks=False)
            except FileExistsError as exc:
                raise HASetupError("HA_CONNECTION_ALREADY_COMMISSIONED") from exc
            directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            os.unlink(temporary)


def configured_connection() -> dict[str, Any] | None:
    path = os.environ.get("ANIMA_HA_CONNECTION_FILE", "").strip()
    return HAConnectionStore(Path(path)).read() if path else None


def commission_owner(
    graph: PostgresHouseholdGraph,
    store: HAConnectionStore,
    owner: VerifiedHAOwner,
    *,
    instance_id: UUID,
    base_url: str,
) -> UUID:
    """Bootstrap a distinct owner household; never turn fixture members into owners."""
    namespace = uuid5(NAMESPACE_URL, f"anima://ha/{instance_id}/owner")
    household_id = uuid5(namespace, "household")
    person_id = uuid5(namespace, owner.user_id)
    value = {
        "version": 1,
        "instance_id": str(instance_id),
        "household_id": str(household_id),
        "user_id": owner.user_id,
        "base_url": base_url.rstrip("/"),
        "token": owner.token,
    }
    store.save_new(value)
    # Reusing existing nodes avoids resetting the owner's later name/preferences.
    household = graph.get_node(household_id) or CanonicalNode(
        household_id,
        NodeKind.HOUSEHOLD,
        owner.household_name or "My home",
        metadata={"source": "ha_owner_commissioning", "timezone": owner.timezone},
    )
    person = graph.get_node(person_id) or CanonicalNode(
        person_id,
        NodeKind.PERSON,
        owner.name or "Owner",
        metadata={"semantic_role": "owner", "source": "ha_verified_owner"},
    )
    graph.commission(
        CommissioningDocument(
            1,
            (household, person),
            (
                CanonicalRelationship(
                    uuid5(namespace, "membership"),
                    RelationshipType.MEMBER_OF,
                    person_id,
                    household_id,
                ),
            ),
            provider_references=(
                ProviderReference(
                    uuid5(namespace, "owner-reference"),
                    "home_assistant",
                    str(instance_id),
                    "user",
                    owner.user_id,
                    person_id,
                    metadata={"provenance": "ha_oauth_verified_owner"},
                ),
            ),
        )
    )
    return household_id
