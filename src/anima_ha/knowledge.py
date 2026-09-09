"""Narrow, local-filesystem knowledge notes; no MemoryService or database writes.

Runtime wiring is deliberately separate. The Core must classify note reads AND
mutation arguments before enabling this plugin: metadata-only receipts do not
prevent an upstream gateway from journaling its input. No secret/restricted
content may be supplied. Notes are data, never owner identity or policy.

Only an existing, private native-Linux managed root is accepted. The host mounts
MEMORY/ANIMA only; this adapter owns <household UUID>/ below it, not the shared
vault or .obsidian. Private mode uses 0700/0600. Explicit configured owner/group
sharing uses 2770 directories/0660 files; no existing permissions are changed.
JSON frontmatter is supported
by Obsidian: https://obsidian.md/help/properties . Retraction/expiry replace the
file with a body-free tombstone; neither promises forensic or backup erasure.
Reads project expiry without writing; purge_expired explicitly writes tombstones.
Source references are attributed claims, not resolved/verified by this adapter.
All readers/writers should use these tools: flock serializes cooperating Core
writers, not arbitrary same-UID editors. Invalid externally edited digests fail
closed. The gateway, not note content, remains responsible for authorization.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    ExternalContentTrust,
    Idempotency,
    InvocationContext,
    PluginManifest,
    PluginValidationError,
    RuntimeKind,
    TrustClass,
)

MAX_NOTES = 10000
MAX_FILE_BYTES = 16384
DEFAULT_MANAGED_ROOT = Path("/home/sketch/Documents/MEMORY/ANIMA")
MAX_RETRIEVAL_BYTES = 16384
# A small public DDC subset, not a copy of the schedule. Decimal suffixes are
# bounded local refinements, not claims of a licensed full schedule.
# https://www.oclc.org/content/dam/oclc/dewey/resources/summaries/deweysummaries.pdf
DEWEY_DIVISIONS = frozenset({"000", "100", "300", "600", "640", "900", "920"})
NOTE_TYPES = ("event", "profile", "preference", "routine", "lesson")
CLASSIFICATIONS = ("SENTRY_INFERENCE", "OBSERVATION", "USER_STATED", "DISCOVERED")
SOURCE_KINDS = (
    "event",
    "truth",
    "graph",
    "memory",
    "note",
    "request",
    "tool_result",
    "test",
    "external",
)
_FIELDS = {
    "title",
    "body",
    "note_type",
    "classifier",
    "classification",
    "confidence",
    "source_refs",
    "observed_at",
    "enabled",
    "retention_days",
    "person_refs",
}
_REQUIRED = _FIELDS - {"observed_at", "enabled", "retention_days", "person_refs"}
_RECEIPT_FIELDS = {
    "note_id",
    "digest",
    "status",
    "classification",
    "inferred",
    "enabled",
    "created_at",
    "updated_at",
    "expires_at",
    "household_id",
    "principal_id",
    "correlation_id",
    "tool_request_id",
    "previous_digest",
}
_INTERNAL_FIELDS = {"create_request_digest", "created_principal_id", "last_request_digest"}


class KnowledgeValidationError(PluginValidationError):
    """Safe, content-free contract or filesystem error."""


class KnowledgeConflict(KnowledgeValidationError):
    """A digest or idempotency key no longer matches."""


@dataclass(frozen=True, slots=True)
class KnowledgeConfig:
    managed_root: Path = DEFAULT_MANAGED_ROOT
    owner_uid: int | None = None
    shared_group_id: int | None = None

    @classmethod
    def from_environment(cls, values: dict[str, str] | None = None) -> KnowledgeConfig:
        source = os.environ if values is None else values
        root = source.get("ANIMA_KNOWLEDGE_ROOT", "").strip()
        if not root:
            raise KnowledgeValidationError("KNOWLEDGE_NOT_CONFIGURED")
        try:
            owner = source.get("ANIMA_KNOWLEDGE_OWNER_UID", "").strip()
            group = source.get("ANIMA_KNOWLEDGE_GROUP_ID", "").strip()
            return cls(Path(root), int(owner) if owner else None, int(group) if group else None)
        except ValueError:
            raise KnowledgeValidationError("KNOWLEDGE_SHARED_CONFIG_INVALID") from None

    def __post_init__(self) -> None:
        if (self.owner_uid is None) != (self.shared_group_id is None):
            raise KnowledgeValidationError("KNOWLEDGE_SHARED_CONFIG_INCOMPLETE")
        if self.owner_uid is not None and (
            type(self.owner_uid) is not int
            or self.owner_uid < 0
            or type(self.shared_group_id) is not int
            or self.shared_group_id < 0
        ):
            raise KnowledgeValidationError("KNOWLEDGE_SHARED_CONFIG_INVALID")

    @property
    def directory_mode(self) -> int:
        return 0o2770 if self.shared_group_id is not None else 0o700

    @property
    def file_mode(self) -> int:
        return 0o660 if self.shared_group_id is not None else 0o600


def _json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_ID")
    try:
        normalized = str(UUID(value))
    except ValueError:
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_ID") from None
    if normalized != value:
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_ID")
    return normalized


def _time(value: Any) -> datetime:
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_TIME") from None


def _text(value: Any, maximum: int) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_TEXT")
    return value


def _fields(arguments: dict[str, Any]) -> dict[str, Any]:
    if set(arguments) - _FIELDS or not _REQUIRED <= set(arguments):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_FIELDS")
    value = dict(arguments)
    value["title"] = _text(value["title"], 120)
    value["body"] = _text(value["body"], 4096)
    if len(value["body"].encode("utf-8")) > 4096:
        raise KnowledgeValidationError("KNOWLEDGE_BODY_TOO_LARGE")
    if value["note_type"] not in NOTE_TYPES or value["classification"] not in CLASSIFICATIONS:
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_CLASSIFICATION")
    classifier = value["classifier"]
    if (
        not isinstance(classifier, str)
        or not re.fullmatch(r"\d{3}(?:\.\d{1,3})?", classifier)
        or classifier[:3] not in DEWEY_DIVISIONS
    ):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_CLASSIFIER")
    confidence = value["confidence"]
    if (
        type(confidence) not in (int, float)
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_CONFIDENCE")
    refs = value["source_refs"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 12:
        raise KnowledgeValidationError("KNOWLEDGE_SOURCE_REQUIRED")
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or set(ref) != {"kind", "source_id", "meaning"}
            or ref["kind"] not in SOURCE_KINDS
            or not isinstance(ref["source_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:._-]{0,127}", ref["source_id"])
        ):
            raise KnowledgeValidationError("KNOWLEDGE_INVALID_SOURCE")
        _text(ref["meaning"], 240)
    if value["classification"] == "USER_STATED" and not any(
        ref["kind"] == "request" for ref in refs
    ):
        raise KnowledgeValidationError("KNOWLEDGE_STATEMENT_SOURCE_REQUIRED")
    people = value.get("person_refs", [])
    if not isinstance(people, list) or len(people) > 8:
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_PERSON_REFS")
    people = [_uuid(person) for person in people]
    if len(set(people)) != len(people) or any(UUID(person).int == 0 for person in people):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_PERSON_REFS")
    value["person_refs"] = people
    value["observed_at"] = value.get("observed_at")
    if value["observed_at"] is not None:
        value["observed_at"] = _time(value["observed_at"]).isoformat()
    if value["classification"] == "OBSERVATION" and value["observed_at"] is None:
        raise KnowledgeValidationError("KNOWLEDGE_OBSERVATION_TIME_REQUIRED")
    value["enabled"] = value.get("enabled", True)
    if type(value["enabled"]) is not bool:
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_ENABLED")
    days = value.get("retention_days")
    if days is not None and (type(days) is not int or not 1 <= days <= 36500):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_RETENTION")
    value["retention_days"] = days
    return value


def _safe_inode(fd: int, config: KnowledgeConfig, *, directory: bool) -> None:
    info = os.fstat(fd)
    kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    required_mode = config.directory_mode if directory else config.file_mode
    if (
        not kind
        or info.st_uid not in {os.geteuid(), config.owner_uid}
        or (config.shared_group_id is not None and info.st_gid != config.shared_group_id)
        or stat.S_IMODE(info.st_mode) != required_mode
        or (not directory and info.st_nlink != 1)
    ):
        raise KnowledgeValidationError("KNOWLEDGE_UNSAFE_PERMISSIONS_OR_LINK")


def _native_mount(path: Path) -> None:
    """Reject remote/FUSE filesystems: flock/replace qualification is local only."""
    matches: list[tuple[int, str]] = []
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        mount = left.split()[4]
        mount = re.sub(r"\\([0-7]{3})", lambda found: chr(int(found[1], 8)), mount)
        if path.is_relative_to(Path(mount)):
            matches.append((len(mount), right.split()[0]))
    if not matches or max(matches)[1] not in {
        "ext4",
        "ext3",
        "xfs",
        "btrfs",
        "zfs",
        "tmpfs",
        "overlay",
        "ramfs",
    }:
        raise KnowledgeValidationError("KNOWLEDGE_NATIVE_FILESYSTEM_REQUIRED")


@contextmanager
def _root(config: KnowledgeConfig) -> Iterator[int]:
    path = config.managed_root
    if (
        not path.is_absolute()
        or len(path.parts) < 3
        or ".." in path.parts
        or path
        in (
            Path.home(),
            DEFAULT_MANAGED_ROOT.parent,
            Path("/srv/ATLAS"),
            Path("/srv/ATLAS/500_MEMORY"),
            Path("/srv/ATLAS/500_MEMORY/MEMORY"),
        )
    ):
        raise KnowledgeValidationError("KNOWLEDGE_INVALID_VAULT_ROOT")
    _native_mount(path)
    if config.shared_group_id is not None and config.shared_group_id not in {
        *os.getgroups(),
        os.getegid(),
    }:
        raise KnowledgeValidationError("KNOWLEDGE_SHARED_GROUP_UNAVAILABLE")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = following
        _safe_inode(fd, config, directory=True)
        yield fd
    finally:
        os.close(fd)


@contextmanager
def _directory(
    parent: int, name: str, config: KnowledgeConfig, *, create: bool = True
) -> Iterator[int]:
    created = False
    try:
        if create:
            os.mkdir(name, config.directory_mode, dir_fd=parent)
            created = True
            os.fsync(parent)
    except FileExistsError:
        pass
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        if created:
            os.fchmod(fd, config.directory_mode)
        _safe_inode(fd, config, directory=True)
        yield fd
    finally:
        os.close(fd)


def _read(fd: int, name: str, config: KnowledgeConfig) -> bytes:
    opened = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    try:
        _safe_inode(opened, config, directory=False)
        if os.fstat(opened).st_size > MAX_FILE_BYTES:
            raise KnowledgeValidationError("KNOWLEDGE_FILE_TOO_LARGE")
        with os.fdopen(opened, "rb", closefd=False) as stream:
            value = stream.read(MAX_FILE_BYTES + 1)
        if len(value) > MAX_FILE_BYTES:
            raise KnowledgeValidationError("KNOWLEDGE_FILE_TOO_LARGE")
        return value
    finally:
        os.close(opened)


def _write(fd: int, name: str, note: dict[str, Any], config: KnowledgeConfig) -> None:
    metadata = {key: value for key, value in note.items() if key != "body"}
    encoded = ("---\n" + _json(metadata) + "\n---\n" + note.get("body", "")).encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise KnowledgeValidationError("KNOWLEDGE_FILE_TOO_LARGE")
    temporary = f".pending-{uuid4()}"
    opened = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, config.file_mode, dir_fd=fd
    )
    try:
        with os.fdopen(opened, "wb") as stream:
            os.fchmod(stream.fileno(), config.file_mode)
            _safe_inode(stream.fileno(), config, directory=False)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
        os.fsync(fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=fd)
        except FileNotFoundError:
            pass


class KnowledgeNativePlugin:
    def __init__(
        self,
        config: KnowledgeConfig,
        *,
        clock: Callable[[], datetime] | None = None,
        person_validator: Callable[[UUID, UUID], bool] | None = None,
    ) -> None:
        self.config = config
        self.clock = clock or (lambda: datetime.now(UTC))
        self.person_validator = person_validator

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env
        try:
            with _root(self.config):
                pass
        except OSError:
            raise KnowledgeValidationError("KNOWLEDGE_VAULT_UNAVAILABLE") from None

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(tool) for tool in KNOWLEDGE_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise KnowledgeValidationError("knowledge requires trusted invocation context")

    @contextmanager
    def _namespace(
        self, household: UUID, *, read_only: bool = False
    ) -> Iterator[tuple[int, list[str]]]:
        with _root(self.config) as managed:
            with ExitStack() as stack:
                try:
                    directory = stack.enter_context(
                        _directory(managed, str(household), self.config, create=not read_only)
                    )
                except FileNotFoundError:
                    if not read_only:
                        raise
                    yield managed, []
                    return
                created_lock = False
                try:
                    if read_only:
                        lock = os.open(
                            ".lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                        )
                    else:
                        lock = os.open(
                            ".lock",
                            os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            self.config.file_mode,
                            dir_fd=directory,
                        )
                        created_lock = True
                except FileExistsError:
                    lock = os.open(
                        ".lock", os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
                    )
                try:
                    if created_lock:
                        os.fchmod(lock, self.config.file_mode)
                    _safe_inode(lock, self.config, directory=False)
                    try:
                        fcntl.flock(
                            lock, (fcntl.LOCK_SH if read_only else fcntl.LOCK_EX) | fcntl.LOCK_NB
                        )
                    except BlockingIOError:
                        raise KnowledgeConflict("KNOWLEDGE_BUSY") from None
                    names: list[str] = []
                    with os.scandir(directory) as entries:
                        for index, entry in enumerate(entries):
                            if index > MAX_NOTES + 100:
                                raise KnowledgeValidationError("KNOWLEDGE_NAMESPACE_LIMIT")
                            if entry.name == ".lock":
                                continue
                            if entry.name.startswith(".pending-"):
                                _uuid(entry.name.removeprefix(".pending-"))
                                _read(directory, entry.name, self.config)
                                if not read_only:
                                    os.unlink(entry.name, dir_fd=directory)
                                continue
                            if not entry.name.endswith(".md"):
                                raise KnowledgeValidationError("KNOWLEDGE_UNEXPECTED_FILE")
                            _uuid(entry.name[:-3])
                            info = entry.stat(follow_symlinks=False)
                            if (
                                not stat.S_ISREG(info.st_mode)
                                or info.st_nlink != 1
                                or info.st_uid not in {os.geteuid(), self.config.owner_uid}
                                or (
                                    self.config.shared_group_id is not None
                                    and info.st_gid != self.config.shared_group_id
                                )
                                or stat.S_IMODE(info.st_mode) != self.config.file_mode
                            ):
                                raise KnowledgeValidationError("KNOWLEDGE_UNSAFE_NOTE")
                            names.append(entry.name)
                            if len(names) > MAX_NOTES:
                                raise KnowledgeValidationError("KNOWLEDGE_NAMESPACE_LIMIT")
                    yield directory, sorted(names)
                finally:
                    os.close(lock)

    @staticmethod
    def _seal(note: dict[str, Any]) -> dict[str, Any]:
        note["digest"] = _digest({key: value for key, value in note.items() if key != "digest"})
        return note

    @staticmethod
    def _receipt(note: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "SUCCEEDED",
            "note": {key: value for key, value in note.items() if key in _RECEIPT_FIELDS},
        }

    def _tombstone(self, note: dict[str, Any], status: str, now: datetime) -> dict[str, Any]:
        retained = {
            key: value for key, value in note.items() if key in _RECEIPT_FIELDS | _INTERNAL_FIELDS
        }
        retained.update(
            status=status, enabled=False, previous_digest=note["digest"], updated_at=now.isoformat()
        )
        return self._seal(retained)

    def _load(
        self, directory: int, name: str, household: UUID, now: datetime, *, purge: bool = True
    ) -> dict[str, Any]:
        try:
            raw = _read(directory, name, self.config).decode("utf-8")
            if not raw.startswith("---\n"):
                raise ValueError
            header, separator, body = raw[4:].partition("\n---\n")
            note: dict[str, Any] = json.loads(header)
            if (
                not separator
                or not isinstance(note, dict)
                or "body" in note
                or note.get("note_id") != name[:-3]
                or note.get("household_id") != str(household)
                or note.get("classification") not in CLASSIFICATIONS
                or note.get("status") not in ("ACTIVE", "RETRACTED", "EXPIRED")
            ):
                raise ValueError
            if note["status"] == "ACTIVE":
                if set(note) - (_FIELDS | _RECEIPT_FIELDS | _INTERNAL_FIELDS):
                    raise ValueError
                note["body"] = body
                _fields({key: note[key] for key in _FIELDS if key in note})
            elif body or set(note) - (_RECEIPT_FIELDS | _INTERNAL_FIELDS):
                raise ValueError
            if note.get("digest") != _digest({k: v for k, v in note.items() if k != "digest"}):
                raise KnowledgeConflict("KNOWLEDGE_EXTERNAL_EDIT_UNRECONCILED")
            if (
                note["status"] == "ACTIVE"
                and note["expires_at"] is not None
                and _time(note["expires_at"]) <= now
            ):
                note = self._tombstone(note, "EXPIRED", _time(note["expires_at"]))
                if purge:
                    _write(directory, name, note, self.config)
            return note
        except KnowledgeConflict:
            raise
        except (ValueError, KeyError, UnicodeError):
            raise KnowledgeValidationError("KNOWLEDGE_CORRUPT_NOTE") from None

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> Any:
        del timeout
        try:
            return self._invoke(name, arguments, context)
        except FileNotFoundError:
            raise KnowledgeValidationError("KNOWLEDGE_NOT_FOUND_OR_VAULT_UNAVAILABLE") from None
        except OSError:
            raise KnowledgeValidationError("KNOWLEDGE_FILESYSTEM_UNAVAILABLE") from None

    def _validate_people(self, household: UUID, people: list[str]) -> None:
        for person in people:
            try:
                valid = (
                    self.person_validator is not None
                    and self.person_validator(household, UUID(person)) is True
                )
            except Exception:
                # Graph/provider errors must not echo names, query or note text.
                raise KnowledgeValidationError("KNOWLEDGE_PERSON_VALIDATION_UNAVAILABLE") from None
            if not valid:
                raise KnowledgeValidationError("KNOWLEDGE_PERSON_NOT_IN_HOUSEHOLD")

    def _retrieve(
        self,
        directory: int,
        names: list[str],
        context: InvocationContext,
        now: datetime,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        query = arguments.get("query", "").casefold().strip()
        tokens = list(dict.fromkeys(re.findall(r"\w+", query)))
        person = arguments.get("person_id")
        limit = arguments.get("limit", 10 if name == "search_notes" else 50)
        cursor = arguments.get("cursor")
        matches: list[dict[str, Any]] = []
        counts: dict[str, int] = {}
        for filename in names:
            note = self._load(directory, filename, context.household_id, now, purge=False)
            if note["status"] != "ACTIVE" or not note["enabled"]:
                continue
            if person is not None and person not in note.get("person_refs", []):
                continue
            if any(
                arguments.get(key) is not None and arguments[key] != note[key]
                for key in ("note_type", "classification")
            ):
                continue
            haystack = (
                note["title"] + " " + note["body"] + " " + _json(note["source_refs"])
            ).casefold()
            if not all(token in haystack for token in tokens):
                continue
            counts[note["note_type"]] = counts.get(note["note_type"], 0) + 1
            if cursor is not None and note["note_id"] <= cursor:
                continue
            item = {
                key: note[key]
                for key in (
                    "note_id",
                    "title",
                    "note_type",
                    "classifier",
                    "classification",
                    "confidence",
                    "digest",
                    "updated_at",
                    "expires_at",
                    "enabled",
                    "status",
                )
            }
            item["person_refs"] = note.get("person_refs", [])
            # References are canonical-shaped claims; not live Graph/Truth proof.
            item["person_refs_status"] = "NOT_REVALIDATED"
            if name == "search_notes":
                body = note["body"]
                starts = [body.casefold().find(token) for token in tokens]
                start = max(
                    0, min((position for position in starts if position >= 0), default=0) - 60
                )
                item.update(
                    excerpt=body[start : start + 320],
                    excerpt_truncated=start > 0 or len(body) > start + 320,
                    source_refs=note["source_refs"][:3],
                    source_refs_total=len(note["source_refs"]),
                    relevance=sum(
                        3 if token in note["title"].casefold() else 1 for token in tokens
                    ),
                )
            matches.append(item)
        if name == "search_notes":
            matches.sort(key=lambda item: (-item["relevance"], item["note_id"]))
        result: dict[str, Any] = {
            "status": "SUCCEEDED",
            "items": [],
            "matched": sum(counts.values()),
            "external_content_trust": "EXTERNAL_UNTRUSTED",
            "evidence_status": "ATTRIBUTED_UNVERIFIED",
            "authority": "NONE",
            "retrieval_mode": "DERIVED_LEXICAL_SCAN",
            "truncated": False,
            "next_cursor": None,
        }
        if name == "memory_index":
            result["counts_by_type"] = counts
        for item in matches[:limit]:
            candidate = {**result, "items": [*result["items"], item]}
            # Leave room for cursor/truncation metadata in the bounded response.
            if len(_json(candidate).encode("utf-8")) > MAX_RETRIEVAL_BYTES - 128:
                break
            result["items"].append(item)
        result["truncated"] = len(matches) > len(result["items"])
        if name == "memory_index" and result["truncated"] and result["items"]:
            result["next_cursor"] = result["items"][-1]["note_id"]
        return result

    def _invoke(self, name: str, arguments: dict[str, Any], context: InvocationContext) -> Any:
        now = self.clock()
        if now.tzinfo is None:
            raise KnowledgeValidationError("KNOWLEDGE_INVALID_CLOCK")
        now = now.astimezone(UTC)
        # Validate arguments before touching any filesystem path.
        allowed = {
            "list_notes": {"limit", "cursor", "query", "include_inactive"},
            "purge_expired": set(),
            "get_note": {"note_id"},
            "create_note": _FIELDS,
            "update_note": _FIELDS | {"note_id", "expected_digest"},
            "retract_note": {"note_id", "expected_digest"},
            "search_notes": {"query", "person_id", "note_type", "classification", "limit"},
            "memory_index": {"limit", "cursor"},
        }
        if name not in allowed or set(arguments) - allowed[name]:
            raise KnowledgeValidationError("KNOWLEDGE_INVALID_FIELDS")
        content = None
        if name in ("create_note", "update_note"):
            content = _fields({k: v for k, v in arguments.items() if k in _FIELDS})
            self._validate_people(context.household_id, content["person_refs"])
        note_id = None
        if name in ("get_note", "update_note", "retract_note"):
            note_id = _uuid(arguments.get("note_id"))
        if name in ("update_note", "retract_note") and (
            not isinstance(arguments.get("expected_digest"), str)
            or not re.fullmatch("[0-9a-f]{64}", arguments["expected_digest"])
        ):
            raise KnowledgeValidationError("KNOWLEDGE_DIGEST_REQUIRED")
        limit = arguments.get("limit", 50)
        cursor = arguments.get("cursor")
        query = arguments.get("query", "")
        inactive = arguments.get("include_inactive", False)
        if (
            type(limit) is not int
            or not 1 <= limit <= 50
            or not isinstance(query, str)
            or len(query) > 120
            or type(inactive) is not bool
        ):
            raise KnowledgeValidationError("KNOWLEDGE_INVALID_PAGE")
        if cursor is not None:
            _uuid(cursor)
        if name == "search_notes":
            person = arguments.get("person_id")
            if person is not None:
                person = _uuid(person)
                self._validate_people(context.household_id, [person])
            if (
                arguments.get("note_type") is not None
                and arguments["note_type"] not in NOTE_TYPES
                or arguments.get("classification") is not None
                and arguments["classification"] not in CLASSIFICATIONS
                or ("limit" in arguments and limit > 20)
                or len(re.findall(r"\w+", query)) > 12
                or (query and not re.search(r"\w", query))
                or not (query.strip() or person or arguments.get("note_type"))
            ):
                raise KnowledgeValidationError("KNOWLEDGE_INVALID_SEARCH")
        fingerprint = _digest({"operation": name, "arguments": arguments})
        read_only = name in ("list_notes", "get_note", "search_notes", "memory_index")
        with self._namespace(context.household_id, read_only=read_only) as (directory, names):
            if name in ("search_notes", "memory_index"):
                return self._retrieve(directory, names, context, now, name, arguments)
            if name == "purge_expired":
                expired = 0
                for filename in names:
                    note = self._load(directory, filename, context.household_id, now)
                    expired += note["status"] == "EXPIRED"
                return {"status": "SUCCEEDED", "scanned": len(names), "expired_tombstones": expired}
            if name == "list_notes":
                matches = []
                for filename in names:
                    note = self._load(directory, filename, context.household_id, now, purge=False)
                    if cursor is not None and note["note_id"] <= cursor:
                        continue
                    if not inactive and note["status"] != "ACTIVE":
                        continue
                    if (
                        query.casefold()
                        not in (note.get("title", "") + " " + note.get("body", "")).casefold()
                    ):
                        continue
                    matches.append(
                        {
                            k: v
                            for k, v in note.items()
                            if k not in _INTERNAL_FIELDS | {"body", "source_refs"}
                        }
                    )
                page = matches[:limit]
                return {
                    "status": "SUCCEEDED",
                    "items": page,
                    "next_cursor": page[-1]["note_id"] if len(matches) > limit else None,
                    "external_content_trust": "EXTERNAL_UNTRUSTED",
                }
            if name == "create_note":
                note_id = str(uuid5(context.household_id, str(context.tool_request_id)))
            filename = f"{note_id}.md"
            original = (
                self._load(directory, filename, context.household_id, now, purge=not read_only)
                if filename in names
                else None
            )
            if name == "get_note":
                if original is None:
                    raise KnowledgeValidationError("KNOWLEDGE_NOT_FOUND")
                return {
                    "status": "SUCCEEDED",
                    "note": {k: v for k, v in original.items() if k not in _INTERNAL_FIELDS},
                    "external_content_trust": "EXTERNAL_UNTRUSTED",
                    "evidence_status": "ATTRIBUTED_UNVERIFIED",
                    "authority": "NONE",
                }
            if original is not None:
                if name == "create_note":
                    if original["create_request_digest"] != fingerprint or original[
                        "created_principal_id"
                    ] != (str(context.principal_id) if context.principal_id else None):
                        raise KnowledgeConflict("KNOWLEDGE_IDEMPOTENCY_CONFLICT")
                    return self._receipt(original)
                if original["tool_request_id"] == str(context.tool_request_id):
                    if original["last_request_digest"] != fingerprint or original[
                        "principal_id"
                    ] != (str(context.principal_id) if context.principal_id else None):
                        raise KnowledgeConflict("KNOWLEDGE_IDEMPOTENCY_CONFLICT")
                    return self._receipt(original)
                if original["digest"] != arguments["expected_digest"]:
                    raise KnowledgeConflict("KNOWLEDGE_DIGEST_CONFLICT")
                if original["status"] != "ACTIVE":
                    raise KnowledgeConflict("KNOWLEDGE_NOTE_INACTIVE")
            elif name != "create_note":
                raise KnowledgeValidationError("KNOWLEDGE_NOT_FOUND")
            elif len(names) >= MAX_NOTES:
                raise KnowledgeValidationError("KNOWLEDGE_NAMESPACE_LIMIT")
            trusted = {
                "note_id": note_id,
                "household_id": str(context.household_id),
                "principal_id": str(context.principal_id) if context.principal_id else None,
                "correlation_id": str(context.episode_id) if context.episode_id else None,
                "tool_request_id": str(context.tool_request_id),
                "last_request_digest": fingerprint,
                "updated_at": now.isoformat(),
            }
            if name == "retract_note" and original is not None:
                note = self._tombstone(original, "RETRACTED", now)
                note.update(trusted)
            else:
                assert content is not None
                if original and "person_refs" not in arguments:
                    content["person_refs"] = original.get("person_refs", [])
                    self._validate_people(context.household_id, content["person_refs"])
                if original and "retention_days" not in arguments:
                    content["retention_days"] = original["retention_days"]
                    expires_at = original["expires_at"]
                else:
                    try:
                        expires_at = (
                            None
                            if content["retention_days"] is None
                            else (now + timedelta(days=content["retention_days"])).isoformat()
                        )
                    except OverflowError:
                        raise KnowledgeValidationError("KNOWLEDGE_INVALID_RETENTION") from None
                note = {
                    **content,
                    **trusted,
                    "status": "ACTIVE",
                    "inferred": content["classification"] == "SENTRY_INFERENCE",
                    "created_at": original["created_at"] if original else now.isoformat(),
                    "created_principal_id": original["created_principal_id"]
                    if original
                    else trusted["principal_id"],
                    "create_request_digest": original["create_request_digest"]
                    if original
                    else fingerprint,
                    "expires_at": expires_at,
                }
                if original:
                    note["previous_digest"] = original["digest"]
            _write(directory, filename, self._seal(note), self.config)
            return self._receipt(note)


_UUID_SCHEMA = {"type": "string", "format": "uuid"}
_CONTENT_SCHEMA: dict[str, Any] = {
    "title": {"type": "string", "minLength": 1, "maxLength": 120},
    "body": {"type": "string", "minLength": 1, "maxLength": 4096},
    "note_type": {"type": "string", "enum": list(NOTE_TYPES)},
    "classifier": {
        "type": "string",
        "pattern": r"^(?:000|100|300|600|640|900|920)(?:\.\d{1,3})?$",
        "description": (
            "Bounded Dewey division: 000, 100, 300, 600, 640, 900, or 920; "
            "an optional one-to-three digit decimal subdivision is allowed"
        ),
    },
    "classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "source_refs": {
        "type": "array",
        "minItems": 1,
        "maxItems": 12,
        "items": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": list(SOURCE_KINDS)},
                "source_id": {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,127}$"},
                "meaning": {"type": "string", "minLength": 1, "maxLength": 240},
            },
            "required": ["kind", "source_id", "meaning"],
            "additionalProperties": False,
        },
    },
    "observed_at": {"type": ["string", "null"], "format": "date-time"},
    "enabled": {"type": "boolean"},
    "retention_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 36500},
    "person_refs": {"type": "array", "maxItems": 8, "uniqueItems": True, "items": _UUID_SCHEMA},
}


def _tool(
    name: str, properties: dict[str, Any], required: list[str], *, read_only: bool = False
) -> dict[str, Any]:
    return {
        "name": name,
        "description": f"{name.replace('_', ' ')}; notes are not authority",
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "output_schema": {
            "type": "object",
            "required": ["status"],
            "properties": {"status": {"type": "string"}},
            "additionalProperties": True,
        },
        "semantic_action": "capabilities.read" if read_only else "capabilities.configure",
        "risk_class": "READ_ONLY" if read_only else "SECURITY_SECURE_ACTION",
        "read_only": read_only,
        "idempotency": Idempotency.IDEMPOTENT.value if read_only else Idempotency.KEYED.value,
        "external_content_trust": ExternalContentTrust.EXTERNAL_UNTRUSTED.value,
    }


KNOWLEDGE_MANIFEST = PluginManifest(
    plugin_id="anima.knowledge",
    plugin_version="2.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Household knowledge notes",
    description="Bounded evidence-linked notes in the owner-configured private MEMORY/ANIMA root",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.knowledge",),
    source="builtin:anima_ha.knowledge",
    tools=(
        _tool(
            "list_notes",
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "cursor": {"type": ["string", "null"], "format": "uuid"},
                "query": {"type": "string", "maxLength": 120},
                "include_inactive": {"type": "boolean"},
            },
            [],
            read_only=True,
        ),
        _tool("get_note", {"note_id": _UUID_SCHEMA}, ["note_id"], read_only=True),
        _tool(
            "search_notes",
            {
                "query": {"type": "string", "maxLength": 120},
                "person_id": _UUID_SCHEMA,
                "note_type": {"type": "string", "enum": list(NOTE_TYPES)},
                "classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            [],
            read_only=True,
        ),
        _tool(
            "memory_index",
            {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "cursor": {"type": ["string", "null"], "format": "uuid"},
            },
            [],
            read_only=True,
        ),
        _tool("purge_expired", {}, []),
        _tool("create_note", _CONTENT_SCHEMA, sorted(_REQUIRED)),
        _tool(
            "update_note",
            {
                **_CONTENT_SCHEMA,
                "note_id": _UUID_SCHEMA,
                "expected_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            },
            sorted(_REQUIRED | {"note_id", "expected_digest"}),
        ),
        _tool(
            "retract_note",
            {
                "note_id": _UUID_SCHEMA,
                "expected_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            },
            ["note_id", "expected_digest"],
        ),
    ),
)
