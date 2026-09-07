"""ANIMA-owned explicit household preferences.

Preferences are presentation/context inputs, not an authority or policy
surface.  They are persisted through the canonical governed MemoryService so
correction and retraction remain auditable and household-scoped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from anima_ha.graph import NodeKind
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
from anima_ha.policy import RequestOrigin

MAX_PREFERENCE_LENGTH = 1000
MAX_PREFERENCES = 100
PREFERENCE_CATEGORIES = (
    "alerts",
    "comfort",
    "meals",
    "shopping",
    "privacy",
    "other",
    "notifications",
    "routines",
    "general",
)


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
    if value is not None and not isinstance(value, str):
        raise PreferenceValidationError("unsupported preference category")
    category = str(value or "other").strip().casefold()
    if category not in PREFERENCE_CATEGORIES:
        raise PreferenceValidationError("unsupported preference category")
    return category


def _uuid(value: Any) -> UUID:
    try:
        if not isinstance(value, str):
            raise ValueError
        parsed = UUID(value)
        if parsed.int == 0:
            raise ValueError
        return parsed
    except ValueError:
        raise PreferenceValidationError("a canonical identifier is required") from None


def _household(graph: Any, household_id: UUID) -> None:
    root = graph.get_node(household_id) if graph is not None else None
    if root is None or root.kind != NodeKind.HOUSEHOLD or root.retired_at is not None:
        raise PreferenceValidationError("a commissioned household is required")


def _member(graph: Any, household_id: UUID, person_id: UUID) -> Any:
    _household(graph, household_id)
    person = graph.get_node(person_id)
    if (
        person is None
        or person.kind != NodeKind.PERSON
        or person.retired_at is not None
        or not any(
            item.canonical_id == person_id for item in graph.members_of_household(household_id)
        )
    ):
        raise PreferenceValidationError("person does not belong to this household")
    return person


def preference_payload(memory: MemoryRecord, graph: Any = None) -> dict[str, Any]:
    """Return the browser/SENTRY-safe projection, excluding authority data."""

    scope = memory.metadata.get("scope", "household")
    if scope not in {"household", "personal"} or (
        scope == "personal" and memory.subject_id is None
    ):
        raise PreferenceValidationError("invalid preference scope")
    person_id = memory.subject_id if scope == "personal" else None
    person = (
        _member(graph, memory.household_id, person_id) if graph is not None and person_id else None
    )
    return {
        "preference_id": str(memory.memory_id),
        "content": memory.content,
        "category": str(memory.metadata.get("category", "other")),
        "created_at": memory.created_at.isoformat(),
        "status": memory.status.value,
        "scope": scope,
        "person_id": str(person_id) if person_id else None,
        "person_name": person.name
        if person is not None and person.kind == NodeKind.PERSON
        else None,
        "version": str(memory.memory_id),
        "supersedes_preference_id": str(memory.supersedes_memory_id)
        if memory.supersedes_memory_id
        else None,
        "classification": "OWNER_DECLARED_PREFERENCE",
        "authority": "NONE",
        "provenance": {"kind": memory.provenance.kind.value},
    }


def preferences_page(
    memory_service: Any,
    household_id: UUID,
    *,
    graph: Any = None,
    scope: str | None = None,
    person_id: str | None = None,
    category: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Filter in canonical Memory BEFORE bounded UUID keyset pagination."""
    if graph is not None:
        _household(graph, household_id)
    if scope is not None and scope not in ("household", "personal"):
        raise PreferenceValidationError("unsupported preference scope")
    subject = _uuid(person_id) if person_id is not None else None
    if subject is not None:
        _member(graph, household_id, subject)
        if scope == "household":
            raise PreferenceValidationError("household scope cannot select a person")
        scope = "personal"
    if type(limit) is not int or not 1 <= limit <= MAX_PREFERENCES:
        raise PreferenceValidationError("page size must be 1–100")
    after = _uuid(cursor) if cursor is not None else None
    category_filter = _category(category) if category is not None else None
    where, params = memory_service._rows_for_filters(
        household_id=household_id,
        subject_id=subject,
        memory_types=[MemoryType.EXPLICIT_PREFERENCE],
        graph_ref=None,
        now=datetime.now(UTC),
    )
    params.update(scope=scope, category=category_filter, after=after, limit=limit + 1)
    with memory_service._connect() as connection, connection.cursor() as sql:
        sql.execute(
            f"""SELECT m.* FROM anima_memory_records m WHERE {where}
            AND m.provenance_kind = 'EXPLICIT_INPUT'
            AND COALESCE(m.metadata->>'scope', 'household') IN ('household', 'personal')
            AND (%(scope)s::text IS NULL OR COALESCE(m.metadata->>'scope', 'household') = %(scope)s)
            AND (%(category)s::text IS NULL
                 OR COALESCE(m.metadata->>'category', 'other') = %(category)s)
            AND (%(after)s::uuid IS NULL OR m.memory_id > %(after)s::uuid)
            ORDER BY m.memory_id ASC LIMIT %(limit)s""",
            params,
        )
        records = [memory_service._memory(row) for row in sql.fetchall()]
    return {
        "status": "SUCCEEDED",
        "items": [preference_payload(item, graph) for item in records[:limit]],
        "next_cursor": str(records[limit - 1].memory_id) if len(records) > limit else None,
    }


def preference_payloads(memory_service: Any, household_id: UUID) -> list[dict[str, Any]]:
    """Legacy list projection; never silently truncate a larger household."""
    page = preferences_page(memory_service, household_id, limit=MAX_PREFERENCES)
    if page["next_cursor"] is not None:
        raise PreferenceValidationError("use paginated preferences to load all records")
    return list(page["items"])


class PreferencesNativePlugin:
    def __init__(self, memory_service: Any, graph: Any = None) -> None:
        self.memory_service, self.graph = memory_service, graph

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
            if set(arguments) - {"scope", "person_id", "category", "limit", "cursor"}:
                raise PreferenceValidationError("unsupported list fields")
            return preferences_page(
                self.memory_service, context.household_id, graph=self.graph, **arguments
            )
        if name not in {"create_preference", "update_preference", "retract_preference"}:
            raise PluginValidationError("unknown household-preferences tool")
        if context.principal_id is None:
            raise PreferenceValidationError("a commissioned owner is required")
        owner = _member(self.graph, context.household_id, context.principal_id)
        if context.origin != RequestOrigin.DIRECT_USER:
            raise PreferenceValidationError("a direct household request is required")
        is_owner = owner.metadata.get("semantic_role") == "owner"
        if not is_owner and (
            name == "retract_preference"
            or str(arguments.get("person_id", "")) != str(context.principal_id)
        ):
            raise PreferenceValidationError(
                "limited users may change only their own personal preferences"
            )
        allowed = (
            {"preference_id"}
            if name == "retract_preference"
            else {"content", "category", "person_id"}
        )
        if name == "update_preference":
            allowed.add("preference_id")
        if set(arguments) - allowed:
            raise PreferenceValidationError("unsupported preference fields")
        if name == "create_preference":
            content = _content(arguments.get("content"))
            category = _category(arguments.get("category"))
            person_id = (
                _uuid(arguments["person_id"]) if arguments.get("person_id") is not None else None
            )
            if person_id is not None:
                _member(self.graph, context.household_id, person_id)
            memory = MemoryRecord.create(
                household_id=context.household_id,
                subject_id=person_id,
                memory_type=MemoryType.EXPLICIT_PREFERENCE,
                content=content,
                provenance=MemoryProvenance(
                    ProvenanceKind.EXPLICIT_INPUT,
                    f"anima:principal:{context.principal_id}",
                ),
                confidence=1.0,
                graph_refs=(person_id,) if person_id else (),
                metadata={"category": category, "scope": "personal" if person_id else "household"},
            )
            created = self.memory_service.create(memory)
            return {"status": "SUCCEEDED", "preference": preference_payload(created, self.graph)}
        preference_id = _uuid(arguments.get("preference_id"))
        original = self.memory_service.get(preference_id)
        if original is None or original.household_id != context.household_id:
            raise PreferenceValidationError("preference does not exist in this household")
        if (
            original.memory_type != MemoryType.EXPLICIT_PREFERENCE
            or original.provenance.kind != ProvenanceKind.EXPLICIT_INPUT
        ):
            raise PreferenceValidationError("memory is not an explicit owner preference")
        if original.status != MemoryStatus.ACTIVE or original.superseded_by_memory_id is not None:
            raise PreferenceValidationError("preference version changed; reload before editing")
        original_payload = preference_payload(original, self.graph)
        if original_payload["person_id"] is not None:
            _member(self.graph, context.household_id, _uuid(original_payload["person_id"]))
        if name == "update_preference":
            content = _content(arguments.get("content"))
            category = _category(arguments.get("category", original.metadata.get("category")))
            selected = arguments.get("person_id", original_payload["person_id"])
            person_id = _uuid(selected) if selected is not None else None
            if person_id is not None:
                _member(self.graph, context.household_id, person_id)
            replacement = MemoryRecord.create(
                household_id=context.household_id,
                subject_id=person_id,
                memory_type=MemoryType.EXPLICIT_PREFERENCE,
                content=content,
                provenance=MemoryProvenance(
                    ProvenanceKind.EXPLICIT_INPUT,
                    f"anima:principal:{context.principal_id}",
                ),
                confidence=1.0,
                supersedes_memory_id=original.memory_id,
                graph_refs=(person_id,) if person_id else (),
                metadata={"category": category, "scope": "personal" if person_id else "household"},
            )
            corrected = self.memory_service.correct(original.memory_id, replacement)
            return {"status": "SUCCEEDED", "preference": preference_payload(corrected, self.graph)}
        if name == "retract_preference":
            retracted = self.memory_service.retract(preference_id)
            return {"status": "SUCCEEDED", "preference": preference_payload(retracted, self.graph)}
        raise PluginValidationError("unknown household-preferences tool")


_PREFERENCE_OUTPUT = {
    "type": "object",
    "required": ["status"],
    "properties": {"status": {"type": "string"}},
    "additionalProperties": True,
}

PREFERENCES_MANIFEST = PluginManifest(
    plugin_id="anima.household-preferences",
    plugin_version="1.1.0",
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
            "input_schema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["household", "personal"]},
                    "person_id": {"type": ["string", "null"], "format": "uuid"},
                    "category": {"type": "string", "enum": list(PREFERENCE_CATEGORIES)},
                    "limit": {"type": "integer", "minimum": 1, "maximum": MAX_PREFERENCES},
                    "cursor": {"type": "string", "format": "uuid"},
                },
                "additionalProperties": False,
            },
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
                    "person_id": {"type": ["string", "null"], "format": "uuid"},
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
                    "person_id": {"type": ["string", "null"], "format": "uuid"},
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
