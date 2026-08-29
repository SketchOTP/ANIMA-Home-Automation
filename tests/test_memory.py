from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryType,
    MemoryValidationError,
    ProvenanceKind,
    memory_precedence,
    normalize_retrieval_text,
)


def test_memory_contract_normalizes_search_text_and_has_no_authority_surface() -> None:
    memory = MemoryRecord.create(
        household_id=uuid4(),
        memory_type=MemoryType.EXPLICIT_PREFERENCE,
        content="  Notify us about unusual movement. ",
        provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "interaction:test"),
        created_at=datetime(2026, 8, 29, tzinfo=UTC),
    )
    assert memory.retrieval_text == normalize_retrieval_text("Notify us about unusual movement.")
    assert not hasattr(memory, "permissions")
    assert memory_precedence(MemoryType.EXPLICIT_PREFERENCE) > memory_precedence(
        MemoryType.INFERRED_PATTERN
    )


def test_agent_lessons_are_lower_confidence_and_metadata_cannot_grant_authority() -> None:
    with pytest.raises(MemoryValidationError, match="agent lessons"):
        MemoryRecord.create(
            household_id=uuid4(),
            memory_type=MemoryType.AGENT_LESSON,
            content="A bounded lesson.",
            provenance=MemoryProvenance(ProvenanceKind.AGENT_LESSON, "lesson:test"),
            confidence=0.8,
        )
    with pytest.raises(MemoryValidationError, match="authority"):
        MemoryRecord.create(
            household_id=uuid4(),
            memory_type=MemoryType.EXPLICIT_PREFERENCE,
            content="Prefer quiet notifications.",
            provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "interaction:test"),
            metadata={"permissions": ["unlock"]},
        )


def test_temporary_memory_window_is_validated() -> None:
    now = datetime(2026, 8, 29, tzinfo=UTC)
    with pytest.raises(MemoryValidationError, match="valid_until"):
        MemoryRecord.create(
            household_id=uuid4(),
            memory_type=MemoryType.TEMPORARY_EPISODIC,
            content="Guests are staying.",
            provenance=MemoryProvenance(ProvenanceKind.EXPLICIT_INPUT, "interaction:test"),
            valid_from=now,
            valid_until=now - timedelta(minutes=1),
        )
