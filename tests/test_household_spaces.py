from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from anima_ha.graph import NodeKind
from anima_ha.household_spaces import HOUSEHOLD_SPACES_MANIFEST, HouseholdSpacesNativePlugin
from anima_ha.plugins import InvocationContext, PluginValidationError
from anima_ha.policy import RequestOrigin

HOUSEHOLD = UUID("00000000-0000-0000-0000-000000000012")
PARENT = UUID("00000000-0000-0000-0000-000000000014")


class FakeGraph:
    def __init__(self) -> None:
        self.created: list[tuple[UUID, UUID, str, NodeKind]] = []
        self.renamed: list[tuple[UUID, UUID, str]] = []
        self.root = SimpleNamespace(canonical_id=HOUSEHOLD, kind=NodeKind.HOUSEHOLD, name="Home")
        self.room = SimpleNamespace(canonical_id=PARENT, kind=NodeKind.ROOM, name="Living room")

    def get_node(self, canonical_id: UUID) -> object | None:
        return self.root if canonical_id == HOUSEHOLD else None

    def places_in_household(self, household_id: UUID) -> list[object]:
        assert household_id == HOUSEHOLD
        return [self.room]

    def parent_of_place(self, household_id: UUID, place_id: UUID) -> UUID | None:
        assert household_id == HOUSEHOLD
        return HOUSEHOLD if place_id == PARENT else None

    def create_place(
        self, household_id: UUID, parent_id: UUID, name: str, kind: NodeKind
    ) -> object:
        self.created.append((household_id, parent_id, name, kind))
        return SimpleNamespace(canonical_id=uuid4(), kind=kind, name=name)

    def rename_place(self, household_id: UUID, place_id: UUID, name: str) -> object:
        self.renamed.append((household_id, place_id, name))
        return SimpleNamespace(canonical_id=place_id, kind=NodeKind.ROOM, name=name)

    def move_place(self, household_id: UUID, place_id: UUID, parent_id: UUID) -> object:
        assert household_id == HOUSEHOLD
        return SimpleNamespace(canonical_id=place_id, kind=NodeKind.ROOM, name="Living room")

    def retire_place(self, household_id: UUID, place_id: UUID) -> object:
        assert household_id == HOUSEHOLD
        return SimpleNamespace(canonical_id=place_id, kind=NodeKind.ROOM, name="Living room")


def context() -> InvocationContext:
    return InvocationContext(
        household_id=HOUSEHOLD,
        principal_id=uuid4(),
        episode_id=None,
        tool_request_id=uuid4(),
        ordinal=1,
        system_idempotency_key="test:space",
        origin=RequestOrigin.DIRECT_USER,
    )


def test_household_spaces_requires_trusted_context() -> None:
    plugin = HouseholdSpacesNativePlugin(FakeGraph())  # type: ignore[arg-type]
    with pytest.raises(PluginValidationError):
        plugin.invoke("list_spaces", {}, 1.0)


def test_household_spaces_are_context_scoped_and_typed() -> None:
    graph = FakeGraph()
    plugin = HouseholdSpacesNativePlugin(graph)  # type: ignore[arg-type]
    listed = plugin.invoke_with_invocation_context("list_spaces", {}, 1.0, context())
    assert listed["status"] == "SUCCEEDED"
    assert listed["items"] == [
        {"place_id": str(HOUSEHOLD), "name": "Home", "kind": "HOUSEHOLD", "parent_id": None},
        {
            "place_id": str(PARENT),
            "name": "Living room",
            "kind": "ROOM",
            "parent_id": str(HOUSEHOLD),
        },
    ]

    created = plugin.invoke_with_invocation_context(
        "create_space",
        {"parent_id": str(HOUSEHOLD), "name": "Basement", "kind": "ROOM"},
        1.0,
        context(),
    )
    assert created["status"] == "SUCCEEDED"
    assert graph.created == [(HOUSEHOLD, HOUSEHOLD, "Basement", NodeKind.ROOM)]


def test_household_spaces_move_and_remove_use_typed_context() -> None:
    plugin = HouseholdSpacesNativePlugin(FakeGraph())  # type: ignore[arg-type]
    moved = plugin.invoke_with_invocation_context(
        "move_space",
        {"place_id": str(PARENT), "parent_id": str(HOUSEHOLD)},
        1.0,
        context(),
    )
    removed = plugin.invoke_with_invocation_context(
        "remove_space", {"place_id": str(PARENT)}, 1.0, context()
    )
    assert moved["status"] == "SUCCEEDED"
    assert moved["space"]["parent_id"] == str(HOUSEHOLD)
    assert removed["status"] == "SUCCEEDED"
    assert removed["removed"]["place_id"] == str(PARENT)


def test_household_spaces_manifest_has_no_household_authority_argument() -> None:
    create = next(
        item for item in HOUSEHOLD_SPACES_MANIFEST.tools if item["name"] == "create_space"
    )
    assert "household_id" not in create["input_schema"]["properties"]
    assert create["input_schema"]["additionalProperties"] is False
    assert {item["name"] for item in HOUSEHOLD_SPACES_MANIFEST.tools} == {
        "list_spaces",
        "create_space",
        "rename_space",
        "move_space",
        "remove_space",
    }
