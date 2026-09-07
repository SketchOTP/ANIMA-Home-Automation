from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from anima_ha.graph import CanonicalNode, NodeKind
from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemorySearchResult,
    MemoryStatus,
    MemoryType,
    ProvenanceKind,
    RetrievalMode,
)
from anima_ha.plugins import InvocationContext, PluginValidationError
from anima_ha.policy import RequestOrigin
from anima_ha.preferences import (
    PREFERENCES_MANIFEST,
    PreferencesNativePlugin,
    PreferenceValidationError,
    preference_payload,
    preference_payloads,
    preferences_page,
)


class FakeMemoryService:
    def __init__(self) -> None:
        self.records: dict[UUID, MemoryRecord] = {}
        self.parameters: dict[str, Any] = {}

    def create(self, memory: MemoryRecord) -> MemoryRecord:
        self.records[memory.memory_id] = memory
        return memory

    def get(self, memory_id: UUID) -> MemoryRecord | None:
        return self.records.get(memory_id)

    def retrieve(self, query: str, **_: object) -> list[MemorySearchResult]:
        del query
        return [
            MemorySearchResult(memory, 0.0, 490, RetrievalMode.LEXICAL_FALLBACK)
            for memory in self.records.values()
            if memory.status == MemoryStatus.ACTIVE
        ]

    def correct(self, original_id: UUID, replacement: MemoryRecord) -> MemoryRecord:
        original = self.records[original_id]
        assert original.status == MemoryStatus.ACTIVE
        self.records[original_id] = replace(
            original, status=MemoryStatus.SUPERSEDED, superseded_by_memory_id=replacement.memory_id
        )
        self.records[replacement.memory_id] = replacement
        return replacement

    def retract(self, memory_id: UUID) -> MemoryRecord:
        original = self.records[memory_id]
        assert original.status == MemoryStatus.ACTIVE
        retracted = MemoryRecord(
            memory_id=original.memory_id,
            household_id=original.household_id,
            memory_type=original.memory_type,
            content=original.content,
            retrieval_text=original.retrieval_text,
            provenance=original.provenance,
            created_at=original.created_at,
            subject_id=original.subject_id,
            valid_from=original.valid_from,
            valid_until=original.valid_until,
            confidence=original.confidence,
            expires_at=original.expires_at,
            status=MemoryStatus.RETRACTED,
            metadata=original.metadata,
        )
        self.records[memory_id] = retracted
        return retracted

    def _rows_for_filters(self, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        return "m.household_id = %(household_id)s", kwargs

    @contextmanager
    def _connect(self) -> Iterator[FakeMemoryService]:
        yield self

    @contextmanager
    def cursor(self) -> Iterator[FakeMemoryService]:
        yield self

    def execute(self, sql: str, parameters: dict[str, Any]) -> None:
        assert "ORDER BY m.memory_id ASC LIMIT" in sql
        assert "provenance_kind = 'EXPLICIT_INPUT'" in sql
        assert "metadata->>'scope'" in sql and "metadata->>'category'" in sql
        self.parameters = parameters

    def fetchall(self) -> list[MemoryRecord]:
        p = self.parameters
        return sorted(
            [
                item
                for item in self.records.values()
                if item.household_id == p["household_id"]
                and item.status == MemoryStatus.ACTIVE
                and item.memory_type == MemoryType.EXPLICIT_PREFERENCE
                and item.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
                and (item.expires_at is None or item.expires_at > p["now"])
                and (item.valid_from is None or item.valid_from <= p["now"])
                and (item.valid_until is None or item.valid_until >= p["now"])
                and (p["subject_id"] is None or item.subject_id == p["subject_id"])
                and (p["scope"] is None or item.metadata.get("scope", "household") == p["scope"])
                and (
                    p["category"] is None or item.metadata.get("category", "other") == p["category"]
                )
                and (p["after"] is None or item.memory_id > p["after"])
            ],
            key=lambda item: item.memory_id,
        )[: p["limit"]]

    def _memory(self, row: MemoryRecord) -> MemoryRecord:
        return row


class FakeGraph:
    def __init__(self, household: UUID, principal: UUID) -> None:
        self.owner = CanonicalNode(
            principal, NodeKind.PERSON, "Fixture owner", metadata={"semantic_role": "owner"}
        )
        self.person = CanonicalNode(uuid4(), NodeKind.PERSON, "Fixture member")
        self.household = CanonicalNode(household, NodeKind.HOUSEHOLD, "Fixture household")
        self.foreign = CanonicalNode(uuid4(), NodeKind.PERSON, "Foreign member")
        self.nodes = {
            item.canonical_id: item
            for item in (self.owner, self.person, self.household, self.foreign)
        }

    def get_node(self, node_id: UUID) -> CanonicalNode | None:
        return self.nodes.get(node_id)

    def members_of_household(self, household: UUID) -> list[CanonicalNode]:
        return (
            [self.nodes[self.owner.canonical_id], self.nodes[self.person.canonical_id]]
            if household == self.household.canonical_id
            else []
        )


def context(household_id: UUID, principal_id: UUID) -> InvocationContext:
    return InvocationContext(
        household_id=household_id,
        principal_id=principal_id,
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key=f"test:{uuid4()}",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_preferences_manifest_is_bounded_and_requires_trusted_context() -> None:
    assert PREFERENCES_MANIFEST.required_secrets == ()
    assert {tool["name"] for tool in PREFERENCES_MANIFEST.tools} == {
        "list_preferences",
        "create_preference",
        "update_preference",
        "retract_preference",
    }
    with pytest.raises(PluginValidationError, match="trusted invocation"):
        PreferencesNativePlugin(FakeMemoryService()).invoke("list_preferences", {}, 1.0)


def test_preferences_are_explicitly_provenanced_and_household_scoped() -> None:
    service = FakeMemoryService()
    household = uuid4()
    principal = uuid4()
    plugin = PreferencesNativePlugin(service, FakeGraph(household, principal))
    created = plugin.invoke_with_invocation_context(
        "create_preference",
        {"content": "Notify us about movement overnight", "category": "alerts"},
        1.0,
        context(household, principal),
    )
    preference_id = UUID(created["preference"]["preference_id"])
    record = service.get(preference_id)
    assert record is not None
    assert record.household_id == household
    assert record.memory_type == MemoryType.EXPLICIT_PREFERENCE
    assert record.provenance.kind == ProvenanceKind.EXPLICIT_INPUT
    assert "policy" not in record.metadata

    service.records[preference_id] = replace(record, household_id=uuid4())
    with pytest.raises(PreferenceValidationError, match="does not exist in this household"):
        plugin.invoke_with_invocation_context(
            "update_preference",
            {"preference_id": str(preference_id), "content": "Other household"},
            1.0,
            context(household, principal),
        )


def test_preferences_support_correction_and_retraction_without_authority_fields() -> None:
    service = FakeMemoryService()
    household = uuid4()
    principal = uuid4()
    plugin = PreferencesNativePlugin(service, FakeGraph(household, principal))
    created = plugin.invoke_with_invocation_context(
        "create_preference",
        {"content": "Prefer quiet alerts", "category": "alerts"},
        1.0,
        context(household, principal),
    )
    preference_id = created["preference"]["preference_id"]
    corrected = plugin.invoke_with_invocation_context(
        "update_preference",
        {
            "preference_id": preference_id,
            "content": "Prefer immediate alerts",
            "category": "alerts",
        },
        1.0,
        context(household, principal),
    )
    replacement_id = UUID(corrected["preference"]["preference_id"])
    original = service.get(UUID(preference_id))
    replacement = service.get(replacement_id)
    assert original is not None and original.status == MemoryStatus.SUPERSEDED
    assert replacement is not None and replacement.supersedes_memory_id == UUID(preference_id)
    retracted = plugin.invoke_with_invocation_context(
        "retract_preference",
        {"preference_id": str(replacement_id)},
        1.0,
        context(household, principal),
    )
    assert retracted["preference"]["status"] == MemoryStatus.RETRACTED.value
    with pytest.raises(PreferenceValidationError):
        plugin.invoke_with_invocation_context(
            "create_preference",
            {"content": "x" * 1001},
            1.0,
            context(household, principal),
        )


def fixture() -> tuple[FakeMemoryService, FakeGraph, PreferencesNativePlugin, InvocationContext]:
    service = FakeMemoryService()
    ctx = context(uuid4(), uuid4())
    assert ctx.principal_id is not None
    graph = FakeGraph(ctx.household_id, ctx.principal_id)
    return service, graph, PreferencesNativePlugin(service, graph), ctx


def test_personal_exception_and_household_default_remain_independent_text_data() -> None:
    service, graph, plugin, ctx = fixture()
    household = plugin.invoke_with_invocation_context(
        "create_preference",
        {"content": "Synthetic household wording", "category": "notifications"},
        1,
        ctx,
    )["preference"]
    personal = plugin.invoke_with_invocation_context(
        "create_preference",
        {
            "content": "Synthetic personal exception wording",
            "category": "notifications",
            "person_id": str(graph.person.canonical_id),
        },
        1,
        ctx,
    )["preference"]
    assert household["scope"] == "household" and household["person_id"] is None
    assert personal["scope"] == "personal" and personal["person_name"] == graph.person.name
    assert personal["version"] == personal["preference_id"]
    assert personal["authority"] == household["authority"] == "NONE"
    saved = service.records[UUID(personal["preference_id"])]
    assert saved.subject_id == graph.person.canonical_id
    assert saved.graph_refs == (graph.person.canonical_id,)
    assert saved.metadata == {"scope": "personal", "category": "notifications"}
    assert len(service.records) == 2
    page = plugin.invoke_with_invocation_context("list_preferences", {}, 1, ctx)
    assert len(page["items"]) == 2 and page["next_cursor"] is None
    selected = preferences_page(
        service,
        ctx.household_id,
        graph=graph,
        person_id=str(graph.person.canonical_id),
        category="notifications",
    )
    assert selected["items"] == [personal]
    assert preferences_page(service, ctx.household_id, graph=graph, scope="household")["items"] == [
        household
    ]


def test_personal_scope_version_preservation_explicit_clear_and_stale_guards() -> None:
    service, graph, plugin, ctx = fixture()
    original = plugin.invoke_with_invocation_context(
        "create_preference",
        {
            "content": "Synthetic initial",
            "person_id": str(graph.person.canonical_id),
            "category": "routines",
        },
        1,
        ctx,
    )["preference"]
    changed = plugin.invoke_with_invocation_context(
        "update_preference",
        {
            "preference_id": original["preference_id"],
            "content": "Synthetic correction",
        },
        1,
        ctx,
    )["preference"]
    assert changed["person_id"] == original["person_id"]
    assert changed["category"] == "routines" and changed["scope"] == "personal"
    assert changed["supersedes_preference_id"] == original["version"]
    assert changed["version"] != original["version"]
    old = service.records[UUID(original["preference_id"])]
    assert old.content == "Synthetic initial" and old.status == MemoryStatus.SUPERSEDED
    for operation in ("update_preference", "retract_preference"):
        data = {"preference_id": original["preference_id"]}
        if operation == "update_preference":
            data["content"] = "stale edit"
        with pytest.raises(PreferenceValidationError, match="version changed"):
            plugin.invoke_with_invocation_context(operation, data, 1, ctx)
    household = plugin.invoke_with_invocation_context(
        "update_preference",
        {
            "preference_id": changed["preference_id"],
            "content": "Synthetic shared correction",
            "person_id": None,
        },
        1,
        ctx,
    )["preference"]
    assert household["scope"] == "household" and household["person_id"] is None
    retracted = plugin.invoke_with_invocation_context(
        "retract_preference", {"preference_id": household["preference_id"]}, 1, ctx
    )
    assert retracted["preference"]["status"] == "RETRACTED"
    with pytest.raises(PreferenceValidationError, match="version changed"):
        plugin.invoke_with_invocation_context(
            "retract_preference", {"preference_id": household["preference_id"]}, 1, ctx
        )
    assert preferences_page(service, ctx.household_id)["items"] == []
    assert len(service.records) == 3  # History retained, not prose erasure.


@pytest.mark.parametrize(
    "case",
    [
        "no-graph",
        "no-principal",
        "resident",
        "foreign-owner",
        "autonomous",
        "retired-owner",
        "wrong-kind",
        "wrong-household",
    ],
)
def test_mutations_require_real_canonical_owner_before_memory_write(case: str) -> None:
    service, graph, plugin, ctx = fixture()
    if case == "no-graph":
        plugin = PreferencesNativePlugin(service)
    elif case == "no-principal":
        ctx = replace(ctx, principal_id=None)
    elif case == "resident":
        ctx = replace(ctx, principal_id=graph.person.canonical_id)
    elif case == "foreign-owner":
        graph.nodes[graph.foreign.canonical_id] = replace(
            graph.foreign, metadata={"semantic_role": "owner"}
        )
        ctx = replace(ctx, principal_id=graph.foreign.canonical_id)
    elif case == "autonomous":
        ctx = replace(ctx, origin=RequestOrigin.AUTONOMOUS_AGENT)
    elif case == "retired-owner":
        graph.nodes[graph.owner.canonical_id] = replace(graph.owner, retired_at=datetime.now(UTC))
    elif case == "wrong-kind":
        graph.nodes[graph.owner.canonical_id] = replace(graph.owner, kind=NodeKind.RESOURCE)
    else:
        ctx = replace(ctx, household_id=uuid4())
    for operation in ("create_preference", "update_preference", "retract_preference"):
        with pytest.raises(PreferenceValidationError):
            plugin.invoke_with_invocation_context(
                operation,
                {"content": "Synthetic", "preference_id": str(uuid4())}
                if operation != "create_preference"
                else {"content": "Synthetic"},
                1,
                ctx,
            )
    assert not service.records


@pytest.mark.parametrize("case", ["foreign", "retired", "wrong-kind", "missing", "malformed"])
def test_personal_member_validation_fails_before_write(case: str) -> None:
    service, graph, plugin, ctx = fixture()
    person_id = str(graph.person.canonical_id)
    if case == "foreign":
        person_id = str(graph.foreign.canonical_id)
    elif case == "retired":
        graph.nodes[graph.person.canonical_id] = replace(graph.person, retired_at=datetime.now(UTC))
    elif case == "wrong-kind":
        graph.nodes[graph.person.canonical_id] = replace(graph.person, kind=NodeKind.ROOM)
    elif case == "missing":
        person_id = str(uuid4())
    else:
        person_id = "not-a-person-id"
    with pytest.raises(PreferenceValidationError):
        plugin.invoke_with_invocation_context(
            "create_preference", {"content": "Synthetic", "person_id": person_id}, 1, ctx
        )
    assert not service.records


@pytest.mark.parametrize(
    "field",
    [
        "authority",
        "policy",
        "semantic_role",
        "source_ref",
        "scope",
        "household_id",
        "version",
        "action",
    ],
)
def test_native_invocation_rejects_forged_metadata_even_without_schema_validation(
    field: str,
) -> None:
    service, _, plugin, ctx = fixture()
    with pytest.raises(PreferenceValidationError):
        plugin.invoke_with_invocation_context(
            "create_preference", {"content": "Synthetic", field: "forged"}, 1, ctx
        )
    assert not service.records


def test_legacy_records_are_household_scoped_and_pagination_filters_before_limit() -> None:
    service, graph, plugin, ctx = fixture()
    legacy = MemoryRecord.create(
        household_id=ctx.household_id,
        memory_type=MemoryType.EXPLICIT_PREFERENCE,
        content="Synthetic legacy",
        provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "fixture"),
        metadata={"category": "alerts"},
    )
    service.create(legacy)
    assert preference_payload(legacy)["scope"] == "household"
    for index in range(111):
        plugin.invoke_with_invocation_context(
            "create_preference",
            {
                "content": f"Synthetic {index}",
                "category": "general",
                "person_id": str(graph.person.canonical_id),
            },
            1,
            ctx,
        )
        service.create(replace(legacy, memory_id=uuid4(), household_id=uuid4()))
        service.create(replace(legacy, memory_id=uuid4(), memory_type=MemoryType.EXPLICIT_FACT))
    first = preferences_page(
        service,
        ctx.household_id,
        graph=graph,
        category="general",
        person_id=str(graph.person.canonical_id),
        limit=100,
    )
    second = preferences_page(
        service,
        ctx.household_id,
        graph=graph,
        category="general",
        person_id=str(graph.person.canonical_id),
        limit=100,
        cursor=first["next_cursor"],
    )
    assert len(first["items"]) == 100 and len(second["items"]) == 11
    assert len({item["preference_id"] for item in first["items"] + second["items"]}) == 111
    assert second["next_cursor"] is None
    assert preferences_page(service, ctx.household_id, category="alerts")["items"] == [
        preference_payload(legacy)
    ]
    with pytest.raises(PreferenceValidationError, match="paginated"):
        preference_payloads(service, ctx.household_id)


@pytest.mark.parametrize("kind", ["wrong-type", "nonexplicit"])
def test_nonpreference_or_nonexplicit_history_cannot_be_corrected_or_retracted(kind: str) -> None:
    service, _, plugin, ctx = fixture()
    created = plugin.invoke_with_invocation_context(
        "create_preference", {"content": "Synthetic"}, 1, ctx
    )["preference"]
    key = UUID(created["preference_id"])
    original = service.records[key]
    service.records[key] = (
        replace(original, memory_type=MemoryType.EXPLICIT_FACT)
        if kind == "wrong-type"
        else replace(
            original, provenance=MemoryProvenance(ProvenanceKind.INFERRED_FROM_HISTORY, "fixture")
        )
    )
    for operation in ("update_preference", "retract_preference"):
        with pytest.raises(PreferenceValidationError, match="explicit owner preference"):
            plugin.invoke_with_invocation_context(
                operation,
                {
                    "preference_id": str(key),
                    **({"content": "Synthetic"} if operation == "update_preference" else {}),
                },
                1,
                ctx,
            )
    assert service.records[key].status == MemoryStatus.ACTIVE


@pytest.mark.parametrize(
    "arguments",
    [
        {"limit": 0},
        {"limit": 101},
        {"limit": True},
        {"cursor": "bad"},
        {"scope": "private"},
        {"category": "email_action"},
        {"category": {}},
    ],
)
def test_invalid_list_filters_fail_closed(arguments: dict[str, Any]) -> None:
    service, graph, _, ctx = fixture()
    with pytest.raises(PreferenceValidationError):
        preferences_page(service, ctx.household_id, graph=graph, **arguments)


def test_optin_postgres_personal_and_legacy_preferences_filter_page_and_reload() -> None:
    import psycopg

    from anima_ha.db.migrate import migrate
    from anima_ha.graph import (
        CanonicalRelationship,
        CommissioningDocument,
        PostgresHouseholdGraph,
        RelationshipType,
    )
    from anima_ha.memory import MemoryService

    database_url = os.environ.get("ANIMA_PREFERENCES_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("requires isolated ANIMA_PREFERENCES_TEST_DATABASE_URL")
    with psycopg.connect(database_url) as connection:
        assert connection.execute("SELECT current_database()").fetchone() == (
            "anima_preferences_test",
        )
    migrate(database_url, 5)
    _, data, _, ctx = fixture()
    graph = PostgresHouseholdGraph(database_url)
    graph.commission(
        CommissioningDocument(
            1,
            (data.household, data.owner, data.person),
            (
                CanonicalRelationship(
                    uuid4(), RelationshipType.MEMBER_OF, data.owner.canonical_id, ctx.household_id
                ),
                CanonicalRelationship(
                    uuid4(), RelationshipType.MEMBER_OF, data.person.canonical_id, ctx.household_id
                ),
            ),
        )
    )
    memory = MemoryService(database_url, index_enabled=False)
    plugin = PreferencesNativePlugin(memory, graph)
    legacy = memory.create(
        MemoryRecord.create(
            household_id=ctx.household_id,
            memory_type=MemoryType.EXPLICIT_PREFERENCE,
            content="Synthetic legacy default",
            provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "fixture"),
        )
    )
    for index in range(102):
        plugin.invoke_with_invocation_context(
            "create_preference",
            {
                "content": f"Synthetic scoped {index}",
                "category": "notifications",
                "person_id": str(data.person.canonical_id),
            },
            1,
            ctx,
        )
    memory.create(replace(legacy, memory_id=uuid4(), memory_type=MemoryType.EXPLICIT_FACT))
    memory.create(replace(legacy, memory_id=uuid4(), household_id=uuid4()))
    fresh = MemoryService(database_url, index_enabled=False)
    first = preferences_page(
        fresh,
        ctx.household_id,
        graph=graph,
        person_id=str(data.person.canonical_id),
        category="notifications",
        limit=100,
    )
    second = preferences_page(
        fresh,
        ctx.household_id,
        graph=graph,
        person_id=str(data.person.canonical_id),
        category="notifications",
        limit=100,
        cursor=first["next_cursor"],
    )
    assert len(first["items"]) == 100 and len(second["items"]) == 2
    assert len({item["version"] for item in first["items"] + second["items"]}) == 102
    assert second["next_cursor"] is None
    assert preferences_page(fresh, ctx.household_id, graph=graph, scope="household")["items"] == [
        preference_payload(legacy, graph)
    ]
    chosen = first["items"][0]
    corrected = plugin.invoke_with_invocation_context(
        "update_preference",
        {
            "preference_id": chosen["preference_id"],
            "content": "Synthetic replacement",
        },
        1,
        ctx,
    )["preference"]
    assert corrected["person_id"] == chosen["person_id"]
    assert corrected["supersedes_preference_id"] == chosen["version"]
    with pytest.raises(PreferenceValidationError, match="version changed"):
        plugin.invoke_with_invocation_context(
            "retract_preference", {"preference_id": chosen["preference_id"]}, 1, ctx
        )
    plugin.invoke_with_invocation_context(
        "retract_preference", {"preference_id": corrected["preference_id"]}, 1, ctx
    )
    old = fresh.get(UUID(chosen["preference_id"]))
    latest = fresh.get(UUID(corrected["preference_id"]))
    assert old is not None and old.status == MemoryStatus.SUPERSEDED
    assert latest is not None and latest.status == MemoryStatus.RETRACTED
    assert old.content == chosen["content"] and latest.content == "Synthetic replacement"
