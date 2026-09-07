"""Owner routines use real canonical members and immutable governed Memory versions."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest
from test_preferences import context

from anima_ha.db.migrate import migrate
from anima_ha.family_routines import (
    FAMILY_ROUTINES_MANIFEST,
    FamilyRoutineError,
    FamilyRoutinesNativePlugin,
    family_routine_options,
    family_routines_page,
)
from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    PostgresHouseholdGraph,
    RelationshipType,
    validate_commissioning,
)
from anima_ha.memory import MemoryRecord, MemoryService, MemoryStatus, MemoryType, ProvenanceKind
from anima_ha.plugins import PluginValidationError
from anima_ha.policy import RequestOrigin


class Graph:
    def __init__(self) -> None:
        self.household = CanonicalNode(uuid4(), NodeKind.HOUSEHOLD, "Synthetic home")
        self.owner = CanonicalNode(
            uuid4(), NodeKind.PERSON, "Synthetic owner", metadata={"semantic_role": "owner"}
        )
        self.person = CanonicalNode(uuid4(), NodeKind.PERSON, "Synthetic member")
        self.room = CanonicalNode(uuid4(), NodeKind.ROOM, "Synthetic room")
        self.foreign = CanonicalNode(uuid4(), NodeKind.PERSON, "Foreign member")
        self.nodes = {
            item.canonical_id: item
            for item in (self.household, self.owner, self.person, self.room, self.foreign)
        }
        self.added_members: list[CanonicalNode] = []
        self.commissions: list[CommissioningDocument] = []

    def commission(self, document: CommissioningDocument) -> None:
        validate_commissioning(document)
        self.commissions.append(document)
        self.nodes.update({item.canonical_id: item for item in document.nodes})
        self.added_members.extend(
            self.nodes[item.source_id]
            for item in document.relationships
            if item.relationship_type == RelationshipType.MEMBER_OF
            and item.target_id == self.household.canonical_id
        )

    def get_node(self, node_id: UUID) -> CanonicalNode | None:
        return self.nodes.get(node_id)

    def members_of_household(self, household_id: UUID) -> list[CanonicalNode]:
        return (
            [
                self.nodes[self.owner.canonical_id],
                self.nodes[self.person.canonical_id],
                *self.added_members,
            ]
            if household_id == self.household.canonical_id
            else []
        )

    def places_in_household(self, household_id: UUID) -> list[CanonicalNode]:
        return [self.room] if household_id == self.household.canonical_id else []


class Memory:
    def __init__(self) -> None:
        self.records: dict[UUID, MemoryRecord] = {}
        self.parameters: dict[str, Any] = {}

    def create(self, memory: MemoryRecord) -> MemoryRecord:
        self.records[memory.memory_id] = memory
        return memory

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        return self.records.get(memory_id)

    def correct(self, original_id: UUID, replacement: MemoryRecord) -> MemoryRecord:
        original = self.records[original_id]
        assert original.status == MemoryStatus.ACTIVE
        assert original.household_id == replacement.household_id
        replacement = replace(replacement, supersedes_memory_id=original_id)
        self.records[original_id] = replace(
            original, status=MemoryStatus.SUPERSEDED, superseded_by_memory_id=replacement.memory_id
        )
        return self.create(replacement)

    def retract(self, memory_id: UUID) -> MemoryRecord:
        return self.create(replace(self.records[memory_id], status=MemoryStatus.RETRACTED))

    def _rows_for_filters(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "m.household_id = %(household_id)s", kwargs

    @contextmanager
    def _connect(self) -> Iterator[Memory]:
        yield self

    @contextmanager
    def cursor(self) -> Iterator[Memory]:
        yield self

    def execute(self, sql: str, parameters: dict[str, Any]) -> None:
        assert "record_kind' = 'family_routine'" in sql
        assert "ORDER BY m.memory_id ASC" in sql
        self.parameters = parameters

    def fetchall(self) -> list[MemoryRecord]:
        p = self.parameters
        rows = [
            item
            for item in self.records.values()
            if item.household_id == p["household_id"]
            and item.status == MemoryStatus.ACTIVE
            and item.memory_type == MemoryType.EXPLICIT_FACT
            and item.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
            and item.metadata.get("record_kind") == "family_routine"
            and (p["subject_id"] is None or item.subject_id == p["subject_id"])
            and (p["after"] is None or item.memory_id > p["after"])
        ]
        return sorted(rows, key=lambda item: item.memory_id)[: p["limit"]]

    def _memory(self, row: MemoryRecord) -> MemoryRecord:
        return row


def fields(graph: Graph) -> dict[str, Any]:
    return {
        "person_id": str(graph.person.canonical_id),
        "label": "Synthetic expectation",
        "days": [0, 2, 6],
        "start": "22:30",
        "end": "06:30",
        "timezone": "America/New_York",
        "place_id": str(graph.room.canonical_id),
        "notes": "Synthetic test description",
        "enabled": True,
    }


def test_create_reload_edit_disable_retains_history_and_provenance() -> None:
    memory, graph = Memory(), Graph()
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    original = plugin.invoke_with_invocation_context("create_routine", fields(graph), 5, ctx)[
        "routine"
    ]
    assert (
        original["authority"] == "NONE"
        and original["classification"] == "OWNER_DECLARED_EXPECTATION"
    )
    assert original["provenance"] == {
        "kind": "EXPLICIT_INPUT",
        "source_ref": f"anima:principal:{graph.owner.canonical_id}",
    }
    saved = memory.records[UUID(original["routine_id"])]
    assert saved.memory_type == MemoryType.EXPLICIT_FACT
    assert saved.subject_id == graph.person.canonical_id
    assert saved.graph_refs == (graph.person.canonical_id, graph.room.canonical_id)
    assert "not observed presence" in saved.content
    reloaded = family_routines_page(memory, graph, graph.household.canonical_id)
    assert reloaded["items"] == [original]
    changed = FamilyRoutinesNativePlugin(memory, graph).invoke_with_invocation_context(
        "update_routine",
        {**fields(graph), "routine_id": original["routine_id"], "label": "Corrected expectation"},
        5,
        ctx,
    )["routine"]
    assert changed["routine_id"] != original["routine_id"]
    assert changed["supersedes_routine_id"] == original["routine_id"]
    assert memory.records[saved.memory_id].status == MemoryStatus.SUPERSEDED
    with pytest.raises(FamilyRoutineError, match="version changed"):
        plugin.invoke_with_invocation_context(
            "disable_routine", {"routine_id": original["routine_id"]}, 5, ctx
        )
    disabled = plugin.invoke_with_invocation_context(
        "disable_routine", {"routine_id": changed["routine_id"]}, 5, ctx
    )["routine"]
    assert disabled["enabled"] is False and disabled["routine_id"] != changed["routine_id"]
    assert family_routines_page(memory, graph, ctx.household_id)["items"] == [disabled]
    assert (
        plugin.invoke_with_invocation_context(
            "disable_routine", {"routine_id": disabled["routine_id"]}, 5, ctx
        )["routine"]
        == disabled
    )
    assert len(memory.records) == 3


def test_foreign_routine_ids_fail_closed_and_retraction_retains_history() -> None:
    memory, graph = Memory(), Graph()
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    routine = plugin.invoke_with_invocation_context("create_routine", fields(graph), 5, ctx)[
        "routine"
    ]
    routine_id = UUID(routine["routine_id"])
    original = memory.records[routine_id]
    memory.records[routine_id] = replace(original, household_id=uuid4())
    for operation in ("update_routine", "disable_routine", "retract_routine"):
        payload = {"routine_id": str(routine_id)}
        if operation == "update_routine":
            payload.update(fields(graph))
        with pytest.raises(FamilyRoutineError, match="does not exist in this household"):
            plugin.invoke_with_invocation_context(operation, payload, 5, ctx)
    assert family_routines_page(memory, graph, ctx.household_id)["items"] == []
    memory.records[routine_id] = original
    result = plugin.invoke_with_invocation_context(
        "retract_routine", {"routine_id": str(routine_id)}, 5, ctx
    )
    assert result["routine"]["status"] == "RETRACTED"
    assert memory.records[routine_id].content == original.content
    assert family_routines_page(memory, graph, ctx.household_id)["items"] == []
    with pytest.raises(FamilyRoutineError, match="version changed"):
        plugin.invoke_with_invocation_context(
            "retract_routine", {"routine_id": str(routine_id)}, 5, ctx
        )


@pytest.mark.parametrize(
    "key,value",
    [
        ("days", []),
        ("days", [True]),
        ("days", [7]),
        ("days", [0, 0]),
        ("days", "Monday"),
        ("start", "25:00"),
        ("end", "22:30"),
        ("start", "1:00"),
        ("timezone", "Unknown/Zone"),
        ("timezone", "../UTC"),
        ("label", " "),
        ("label", "x" * 121),
        ("notes", "x" * 1001),
        ("enabled", "false"),
        ("person_id", None),
        ("source_ref", "model"),
        ("authority", "owner"),
        ("record_kind", "inferred"),
        ("household_id", str(uuid4())),
    ],
)
def test_invalid_and_model_provenance_fields_fail_before_write(key: str, value: Any) -> None:
    memory, graph = Memory(), Graph()
    with pytest.raises(FamilyRoutineError):
        FamilyRoutinesNativePlugin(memory, graph).invoke_with_invocation_context(
            "create_routine",
            {**fields(graph), key: value},
            5,
            context(graph.household.canonical_id, graph.owner.canonical_id),
        )
    assert not memory.records


@pytest.mark.parametrize(
    "case",
    [
        "foreign-person",
        "missing-person",
        "retired-person",
        "wrong-kind",
        "foreign-place",
        "autonomous",
        "resident",
        "foreign-owner",
    ],
)
def test_member_household_and_owner_isolation(case: str) -> None:
    memory, graph = Memory(), Graph()
    data = fields(graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    if case == "foreign-person":
        data["person_id"] = str(graph.foreign.canonical_id)
    elif case == "missing-person":
        data["person_id"] = str(uuid4())
    elif case == "retired-person":
        graph.nodes[graph.person.canonical_id] = replace(graph.person, retired_at=datetime.now(UTC))
    elif case == "wrong-kind":
        data["person_id"] = str(graph.room.canonical_id)
    elif case == "foreign-place":
        data["place_id"] = str(uuid4())
    elif case == "autonomous":
        ctx = replace(ctx, origin=RequestOrigin.AUTONOMOUS_AGENT)
    elif case == "resident":
        ctx = replace(ctx, principal_id=graph.person.canonical_id)
    else:
        ctx = replace(ctx, principal_id=graph.foreign.canonical_id)
    with pytest.raises(FamilyRoutineError):
        FamilyRoutinesNativePlugin(memory, graph).invoke_with_invocation_context(
            "create_routine", data, 5, ctx
        )
    assert not memory.records


def test_scoped_listing_paginates_past_hundred_without_preference_omissions() -> None:
    memory, graph = Memory(), Graph()
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    for index in range(111):
        plugin.invoke_with_invocation_context(
            "create_routine", {**fields(graph), "label": f"Synthetic {index}"}, 5, ctx
        )
    first = family_routines_page(memory, graph, ctx.household_id, limit=100)
    second = family_routines_page(
        memory, graph, ctx.household_id, limit=100, cursor=first["next_cursor"]
    )
    assert len(first["items"]) == 100 and len(second["items"]) == 11
    assert len({item["routine_id"] for item in first["items"] + second["items"]}) == 111
    assert second["next_cursor"] is None
    with pytest.raises(FamilyRoutineError):
        family_routines_page(
            memory, graph, ctx.household_id, person_id=str(graph.foreign.canonical_id)
        )
    other = replace(ctx, household_id=uuid4())
    with pytest.raises(FamilyRoutineError):
        plugin.invoke_with_invocation_context(
            "disable_routine", {"routine_id": first["items"][0]["routine_id"]}, 5, other
        )


def test_plugin_has_no_context_free_writes_or_forged_fields() -> None:
    graph = Graph()
    with pytest.raises(PluginValidationError, match="trusted invocation context"):
        FamilyRoutinesNativePlugin(Memory(), graph).invoke("create_routine", fields(graph), 5)
    assert FAMILY_ROUTINES_MANIFEST.required_secrets == ()
    assert all(
        tool["input_schema"]["additionalProperties"] is False
        for tool in FAMILY_ROUTINES_MANIFEST.tools
    )


def test_real_postgres_versions_reload_and_pagination() -> None:
    database_url = os.environ.get("ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires isolated ANIMA_FAMILY_ROUTINES_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_family_routines_test",
        )
    migrate(database_url, 5)
    fixture = Graph()
    graph = PostgresHouseholdGraph(database_url)
    graph.commission(
        CommissioningDocument(
            1,
            (fixture.household, fixture.owner, fixture.person, fixture.room),
            (
                CanonicalRelationship(
                    uuid4(),
                    RelationshipType.MEMBER_OF,
                    fixture.owner.canonical_id,
                    fixture.household.canonical_id,
                ),
                CanonicalRelationship(
                    uuid4(),
                    RelationshipType.MEMBER_OF,
                    fixture.person.canonical_id,
                    fixture.household.canonical_id,
                ),
                CanonicalRelationship(
                    uuid4(),
                    RelationshipType.CONTAINS,
                    fixture.household.canonical_id,
                    fixture.room.canonical_id,
                ),
            ),
        )
    )
    memory = MemoryService(database_url)
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(fixture.household.canonical_id, fixture.owner.canonical_id)
    member = plugin.invoke_with_invocation_context(
        "add_member", {"name": "Synthetic added member"}, 5, ctx
    )["member"]
    reloaded_graph = PostgresHouseholdGraph(database_url)
    persisted = reloaded_graph.get_node(UUID(member["person_id"]))
    assert persisted is not None and persisted.kind == NodeKind.PERSON
    assert persisted.metadata == {} and not persisted.security_sensitive
    assert member in family_routine_options(reloaded_graph, ctx.household_id)["members"]
    with pytest.raises(FamilyRoutineError, match="already exists"):
        FamilyRoutinesNativePlugin(memory, reloaded_graph).invoke_with_invocation_context(
            "add_member", {"name": " SYNTHETIC  ADDED MEMBER "}, 5, ctx
        )
    assert len(reloaded_graph.members_of_household(ctx.household_id)) == 3
    original = plugin.invoke_with_invocation_context("create_routine", fields(fixture), 5, ctx)[
        "routine"
    ]
    for index in range(101):
        plugin.invoke_with_invocation_context(
            "create_routine", {**fields(fixture), "label": f"Synthetic paging {index}"}, 5, ctx
        )
    first = family_routines_page(MemoryService(database_url), graph, ctx.household_id, limit=100)
    second = family_routines_page(
        MemoryService(database_url), graph, ctx.household_id, limit=100, cursor=first["next_cursor"]
    )
    assert len(first["items"]) + len(second["items"]) == 102
    edited = plugin.invoke_with_invocation_context(
        "update_routine",
        {
            **fields(fixture),
            "routine_id": original["routine_id"],
            "notes": "Changed synthetic description",
        },
        5,
        ctx,
    )["routine"]
    disabled = plugin.invoke_with_invocation_context(
        "disable_routine", {"routine_id": edited["routine_id"]}, 5, ctx
    )["routine"]
    fresh = MemoryService(database_url)
    old = fresh.get(UUID(original["routine_id"]))
    assert old is not None and old.status == MemoryStatus.SUPERSEDED
    latest = fresh.get(UUID(disabled["routine_id"]))
    assert latest is not None and latest.metadata["enabled"] is False
    with pytest.raises(ValueError):
        plugin.invoke_with_invocation_context(
            "disable_routine", {"routine_id": original["routine_id"]}, 5, ctx
        )
    with fresh._connect() as connection:
        row = connection.execute(
            "SELECT count(*) AS n FROM anima_routine_models WHERE household_id = %s",
            (ctx.household_id,),
        ).fetchone()
        assert row is not None and row["n"] == 0


def test_add_member_commissions_plain_person_and_can_be_selected_for_routine() -> None:
    memory, graph = Memory(), Graph()
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    result = plugin.invoke_with_invocation_context("add_member", {"name": " New member "}, 5, ctx)
    member = result["member"]
    assert result == {
        "status": "SUCCEEDED",
        "member": {
            "person_id": member["person_id"],
            "name": "New member",
        },
    }
    person = graph.get_node(UUID(member["person_id"]))
    assert person is not None and person.kind == NodeKind.PERSON
    assert person.metadata == {} and not person.security_sensitive
    document = graph.commissions[0]
    assert document.nodes[0] == graph.household
    assert len(document.nodes) == 2 and len(document.relationships) == 1
    assert document.relationships[0].relationship_type == RelationshipType.MEMBER_OF
    assert document.relationships[0].metadata == {}
    assert not document.aliases and not document.provider_references
    assert not memory.records
    assert member in family_routine_options(graph, ctx.household_id)["members"]
    routine = plugin.invoke_with_invocation_context(
        "create_routine",
        {**fields(graph), "person_id": member["person_id"]},
        5,
        ctx,
    )["routine"]
    assert routine["person_id"] == member["person_id"] and routine["authority"] == "NONE"


def test_add_member_duplicate_name_is_household_scoped() -> None:
    memory, graph = Memory(), Graph()
    plugin = FamilyRoutinesNativePlugin(memory, graph)
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    with pytest.raises(FamilyRoutineError, match="already exists"):
        plugin.invoke_with_invocation_context(
            "add_member", {"name": " SYNTHETIC   MEMBER "}, 5, ctx
        )
    assert not graph.commissions
    result = plugin.invoke_with_invocation_context(
        "add_member", {"name": graph.foreign.name}, 5, ctx
    )
    assert result["member"]["person_id"] != str(graph.foreign.canonical_id)
    with pytest.raises(FamilyRoutineError, match="already exists"):
        plugin.invoke_with_invocation_context("add_member", {"name": graph.foreign.name}, 5, ctx)
    assert len(graph.commissions) == 1


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"name": None},
        {"name": " "},
        {"name": "x" * 121},
        {"name": "line\nbreak"},
        {"name": "bad\x7f"},
        {"name": "Member", "semantic_role": "owner"},
        {"name": "Member", "household_id": str(uuid4())},
        {"name": "Member", "person_id": str(uuid4())},
        {"name": "Member", "presence": True},
        {"name": "Member", "assurance": "STRONG"},
        {"name": "Member", "login": "owner"},
    ],
)
def test_add_member_rejects_invalid_or_authority_fields_without_writes(
    data: dict[str, Any],
) -> None:
    memory, graph = Memory(), Graph()
    with pytest.raises(FamilyRoutineError):
        FamilyRoutinesNativePlugin(memory, graph).invoke_with_invocation_context(
            "add_member",
            data,
            5,
            context(graph.household.canonical_id, graph.owner.canonical_id),
        )
    assert not graph.commissions and not memory.records


@pytest.mark.parametrize(
    "case",
    [
        "no-principal",
        "foreign",
        "resident",
        "autonomous",
        "retired-owner",
        "wrong-kind",
        "foreign-household",
        "retired-household",
    ],
)
def test_add_member_owner_checks_precede_graph_write(case: str) -> None:
    memory, graph = Memory(), Graph()
    ctx = context(graph.household.canonical_id, graph.owner.canonical_id)
    if case == "no-principal":
        ctx = replace(ctx, principal_id=None)
    elif case == "foreign":
        ctx = replace(ctx, principal_id=graph.foreign.canonical_id)
    elif case == "resident":
        ctx = replace(ctx, principal_id=graph.person.canonical_id)
    elif case == "autonomous":
        ctx = replace(ctx, origin=RequestOrigin.AUTONOMOUS_AGENT)
    elif case == "retired-owner":
        graph.nodes[graph.owner.canonical_id] = replace(graph.owner, retired_at=datetime.now(UTC))
    elif case == "wrong-kind":
        graph.nodes[graph.owner.canonical_id] = replace(graph.owner, kind=NodeKind.RESOURCE)
    elif case == "foreign-household":
        ctx = replace(ctx, household_id=uuid4())
    else:
        graph.nodes[graph.household.canonical_id] = replace(
            graph.household, retired_at=datetime.now(UTC)
        )
    with pytest.raises(FamilyRoutineError):
        FamilyRoutinesNativePlugin(memory, graph).invoke_with_invocation_context(
            "add_member",
            {"name": "New member"},
            5,
            ctx,
        )
    assert not graph.commissions and not memory.records


def test_add_member_manifest_is_bounded_and_requires_trusted_context() -> None:
    tool = next(item for item in FAMILY_ROUTINES_MANIFEST.tools if item["name"] == "add_member")
    assert tool["input_schema"]["properties"] == {
        "name": {"type": "string", "minLength": 1, "maxLength": 120},
    }
    assert tool["input_schema"]["required"] == ["name"]
    assert tool["input_schema"]["additionalProperties"] is False
    assert tool["semantic_action"] == "capabilities.configure" and not tool["read_only"]
    assert tool["risk_class"] == "SECURITY_SECURE_ACTION" and tool["idempotency"] == "KEYED"
    with pytest.raises(PluginValidationError, match="trusted invocation context"):
        FamilyRoutinesNativePlugin(Memory(), Graph()).invoke("add_member", {"name": "Member"}, 5)
