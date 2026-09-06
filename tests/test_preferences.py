from __future__ import annotations

from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from anima_ha.memory import (
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
)


class FakeMemoryService:
    def __init__(self) -> None:
        self.records: dict[UUID, MemoryRecord] = {}

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
        self.records[original_id] = replace(original, status=MemoryStatus.SUPERSEDED)
        self.records[replacement.memory_id] = replacement
        return replacement

    def retract(self, memory_id: UUID) -> MemoryRecord:
        original = self.records[memory_id]
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
    plugin = PreferencesNativePlugin(service)
    household = uuid4()
    principal = uuid4()
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

    with pytest.raises(PreferenceValidationError, match="does not exist in this household"):
        plugin.invoke_with_invocation_context(
            "update_preference",
            {"preference_id": str(preference_id), "content": "Other household"},
            1.0,
            context(uuid4(), uuid4()),
        )


def test_preferences_support_correction_and_retraction_without_authority_fields() -> None:
    service = FakeMemoryService()
    plugin = PreferencesNativePlugin(service)
    household = uuid4()
    principal = uuid4()
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
