"""ANIMA-owned explicit household preferences.

Preferences are presentation/context inputs, not an authority or policy
surface.  They are persisted through the canonical governed MemoryService so
correction and retraction remain auditable and household-scoped.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from anima_ha.memory import (
    MemoryProvenance,
    MemoryRecord,
    MemoryStatus,
    MemoryType,
    ProvenanceKind,
)
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

MAX_PREFERENCE_LENGTH = 1000
MAX_PREFERENCES = 100
PREFERENCE_CATEGORIES = ("alerts", "comfort", "meals", "shopping", "privacy", "other")


class PreferenceValidationError(ValueError):
    """A preference is outside the bounded owner-facing contract."""


def _content(value: Any) -> str:
    if not isinstance(value, str):
        raise PreferenceValidationError("preference content must be text")
    content = " ".join(value.split())
    if not 1 <= len(content) <= MAX_PREFERENCE_LENGTH:
        raise PreferenceValidationError("preference content length is invalid")
    return content


def _category(value: Any) -> str:
    category = str(value or "other").strip().casefold()
    if category not in PREFERENCE_CATEGORIES:
        raise PreferenceValidationError("unsupported preference category")
    return category


def preference_payload(memory: MemoryRecord) -> dict[str, Any]:
    """Return the browser/SENTRY-safe projection, excluding authority data."""

    return {
        "preference_id": str(memory.memory_id),
        "content": memory.content,
        "category": str(memory.metadata.get("category", "other")),
        "created_at": memory.created_at.isoformat(),
        "status": memory.status.value,
        "provenance": {"kind": memory.provenance.kind.value},
    }


def preference_payloads(memory_service: Any, household_id: UUID) -> list[dict[str, Any]]:
    records = memory_service.retrieve(
        "",
        household_id=household_id,
        top_k=MAX_PREFERENCES,
        memory_types=[MemoryType.EXPLICIT_PREFERENCE],
    )
    return [
        preference_payload(item.memory)
        for item in records
        if item.memory.status == MemoryStatus.ACTIVE
    ]


class PreferencesNativePlugin:
    def __init__(self, memory_service: Any) -> None:
        self.memory_service = memory_service

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in PREFERENCES_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("household-preferences requires trusted invocation context")

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> Any:
        del timeout
        if name == "list_preferences":
            return {
                "status": "SUCCEEDED",
                "items": preference_payloads(self.memory_service, context.household_id),
            }
        if name == "create_preference":
            content = _content(arguments.get("content"))
            category = _category(arguments.get("category"))
            memory = MemoryRecord.create(
                household_id=context.household_id,
                memory_type=MemoryType.EXPLICIT_PREFERENCE,
                content=content,
                provenance=MemoryProvenance(
                    ProvenanceKind.EXPLICIT_INPUT,
                    f"anima:principal:{context.principal_id}",
                ),
                confidence=1.0,
                metadata={"category": category},
            )
            created = self.memory_service.create(memory)
            return {"status": "SUCCEEDED", "preference": preference_payload(created)}
        if name == "update_preference":
            preference_id = UUID(str(arguments.get("preference_id")))
            original = self.memory_service.get(preference_id)
            if original is None or original.household_id != context.household_id:
                raise PreferenceValidationError("preference does not exist in this household")
            if original.memory_type != MemoryType.EXPLICIT_PREFERENCE:
                raise PreferenceValidationError("memory is not an explicit preference")
            if original.status != MemoryStatus.ACTIVE:
                raise PreferenceValidationError("only active preferences may be updated")
            content = _content(arguments.get("content"))
            category = _category(arguments.get("category", original.metadata.get("category")))
            replacement = MemoryRecord.create(
                household_id=context.household_id,
                memory_type=MemoryType.EXPLICIT_PREFERENCE,
                content=content,
                provenance=MemoryProvenance(
                    ProvenanceKind.EXPLICIT_INPUT,
                    f"anima:principal:{context.principal_id}",
                ),
                confidence=1.0,
                supersedes_memory_id=original.memory_id,
                metadata={"category": category},
            )
            corrected = self.memory_service.correct(original.memory_id, replacement)
            return {"status": "SUCCEEDED", "preference": preference_payload(corrected)}
        if name == "retract_preference":
            preference_id = UUID(str(arguments.get("preference_id")))
            original = self.memory_service.get(preference_id)
            if original is None or original.household_id != context.household_id:
                raise PreferenceValidationError("preference does not exist in this household")
            if original.memory_type != MemoryType.EXPLICIT_PREFERENCE:
                raise PreferenceValidationError("memory is not an explicit preference")
            retracted = self.memory_service.retract(preference_id)
            return {"status": "SUCCEEDED", "preference": preference_payload(retracted)}
        raise PluginValidationError("unknown household-preferences tool")


_PREFERENCE_OUTPUT = {
    "type": "object",
    "required": ["status"],
    "properties": {"status": {"type": "string"}},
    "additionalProperties": True,
}

PREFERENCES_MANIFEST = PluginManifest(
    plugin_id="anima.household-preferences",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Household preferences",
    description="Manage bounded explicit preferences used by household context",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.preferences",),
    tools=(
        {
            "name": "list_preferences",
            "description": "List active explicit household preferences",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {**_PREFERENCE_OUTPUT, "required": ["status", "items"]},
            "semantic_action": "capabilities.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "create_preference",
            "description": "Record one explicit household preference",
            "input_schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_PREFERENCE_LENGTH,
                    },
                    "category": {"type": "string", "enum": list(PREFERENCE_CATEGORIES)},
                },
                "required": ["content"],
                "additionalProperties": False,
            },
            "output_schema": _PREFERENCE_OUTPUT,
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "update_preference",
            "description": "Correct one explicit household preference",
            "input_schema": {
                "type": "object",
                "properties": {
                    "preference_id": {"type": "string", "format": "uuid"},
                    "content": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_PREFERENCE_LENGTH,
                    },
                    "category": {"type": "string", "enum": list(PREFERENCE_CATEGORIES)},
                },
                "required": ["preference_id", "content"],
                "additionalProperties": False,
            },
            "output_schema": _PREFERENCE_OUTPUT,
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "retract_preference",
            "description": "Retract one explicit household preference",
            "input_schema": {
                "type": "object",
                "properties": {"preference_id": {"type": "string", "format": "uuid"}},
                "required": ["preference_id"],
                "additionalProperties": False,
            },
            "output_schema": _PREFERENCE_OUTPUT,
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
    ),
    source="builtin:anima_ha.preferences",
)
