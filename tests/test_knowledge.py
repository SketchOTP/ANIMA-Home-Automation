"""Real temporary native filesystem only; never inspect the owner's vault."""

from __future__ import annotations

import fcntl
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest

from anima_ha import knowledge
from anima_ha.knowledge import (
    KNOWLEDGE_MANIFEST,
    KnowledgeConfig,
    KnowledgeConflict,
    KnowledgeNativePlugin,
    KnowledgeValidationError,
)
from anima_ha.plugins import InvocationContext
from anima_ha.policy import RequestOrigin


@pytest.fixture
def managed(tmp_path: Path) -> Path:
    shared = tmp_path / "MEMORY"
    shared.mkdir(mode=0o2775)
    shared.chmod(0o2775)
    root = shared / "ANIMA"
    root.mkdir(mode=0o700)
    root.chmod(0o700)  # Host provisioning clears inherited setgid on this child only.
    return root


@pytest.fixture
def context() -> InvocationContext:
    return InvocationContext(
        household_id=uuid4(),
        principal_id=uuid4(),
        episode_id=uuid4(),
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key=str(uuid4()),
        origin=RequestOrigin.AUTONOMOUS_AGENT,
    )


@pytest.fixture
def payload() -> dict[str, Any]:
    return {
        "title": "Synthetic contact review",
        "body": "Synthetic note body for testing only.",
        "note_type": "event",
        "classifier": "640",
        "classification": "OBSERVATION",
        "confidence": 0.8,
        "observed_at": "2026-09-06T12:00:00+00:00",
        "source_refs": [
            {
                "kind": "event",
                "source_id": "synthetic-contact-1",
                "meaning": "The referenced event reported contact opening.",
            }
        ],
    }


def fresh(context: InvocationContext) -> InvocationContext:
    return replace(context, tool_request_id=uuid4(), system_idempotency_key=str(uuid4()))


def invoke(
    plugin: KnowledgeNativePlugin, context: InvocationContext, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    result = plugin.invoke_with_invocation_context(name, arguments, 1.0, context)
    assert isinstance(result, dict)
    return result


def create(
    managed: Path, context: InvocationContext, payload: dict[str, Any]
) -> tuple[KnowledgeNativePlugin, dict[str, Any], Path]:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    result = invoke(plugin, context, "create_note", payload)["note"]
    return plugin, result, managed / str(context.household_id) / f"{result['note_id']}.md"


def test_decision_note_type_forms_an_internal_audit_section(
    managed: Path, context: InvocationContext, payload: dict[str, Any]
) -> None:
    plugin, note, _ = create(
        managed,
        context,
        {
            **payload,
            "note_type": "decision",
            "classifier": "100.1",
            "body": "Conclusion-level rationale only; no raw chain-of-thought.",
        },
    )
    result = invoke(plugin, context, "search_notes", {"note_type": "decision", "limit": 20})
    assert [item["note_id"] for item in result["items"]] == [note["note_id"]]


def test_manifest_and_trusted_only_contract(managed: Path) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    plugin.start({})
    plugin.stop()
    assert KNOWLEDGE_MANIFEST.required_secrets == ()
    assert {tool["name"] for tool in plugin.list_tools()} == {
        "list_notes",
        "get_note",
        "create_note",
        "update_note",
        "retract_note",
        "purge_expired",
        "search_notes",
        "memory_index",
    }
    for tool in KNOWLEDGE_MANIFEST.tools:
        assert tool["input_schema"]["additionalProperties"] is False
        assert tool["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    with pytest.raises(KnowledgeValidationError, match="trusted invocation"):
        plugin.invoke("create_note", {}, 1.0)
    assert list(managed.iterdir()) == []


def test_create_receipt_and_read_json_frontmatter(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, note, path = create(managed, context, payload)
    receipt = json.dumps(note)
    for private in (payload["body"], payload["title"], payload["source_refs"][0]["meaning"]):
        assert private not in receipt
    assert note["household_id"] == str(context.household_id)
    assert note["principal_id"] == str(context.principal_id)
    assert note["correlation_id"] == str(context.episode_id)
    assert note["tool_request_id"] == str(context.tool_request_id)
    raw = path.read_text()
    header = json.loads(raw.split("\n---\n")[0][4:])
    assert "body" not in header
    assert raw.endswith(payload["body"])
    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700
    assert managed.parent.stat().st_mode & 0o7777 == 0o2775
    assert not (managed / "ANIMA").exists()
    read = invoke(plugin, context, "get_note", {"note_id": note["note_id"]})
    assert read["note"]["body"] == payload["body"]
    assert read["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    assert "create_request_digest" not in read["note"]


def test_create_idempotence_restart_and_conflicting_reuse(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    _, note, path = create(managed, context, payload)
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    assert invoke(plugin, context, "create_note", payload)["note"] == note
    assert len(list(path.parent.glob("*.md"))) == 1
    with pytest.raises(KnowledgeConflict, match="IDEMPOTENCY"):
        invoke(plugin, context, "create_note", {**payload, "body": "Different draft"})
    with pytest.raises(KnowledgeConflict, match="IDEMPOTENCY"):
        invoke(plugin, replace(context, principal_id=uuid4()), "create_note", payload)


def test_update_conflict_and_retry_do_not_overwrite(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, original, path = create(managed, context, payload)
    updated_context = fresh(context)
    arguments = {
        **payload,
        "body": "Corrected synthetic body",
        "note_id": original["note_id"],
        "expected_digest": original["digest"],
        "enabled": False,
    }
    updated = invoke(plugin, updated_context, "update_note", arguments)["note"]
    assert updated["digest"] != original["digest"]
    assert updated["note_id"] == original["note_id"]
    assert updated["previous_digest"] == original["digest"]
    assert not updated["enabled"]
    assert payload["body"] not in path.read_text()
    assert invoke(plugin, updated_context, "update_note", arguments)["note"] == updated
    before = path.read_bytes()
    with pytest.raises(KnowledgeConflict, match="DIGEST_CONFLICT"):
        invoke(plugin, fresh(context), "update_note", arguments)
    assert path.read_bytes() == before
    with pytest.raises(KnowledgeConflict, match="IDEMPOTENCY"):
        invoke(plugin, updated_context, "update_note", {**arguments, "body": "Other text"})


def test_retract_erases_body_title_sources_without_resurrection(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, original, path = create(managed, context, payload)
    request = fresh(context)
    arguments = {"note_id": original["note_id"], "expected_digest": original["digest"]}
    result = invoke(plugin, request, "retract_note", arguments)
    assert result["note"]["status"] == "RETRACTED"
    assert result["note"]["previous_digest"] == original["digest"]
    assert invoke(plugin, request, "retract_note", arguments) == result
    for file in path.parent.iterdir():
        raw = file.read_text()
        for erased in (payload["body"], payload["title"], payload["source_refs"][0]["meaning"]):
            assert erased not in raw
    read = invoke(plugin, context, "get_note", {"note_id": original["note_id"]})
    assert "body" not in read["note"]
    assert invoke(plugin, context, "list_notes", {})["items"] == []
    assert len(invoke(plugin, context, "list_notes", {"include_inactive": True})["items"]) == 1
    assert invoke(plugin, context, "create_note", payload)["note"]["status"] == "RETRACTED"
    with pytest.raises(KnowledgeConflict, match="INACTIVE"):
        invoke(
            plugin,
            fresh(context),
            "update_note",
            {
                **payload,
                "note_id": original["note_id"],
                "expected_digest": result["note"]["digest"],
            },
        )


@pytest.mark.parametrize("operation", ["get_note", "list_notes", "purge_expired"])
def test_expiry_hides_prose_on_reads_and_erases_only_on_explicit_purge(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    operation: str,
) -> None:
    now = datetime(2026, 9, 6, 13, tzinfo=UTC)
    clock = [now]
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed), clock=lambda: clock[0])
    note = invoke(plugin, context, "create_note", {**payload, "retention_days": 1})["note"]
    clock[0] = now + timedelta(days=1)
    arguments = {"note_id": note["note_id"]} if operation == "get_note" else {}
    result = invoke(plugin, fresh(context), operation, arguments)
    assert payload["body"] not in json.dumps(result)
    path = managed / str(context.household_id) / f"{note['note_id']}.md"
    if operation == "purge_expired":
        assert payload["body"] not in path.read_text()
        assert "EXPIRED" in path.read_text()
    else:
        assert payload["body"] in path.read_text()
        invoke(plugin, fresh(context), "purge_expired", {})
        assert payload["body"] not in path.read_text()
    assert (
        invoke(plugin, context, "create_note", {**payload, "retention_days": 1})["note"]["status"]
        == "EXPIRED"
    )


@pytest.mark.parametrize(
    "classification,days,expected",
    [
        ("OBSERVATION", None, None),
        ("OBSERVATION", 365, 365),
        ("SENTRY_INFERENCE", None, None),
        ("SENTRY_INFERENCE", 365, 365),
        ("SENTRY_INFERENCE", 1, 1),
    ],
)
def test_retention_supports_durable_notes_without_inference_ceiling(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    classification: str,
    days: int | None,
    expected: int | None,
) -> None:
    now = datetime(2026, 9, 6, 13, tzinfo=UTC)
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed), clock=lambda: now)
    arguments = {**payload, "classification": classification}
    if days is not None:
        arguments["retention_days"] = days
    note = invoke(plugin, context, "create_note", arguments)["note"]
    if expected is None:
        assert note["expires_at"] is None
    else:
        assert datetime.fromisoformat(note["expires_at"]) == now + timedelta(days=expected)
    assert note["inferred"] is (classification == "SENTRY_INFERENCE")


def test_paginated_search_does_not_truncate_first_fifty(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    ids = []
    for index in range(113):
        note = invoke(
            plugin,
            fresh(context),
            "create_note",
            {
                **payload,
                "body": f"Synthetic searchable marker {index:03d}",
            },
        )["note"]
        ids.append(note["note_id"])
    found: list[str] = []
    cursor = None
    pages = []
    while True:
        result = invoke(plugin, context, "list_notes", {"cursor": cursor, "limit": 50})
        pages.append(len(result["items"]))
        found.extend(item["note_id"] for item in result["items"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert pages == [50, 50, 13]
    assert found == sorted(ids)
    # Search a late UUID, not merely whichever record happens to be in the first page.
    last = invoke(plugin, context, "get_note", {"note_id": found[-1]})["note"]
    matches = invoke(plugin, context, "list_notes", {"query": last["body"]})
    assert [item["note_id"] for item in matches["items"]] == [found[-1]]
    assert matches["next_cursor"] is None


def test_household_isolation_and_no_other_vault_reads(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    (managed.parent / ".obsidian").mkdir()
    (managed.parent / "owner-private.md").write_text("Private synthetic sibling must remain alone")
    plugin, note, _ = create(managed, context, payload)
    other = replace(fresh(context), household_id=uuid4())
    assert invoke(plugin, other, "list_notes", {})["items"] == []
    for operation, arguments in [
        ("get_note", {"note_id": note["note_id"]}),
        ("retract_note", {"note_id": note["note_id"], "expected_digest": note["digest"]}),
        ("update_note", {**payload, "note_id": note["note_id"], "expected_digest": note["digest"]}),
    ]:
        with pytest.raises(KnowledgeValidationError, match="NOT_FOUND"):
            invoke(plugin, other, operation, arguments)
    assert (managed.parent / "owner-private.md").read_text().startswith("Private synthetic")


@pytest.mark.parametrize(
    "key,value",
    [
        ("household_id", str(uuid4())),
        ("principal_id", str(uuid4())),
        ("authority", "OWNER"),
        ("path", "../../outside"),
        ("classification", "EXPLICIT_INPUT"),
        ("body", "x" * 4097),
        ("body", "é" * 2049),
        ("title", "x" * 121),
        ("body", ""),
        ("body", "bad\x00text"),
        ("confidence", float("nan")),
        ("confidence", True),
        ("confidence", 1.1),
        ("retention_days", 0),
        ("retention_days", 36501),
        ("retention_days", True),
        ("enabled", "true"),
        ("source_refs", []),
        ("source_refs", [{"kind": "event", "source_id": "id"}]),
        ("observed_at", None),
        ("observed_at", "2026-09-06T12:00:00"),
        ("classifier", "040"),
        ("classifier", "999"),
        ("classifier", "640.1234"),
        ("note_type", "permission"),
    ],
)
def test_invalid_fields_fail_before_filesystem_creation(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    key: str,
    value: Any,
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    with pytest.raises(KnowledgeValidationError):
        invoke(plugin, context, "create_note", {**payload, key: value})
    assert list(managed.iterdir()) == []


def test_manifest_classifier_schema_matches_runtime_allowlist() -> None:
    create = next(tool for tool in KNOWLEDGE_MANIFEST.tools if tool["name"] == "create_note")
    assert create["input_schema"]["properties"]["classifier"]["pattern"] == (
        r"^(?:000|100|300|600|640|900|920)(?:\.\d{1,3})?$"
    )


@pytest.mark.parametrize(
    "bad", ["../../outside", "/tmp/outside", "not-a-uuid", "{00000000-0000-0000-0000-000000000001}"]
)
def test_no_model_paths(managed: Path, context: InvocationContext, bad: str) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    with pytest.raises(KnowledgeValidationError, match="INVALID_ID"):
        invoke(plugin, context, "get_note", {"note_id": bad})
    assert list(managed.iterdir()) == []


@pytest.mark.parametrize(
    "arguments",
    [{"limit": 0}, {"limit": 51}, {"limit": True}, {"cursor": "../x"}, {"query": "x" * 121}],
)
def test_invalid_page(managed: Path, context: InvocationContext, arguments: dict[str, Any]) -> None:
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "list_notes", arguments)


@pytest.mark.parametrize(
    "root", ["/", "/tmp", "/home", "/srv/ATLAS/500_MEMORY/MEMORY", "/home/sketch/Documents/MEMORY"]
)
def test_global_root_rejected(root: str, context: InvocationContext) -> None:
    with pytest.raises(KnowledgeValidationError, match="INVALID_VAULT_ROOT"):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(Path(root))), context, "list_notes", {})


def test_missing_root_not_created(tmp_path: Path, context: InvocationContext) -> None:
    root = tmp_path / "missing"
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(root)), context, "list_notes", {})
    assert not root.exists()


@pytest.mark.parametrize("mode", [0o775, 0o755, 0o777])
def test_managed_root_must_be_private(managed: Path, context: InvocationContext, mode: int) -> None:
    managed.chmod(mode)
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "list_notes", {})
    assert managed.stat().st_mode & 0o777 == mode  # Never chmod owner storage.


@pytest.mark.parametrize("level", ["root", "ancestor", "household"])
def test_symlink_directories_rejected(
    managed: Path,
    tmp_path: Path,
    context: InvocationContext,
    level: str,
) -> None:
    if level == "root":
        root = tmp_path / "alias"
        root.symlink_to(managed, target_is_directory=True)
    elif level == "ancestor":
        alias = tmp_path / "alias"
        alias.symlink_to(managed.parent, target_is_directory=True)
        root = alias / "ANIMA"
    else:
        root = managed
        (managed / str(context.household_id)).symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(root)), context, "list_notes", {})


@pytest.mark.parametrize(
    "unsafe", ["symlink", "hardlink", "public", "fifo", "directory", "locklink"]
)
def test_unsafe_note_or_lock_fails_closed(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    unsafe: str,
) -> None:
    plugin, note, path = create(managed, context, payload)
    if unsafe == "public":
        path.chmod(0o644)
    elif unsafe == "hardlink":
        os.link(path, managed.parent / "linked.md")
    elif unsafe == "locklink":
        lock = path.parent / ".lock"
        lock.unlink()
        lock.symlink_to(path)
    else:
        path.unlink()
        if unsafe == "symlink":
            path.symlink_to(managed.parent / "private.md")
        elif unsafe == "fifo":
            os.mkfifo(path)
        else:
            path.mkdir()
    with pytest.raises(KnowledgeValidationError):
        invoke(plugin, context, "get_note", {"note_id": note["note_id"]})


def test_corrupt_or_external_edit_is_not_overwritten(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, note, path = create(managed, context, payload)
    path.write_text(path.read_text() + " External modification")
    before = path.read_bytes()
    with pytest.raises(KnowledgeConflict, match="UNRECONCILED"):
        invoke(
            plugin,
            fresh(context),
            "update_note",
            {
                **payload,
                "note_id": note["note_id"],
                "expected_digest": note["digest"],
            },
        )
    assert path.read_bytes() == before


def test_busy_lock_is_bounded_and_no_duplicate_create(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, _, path = create(managed, context, payload)
    with (path.parent / ".lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(KnowledgeConflict, match="BUSY"):
            invoke(plugin, fresh(context), "create_note", payload)
    assert len(list(path.parent.glob("*.md"))) == 1


def test_failed_replace_preserves_original_and_no_pending_body(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin, note, path = create(managed, context, payload)
    before = path.read_bytes()

    def fail(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(KnowledgeValidationError, match="FILESYSTEM_UNAVAILABLE"):
        invoke(
            plugin,
            fresh(context),
            "update_note",
            {
                **payload,
                "body": "New draft which must not remain",
                "note_id": note["note_id"],
                "expected_digest": note["digest"],
            },
        )
    assert path.read_bytes() == before
    assert not list(path.parent.glob(".pending-*"))


def test_crash_pending_file_cleaned_before_retraction(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, note, path = create(managed, context, payload)
    pending = path.parent / f".pending-{uuid4()}"
    pending.write_text(payload["body"])
    pending.chmod(0o600)
    invoke(
        plugin,
        fresh(context),
        "retract_note",
        {
            "note_id": note["note_id"],
            "expected_digest": note["digest"],
        },
    )
    assert not pending.exists()
    assert all(payload["body"] not in file.read_text() for file in path.parent.iterdir())


def test_namespace_limit_no_silent_truncation(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(knowledge, "MAX_NOTES", 2)
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    for _ in range(2):
        invoke(plugin, fresh(context), "create_note", payload)
    assert len(invoke(plugin, context, "list_notes", {})["items"]) == 2
    with pytest.raises(KnowledgeValidationError, match="NAMESPACE_LIMIT"):
        invoke(plugin, fresh(context), "create_note", payload)


def test_remote_mount_rejected(
    managed: Path, context: InvocationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_text

    def mounted(path: Path, *args: Any, **kwargs: Any) -> str:
        if str(path) == "/proc/self/mountinfo":
            return f"1 0 0:1 / / rw - ext4 source rw\n2 1 0:2 / {managed} rw - fuse.sshfs x rw\n"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", mounted)
    with pytest.raises(KnowledgeValidationError, match="NATIVE_FILESYSTEM_REQUIRED"):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "list_notes", {})


def test_concurrent_idempotent_create_has_one_file(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    barrier = Barrier(2)

    def race() -> dict[str, Any]:
        barrier.wait(timeout=5)
        try:
            return invoke(plugin, context, "create_note", payload)
        except KnowledgeConflict as error:
            assert str(error) == "KNOWLEDGE_BUSY"
            return {"status": "BUSY"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: race(), range(2)))
    successes = [result for result in results if result["status"] == "SUCCEEDED"]
    assert successes
    replay = invoke(plugin, context, "create_note", payload)
    assert all(result == replay for result in successes)
    assert len(list((managed / str(context.household_id)).glob("*.md"))) == 1


def test_concurrent_expected_digest_updates_have_one_winner(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, note, path = create(managed, context, payload)
    barrier = Barrier(2)

    def race(index: int) -> dict[str, Any]:
        arguments = {
            **payload,
            "body": f"Concurrent synthetic version {index}",
            "note_id": note["note_id"],
            "expected_digest": note["digest"],
        }
        barrier.wait(timeout=5)
        try:
            return invoke(plugin, fresh(context), "update_note", arguments)
        except KnowledgeConflict as error:
            assert str(error) in ("KNOWLEDGE_BUSY", "KNOWLEDGE_DIGEST_CONFLICT")
            return {"status": "CONFLICT"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(race, range(2)))
    assert [result["status"] for result in results].count("SUCCEEDED") == 1
    before = path.read_bytes()
    with pytest.raises(KnowledgeConflict, match="DIGEST_CONFLICT"):
        invoke(
            plugin,
            fresh(context),
            "update_note",
            {
                **payload,
                "note_id": note["note_id"],
                "expected_digest": note["digest"],
            },
        )
    assert path.read_bytes() == before


def test_error_after_atomic_rename_can_replay_without_duplicate(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    invoke(plugin, context, "list_notes", {})
    original_replace = os.replace
    original_sync = os.fsync
    renamed = [False]

    def replace_then_flag(*args: Any, **kwargs: Any) -> None:
        original_replace(*args, **kwargs)
        renamed[0] = True

    def fail_after_replace(fd: int) -> None:
        if renamed[0]:
            renamed[0] = False
            raise OSError("synthetic directory sync failure after rename")
        original_sync(fd)

    monkeypatch.setattr(os, "replace", replace_then_flag)
    monkeypatch.setattr(os, "fsync", fail_after_replace)
    with pytest.raises(KnowledgeValidationError, match="FILESYSTEM_UNAVAILABLE"):
        invoke(plugin, context, "create_note", payload)
    replay = invoke(plugin, context, "create_note", payload)
    assert replay["status"] == "SUCCEEDED"
    assert len(list((managed / str(context.household_id)).glob("*.md"))) == 1
    assert not list((managed / str(context.household_id)).glob(".pending-*"))


def test_wrong_filesystem_owner_rejected(
    managed: Path,
    context: InvocationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actual_uid = os.geteuid()
    monkeypatch.setattr(os, "geteuid", lambda: actual_uid + 1)
    with pytest.raises(KnowledgeValidationError, match="UNSAFE_PERMISSIONS"):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "list_notes", {})


def test_known_classifier_decimal_and_lesson_stay_inference(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, note, _ = create(
        managed,
        context,
        {
            **payload,
            "note_type": "lesson",
            "classifier": "640.12",
            "classification": "SENTRY_INFERENCE",
            "observed_at": None,
        },
    )
    read = invoke(plugin, context, "get_note", {"note_id": note["note_id"]})["note"]
    assert read["classification"] == "SENTRY_INFERENCE"
    assert read["inferred"] is True
    assert "authority" not in read


def test_purge_is_repeatable_metadata_only_and_retains_digest_tombstone(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    clock = [datetime(2026, 9, 6, 13, tzinfo=UTC)]
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed), clock=lambda: clock[0])
    note = invoke(plugin, context, "create_note", {**payload, "retention_days": 90})["note"]
    clock[0] += timedelta(days=91)
    first = invoke(plugin, fresh(context), "purge_expired", {})
    assert first == {"status": "SUCCEEDED", "scanned": 1, "expired_tombstones": 1}
    assert invoke(plugin, fresh(context), "purge_expired", {}) == first
    path = managed / str(context.household_id) / f"{note['note_id']}.md"
    assert path.exists()  # Tombstone remains; this is not deletion of all evidence.
    assert note["digest"] in path.read_text()
    assert payload["body"] not in path.read_text()


def test_shared_owner_mode_preserves_2775_parent_and_group_access(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    managed.chmod(0o2770)  # Explicit host fixture provisioning only.
    config = KnowledgeConfig(managed, os.geteuid(), os.getegid())
    plugin = KnowledgeNativePlugin(config)
    note = invoke(plugin, context, "create_note", payload)["note"]
    directory = managed / str(context.household_id)
    assert managed.parent.stat().st_mode & 0o7777 == 0o2775
    assert directory.stat().st_mode & 0o7777 == 0o2770
    assert all(file.stat().st_mode & 0o7777 == 0o660 for file in directory.iterdir())
    assert all(file.stat().st_gid == config.shared_group_id for file in directory.iterdir())
    read = invoke(plugin, context, "get_note", {"note_id": note["note_id"]})
    assert read["note"]["body"] == payload["body"]


@pytest.mark.parametrize(
    "owner,group", [(1000, None), (None, 1000), (-1, 1000), (1000, -1), (True, 1000)]
)
def test_shared_mode_requires_complete_explicit_valid_config(
    managed: Path,
    owner: Any,
    group: Any,
) -> None:
    with pytest.raises(KnowledgeValidationError):
        KnowledgeConfig(managed, owner, group)


def test_environment_shared_config_is_explicit(managed: Path) -> None:
    base = {"ANIMA_KNOWLEDGE_ROOT": str(managed)}
    assert KnowledgeConfig.from_environment(base).shared_group_id is None
    shared = {**base, "ANIMA_KNOWLEDGE_OWNER_UID": "1000", "ANIMA_KNOWLEDGE_GROUP_ID": "1000"}
    assert KnowledgeConfig.from_environment(shared) == KnowledgeConfig(managed, 1000, 1000)
    for bad in (
        {},
        {**base, "ANIMA_KNOWLEDGE_OWNER_UID": "1000"},
        {**shared, "ANIMA_KNOWLEDGE_GROUP_ID": "not-a-group"},
    ):
        with pytest.raises(KnowledgeValidationError):
            KnowledgeConfig.from_environment(bad)


@pytest.mark.parametrize("mode", [0o2775, 0o2777, 0o770])
def test_shared_mode_rejects_world_access_and_missing_setgid(
    managed: Path,
    context: InvocationContext,
    mode: int,
) -> None:
    managed.chmod(mode)
    config = KnowledgeConfig(managed, os.geteuid(), os.getegid())
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(config), context, "list_notes", {})
    assert managed.stat().st_mode & 0o7777 == mode


def test_unconfigured_shared_group_rejected(
    managed: Path,
    context: InvocationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed.chmod(0o2770)
    actual = os.getegid()
    config = KnowledgeConfig(managed, os.geteuid(), actual + 100000)
    monkeypatch.setattr(os, "getgroups", lambda: [actual + 100000])
    with pytest.raises(KnowledgeValidationError, match="UNSAFE_PERMISSIONS"):
        invoke(KnowledgeNativePlugin(config), context, "list_notes", {})


def test_configured_owner_replacement_inode_accepted_but_external_edit_unreconciled(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed.chmod(0o2770)
    owner = os.geteuid()
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed, owner, os.getegid()))
    note = invoke(plugin, context, "create_note", payload)["note"]
    path = managed / str(context.household_id) / f"{note['note_id']}.md"
    previous_inode = path.stat().st_ino
    replacement = path.parent / "replacement"
    replacement.write_bytes(path.read_bytes())
    replacement.chmod(0o660)
    replacement.replace(path)
    assert path.stat().st_ino != previous_inode
    # Validator sees a different Core UID; the real replacement belongs to the
    # configured owner. This tests ownership classification, not setuid execution.
    monkeypatch.setattr(os, "geteuid", lambda: owner + 10001)
    assert (
        invoke(plugin, context, "get_note", {"note_id": note["note_id"]})["note"]["body"]
        == payload["body"]
    )
    path.write_text(path.read_text() + " Owner edited this in Obsidian")
    preserved = path.read_bytes()
    with pytest.raises(KnowledgeConflict, match="UNRECONCILED"):
        invoke(plugin, context, "get_note", {"note_id": note["note_id"]})
    assert path.read_bytes() == preserved


def test_unconfigured_inode_owner_rejected_in_shared_mode(
    managed: Path,
    context: InvocationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed.chmod(0o2770)
    actual_owner = os.geteuid()
    config = KnowledgeConfig(managed, actual_owner + 20002, os.getegid())
    monkeypatch.setattr(os, "geteuid", lambda: actual_owner + 10001)
    with pytest.raises(KnowledgeValidationError, match="UNSAFE_PERMISSIONS"):
        invoke(KnowledgeNativePlugin(config), context, "list_notes", {})


@pytest.mark.parametrize(
    "operation,args",
    [
        ("list_notes", {}),
        ("memory_index", {}),
        ("search_notes", {"query": "synthetic"}),
    ],
)
def test_read_tools_do_not_create_namespace(
    managed: Path, context: InvocationContext, operation: str, args: dict[str, Any]
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    assert invoke(plugin, context, operation, args)["items"] == []
    assert list(managed.iterdir()) == []
    assert next(t for t in KNOWLEDGE_MANIFEST.tools if t["name"] == operation)["read_only"]


def test_read_does_not_cleanup_pending_or_persist_expiry(
    managed: Path, context: InvocationContext, payload: dict[str, Any]
) -> None:
    clock = [datetime(2026, 9, 6, 13, tzinfo=UTC)]
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed), clock=lambda: clock[0])
    note = invoke(plugin, context, "create_note", {**payload, "retention_days": 1})["note"]
    namespace = managed / str(context.household_id)
    pending = namespace / f".pending-{uuid4()}"
    pending.write_text("Synthetic pending prose")
    pending.chmod(0o600)
    before = {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_ino) for p in namespace.iterdir()
    }
    clock[0] += timedelta(days=2)
    for operation, args in [
        ("list_notes", {}),
        ("search_notes", {"query": "synthetic"}),
        ("memory_index", {}),
        ("get_note", {"note_id": note["note_id"]}),
    ]:
        result = invoke(plugin, context, operation, args)
        assert payload["body"] not in json.dumps(result)
    after = {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_ino) for p in namespace.iterdir()
    }
    assert after == before
    invoke(plugin, fresh(context), "purge_expired", {})
    assert not pending.exists()
    assert payload["body"] not in (namespace / f"{note['note_id']}.md").read_text()


def test_null_retention_survives_years_and_correction_preserves_explicit_expiry(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    clock = [datetime(2026, 1, 1, tzinfo=UTC)]
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed), clock=lambda: clock[0])
    durable = invoke(plugin, context, "create_note", {**payload, "retention_days": None})["note"]
    finite = invoke(plugin, fresh(context), "create_note", {**payload, "retention_days": 3650})[
        "note"
    ]
    clock[0] += timedelta(days=365)
    assert (
        invoke(plugin, context, "get_note", {"note_id": durable["note_id"]})["note"]["status"]
        == "ACTIVE"
    )
    updated = invoke(
        plugin,
        fresh(context),
        "update_note",
        {
            **payload,
            "note_id": finite["note_id"],
            "expected_digest": finite["digest"],
            "body": "Corrected claim",
        },
    )["note"]
    assert updated["expires_at"] == finite["expires_at"]


def test_legacy_note_read_does_not_migrate_or_extend_retention(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, receipt, path = create(managed, context, {**payload, "retention_days": 90})
    note = invoke(plugin, context, "get_note", {"note_id": receipt["note_id"]})["note"]
    # Restore legacy layout (no person_refs) with its original private metadata.
    raw = path.read_text()
    header = json.loads(raw.split("\n---\n")[0][4:])
    header.pop("person_refs")
    header["body"] = note["body"]
    KnowledgeNativePlugin._seal(header)
    body = header.pop("body")
    path.write_text("---\n" + knowledge._json(header) + "\n---\n" + body)
    before = path.read_bytes()
    read = invoke(plugin, context, "get_note", {"note_id": receipt["note_id"]})["note"]
    assert read["expires_at"] == receipt["expires_at"]
    assert "person_refs" not in read
    assert path.read_bytes() == before


def test_person_reference_requires_household_graph_validation(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    person = uuid4()
    args = {**payload, "person_refs": [str(person)], "note_type": "profile"}
    with pytest.raises(KnowledgeValidationError, match="PERSON_NOT_IN_HOUSEHOLD"):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "create_note", args)
    assert list(managed.iterdir()) == []
    plugin = KnowledgeNativePlugin(
        KnowledgeConfig(managed),
        person_validator=lambda household, member: (
            household == context.household_id and member == person
        ),
    )
    note = invoke(plugin, context, "create_note", args)["note"]
    result = invoke(
        plugin, context, "search_notes", {"person_id": str(person), "note_type": "profile"}
    )
    assert result["items"][0]["note_id"] == note["note_id"]
    assert result["items"][0]["person_refs_status"] == "NOT_REVALIDATED"
    with pytest.raises(KnowledgeValidationError, match="PERSON_NOT_IN_HOUSEHOLD"):
        invoke(
            plugin,
            replace(context, household_id=uuid4()),
            "search_notes",
            {"person_id": str(person)},
        )
    updated = invoke(
        plugin,
        fresh(context),
        "update_note",
        {
            **payload,
            "note_type": "profile",
            "note_id": note["note_id"],
            "expected_digest": note["digest"],
        },
    )["note"]
    assert invoke(plugin, context, "get_note", {"note_id": updated["note_id"]})["note"][
        "person_refs"
    ] == [str(person)]


@pytest.mark.parametrize("classification", ["USER_STATED", "DISCOVERED", "SENTRY_INFERENCE"])
def test_epistemic_claims_and_test_refs_never_mint_verified_truth(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
    classification: str,
) -> None:
    refs = [
        {
            "kind": "request",
            "source_id": "request-synthetic",
            "meaning": "Attributed user statement",
        },
        {"kind": "tool_result", "source_id": "tool-synthetic", "meaning": "Attributed tool result"},
        {
            "kind": "test",
            "source_id": "run-synthetic",
            "meaning": "Attributed tested outcome, not resolved here",
        },
    ]
    plugin, note, _ = create(
        managed,
        context,
        {
            **payload,
            "classification": classification,
            "note_type": "lesson",
            "source_refs": refs,
        },
    )
    read = invoke(plugin, context, "get_note", {"note_id": note["note_id"]})
    assert read["note"]["classification"] == classification
    assert read["evidence_status"] == "ATTRIBUTED_UNVERIFIED" and read["authority"] == "NONE"
    assert read["external_content_trust"] == "EXTERNAL_UNTRUSTED"
    result = invoke(
        plugin,
        context,
        "search_notes",
        {"query": "tool synthetic", "classification": classification},
    )
    assert result["items"][0]["source_refs"] == refs
    assert result["evidence_status"] == "ATTRIBUTED_UNVERIFIED"


def test_user_stated_without_request_reference_rejected(
    managed: Path, context: InvocationContext, payload: dict[str, Any]
) -> None:
    with pytest.raises(KnowledgeValidationError, match="STATEMENT_SOURCE"):
        create(managed, context, {**payload, "classification": "USER_STATED"})
    assert list(managed.iterdir()) == []


def test_ranked_search_and_index_rebuild_after_correction_and_retraction(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin, first, _ = create(
        managed, context, {**payload, "title": "Synthetic garden hose", "body": "Water twice"}
    )
    second = invoke(
        plugin, fresh(context), "create_note", {**payload, "body": "Synthetic garden hose repair"}
    )["note"]
    result = invoke(plugin, context, "search_notes", {"query": "hose garden", "limit": 1})
    assert result["items"][0]["note_id"] == first["note_id"] and result["truncated"]
    invoke(
        plugin,
        fresh(context),
        "update_note",
        {
            **payload,
            "body": "Corrected unrelated claim",
            "note_id": first["note_id"],
            "expected_digest": first["digest"],
        },
    )
    assert (
        invoke(plugin, context, "search_notes", {"query": "hose garden"})["items"][0]["note_id"]
        == second["note_id"]
    )
    invoke(
        plugin,
        fresh(context),
        "retract_note",
        {"note_id": second["note_id"], "expected_digest": second["digest"]},
    )
    restarted = KnowledgeNativePlugin(KnowledgeConfig(managed))
    assert invoke(restarted, context, "search_notes", {"query": "hose garden"})["items"] == []
    assert invoke(restarted, context, "memory_index", {})["counts_by_type"] == {"event": 1}


def test_retrieval_budget_pagination_and_disabled_notes(
    managed: Path,
    context: InvocationContext,
    payload: dict[str, Any],
) -> None:
    plugin = KnowledgeNativePlugin(KnowledgeConfig(managed))
    for index in range(24):
        invoke(
            plugin,
            fresh(context),
            "create_note",
            {
                **payload,
                "body": "界" * 1300,
                "title": f"Synthetic note {index}",
                "enabled": index != 0,
            },
        )
    search = invoke(plugin, context, "search_notes", {"note_type": "event", "limit": 20})
    assert search["matched"] == 23 and search["truncated"]
    assert len(knowledge._json(search).encode()) <= knowledge.MAX_RETRIEVAL_BYTES
    assert all(len(item["excerpt"]) <= 320 for item in search["items"])
    ids: list[str] = []
    cursor = None
    while True:
        result = invoke(plugin, context, "memory_index", {"limit": 7, "cursor": cursor})
        ids.extend(item["note_id"] for item in result["items"])
        assert all("body" not in item and "source_refs" not in item for item in result["items"])
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert len(ids) == len(set(ids)) == 23


@pytest.mark.parametrize(
    "args",
    [
        {},
        {"query": "!!!"},
        {"query": "x", "limit": 21},
        {"query": "x " * 13},
        {"query": "x", "path": "/outside"},
        {"person_id": "bad"},
        {"note_type": "permission"},
        {"classification": "USER_STATED"},
    ],
)
def test_invalid_search_fails_before_namespace_creation(
    managed: Path, context: InvocationContext, args: dict[str, Any]
) -> None:
    with pytest.raises(KnowledgeValidationError):
        invoke(KnowledgeNativePlugin(KnowledgeConfig(managed)), context, "search_notes", args)
    assert list(managed.iterdir()) == []
