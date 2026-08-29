"""Pure contract and commissioning validation tests."""

# ruff: noqa: E501

from dataclasses import replace
from uuid import uuid4

import pytest

from anima_ha.fixtures import sample_household_document
from anima_ha.graph import (
    CanonicalRelationship,
    GraphConflict,
    GraphValidationError,
    RelationshipType,
    validate_commissioning,
)


def test_sample_commissioning_is_complete_and_provider_independent() -> None:
    document = sample_household_document()
    validate_commissioning(document)
    assert sum(node.kind.value == "ROOM" for node in document.nodes) >= 5
    assert sum(node.kind.value == "ENTRANCE" for node in document.nodes) == 2
    assert any(binding.semantic_attribute == "presence.home" for binding in document.truth_bindings)
    assert all(reference.provider != "homeassistant" for reference in document.provider_references)


def test_containment_cycle_is_rejected() -> None:
    document = sample_household_document()
    cycle = CanonicalRelationship(
        uuid4(),
        RelationshipType.CONTAINS,
        document.relationships[0].target_id,
        document.relationships[0].source_id,
    )
    with pytest.raises(GraphValidationError, match="cycle"):
        validate_commissioning(replace(document, relationships=document.relationships + (cycle,)))


def test_dangling_relationship_is_rejected() -> None:
    document = sample_household_document()
    dangling = replace(document.relationships[0], target_id=uuid4())
    with pytest.raises(GraphValidationError):
        validate_commissioning(replace(document, relationships=(dangling,)))


def test_alias_collision_is_explicit() -> None:
    document = sample_household_document()
    first = document.aliases[0]
    second = replace(
        first, alias_id=document.aliases[1].alias_id, canonical_id=document.nodes[7].canonical_id
    )
    with pytest.raises(GraphConflict, match="ambiguous"):
        validate_commissioning(replace(document, aliases=(first, second)))


def test_invalid_entrance_endpoints_are_rejected() -> None:
    document = sample_household_document()
    bad = replace(document.relationships[11], target_id=document.nodes[14].canonical_id)
    with pytest.raises(GraphValidationError, match="CONNECTS"):
        validate_commissioning(
            replace(
                document,
                relationships=document.relationships[:11] + (bad,) + document.relationships[12:],
            )
        )
