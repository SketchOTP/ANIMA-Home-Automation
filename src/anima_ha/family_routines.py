"""Owner-declared expectations, versioned by governed Memory, never inferred Truth."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from anima_ha.graph import (
    CanonicalNode,
    CanonicalRelationship,
    CommissioningDocument,
    NodeKind,
    RelationshipType,
    normalize_alias,
)
from anima_ha.memory import MemoryProvenance, MemoryRecord, MemoryStatus, MemoryType, ProvenanceKind
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


class FamilyRoutineError(ValueError):
    """A bounded routine request is invalid or outside its household."""


def _uuid(value: Any) -> UUID:
    if not isinstance(value, str):
        raise FamilyRoutineError("A canonical identifier is required")
    try:
        return UUID(value)
    except ValueError:
        raise FamilyRoutineError("Invalid canonical identifier") from None


def _text(value: Any, minimum: int, maximum: int, label: str) -> str:
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise FamilyRoutineError(f"{label} must contain {minimum}–{maximum} characters")
    if any(ord(character) < 32 and character not in "\n\t" for character in value):
        raise FamilyRoutineError(f"{label} contains unsupported control characters")
    return value.strip()


def _household(graph: Any, household_id: UUID) -> None:
    root = graph.get_node(household_id)
    if root is None or root.kind != NodeKind.HOUSEHOLD or root.retired_at is not None:
        raise FamilyRoutineError("Household is unavailable")


def _person(graph: Any, household_id: UUID, person_id: UUID) -> Any:
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
        raise FamilyRoutineError("Member does not belong to this household")
    return person


def _place(graph: Any, household_id: UUID, place_id: UUID | None) -> Any:
    if place_id is None:
        return None
    place = graph.get_node(place_id)
    if (
        place is None
        or place.kind not in {NodeKind.ROOM, NodeKind.ZONE}
        or place.retired_at is not None
        or not any(
            item.canonical_id == place_id for item in graph.places_in_household(household_id)
        )
    ):
        raise FamilyRoutineError("Place must be a room or zone in this household")
    return place


def family_routine_options(graph: Any, household_id: UUID) -> dict[str, Any]:
    _household(graph, household_id)
    return {
        "members": [
            {"person_id": str(item.canonical_id), "name": item.name}
            for item in graph.members_of_household(household_id)
            if item.kind == NodeKind.PERSON and item.retired_at is None
        ],
        "places": [
            {"place_id": str(item.canonical_id), "name": item.name}
            for item in graph.places_in_household(household_id)
            if item.kind in {NodeKind.ROOM, NodeKind.ZONE} and item.retired_at is None
        ],
    }


_FIELDS = {"person_id", "label", "days", "start", "end", "timezone", "place_id", "notes", "enabled"}


def _fields(arguments: dict[str, Any]) -> dict[str, Any]:
    if set(arguments) - _FIELDS:
        raise FamilyRoutineError("Unsupported routine fields")
    person_id = _uuid(arguments.get("person_id"))
    label = _text(arguments.get("label"), 1, 120, "Label")
    notes = _text(arguments.get("notes", ""), 0, 1000, "Description")
    days = arguments.get("days")
    if (
        not isinstance(days, list)
        or not 1 <= len(days) <= 7
        or any(type(day) is not int or not 0 <= day <= 6 for day in days)
        or len(set(days)) != len(days)
    ):
        raise FamilyRoutineError("Select distinct weekdays from Monday (0) to Sunday (6)")
    for key in ("start", "end"):
        if not isinstance(arguments.get(key), str) or not re.fullmatch(
            r"(?:[01]\d|2[0-3]):[0-5]\d", arguments[key]
        ):
            raise FamilyRoutineError("Times must use HH:MM")
    if arguments["start"] == arguments["end"]:
        raise FamilyRoutineError("Start and end must differ; overnight windows are supported")
    timezone = _text(arguments.get("timezone"), 1, 64, "Time zone")
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise FamilyRoutineError("Use a valid IANA time zone") from None
    enabled = arguments.get("enabled", True)
    if type(enabled) is not bool:
        raise FamilyRoutineError("Enabled must be boolean")
    place_id = _uuid(arguments["place_id"]) if arguments.get("place_id") is not None else None
    return {
        "person_id": str(person_id),
        "label": label,
        "days": sorted(days),
        "start": arguments["start"],
        "end": arguments["end"],
        "timezone": timezone,
        "place_id": str(place_id) if place_id else None,
        "notes": notes,
        "enabled": enabled,
    }


def family_routine_payload(memory: MemoryRecord, graph: Any) -> dict[str, Any]:
    fields = _fields({key: value for key, value in memory.metadata.items() if key in _FIELDS})
    person = _person(graph, memory.household_id, _uuid(fields["person_id"]))
    place = _place(
        graph, memory.household_id, _uuid(fields["place_id"]) if fields["place_id"] else None
    )
    if memory.subject_id != person.canonical_id:
        raise FamilyRoutineError("Routine subject does not match its member")
    return {
        **fields,
        "routine_id": str(memory.memory_id),
        "version": str(memory.memory_id),
        "person_name": person.name,
        "place_name": place.name if place else None,
        "created_at": memory.created_at.isoformat(),
        "status": memory.status.value,
        "supersedes_routine_id": str(memory.supersedes_memory_id)
        if memory.supersedes_memory_id
        else None,
        "classification": "OWNER_DECLARED_EXPECTATION",
        "authority": "NONE",
        "provenance": {
            "kind": memory.provenance.kind.value,
            "source_ref": memory.provenance.source_ref,
        },
    }


def family_routines_page(
    memory_service: Any,
    graph: Any,
    household_id: UUID,
    *,
    person_id: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Keyset pagination AFTER scoped metadata filtering; no silent top-k omission."""
    _household(graph, household_id)
    subject = _uuid(person_id) if person_id is not None else None
    if subject:
        _person(graph, household_id, subject)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise FamilyRoutineError("Page size must be 1–100")
    after = _uuid(cursor) if cursor is not None else None
    where, params = memory_service._rows_for_filters(
        household_id=household_id,
        subject_id=subject,
        memory_types=[MemoryType.EXPLICIT_FACT],
        graph_ref=None,
        now=datetime.now(UTC),
    )
    params.update({"after": after, "limit": limit + 1})
    with memory_service._connect() as connection, connection.cursor() as sql:
        sql.execute(
            f"""SELECT m.* FROM anima_memory_records m WHERE {where}
            AND m.metadata->>'record_kind' = 'family_routine'
            AND m.provenance_kind = 'EXPLICIT_INPUT'
            AND (%(after)s::uuid IS NULL OR m.memory_id > %(after)s::uuid)
            ORDER BY m.memory_id ASC LIMIT %(limit)s""",
            params,
        )
        records = [memory_service._memory(row) for row in sql.fetchall()]
    return {
        "status": "SUCCEEDED",
        "items": [family_routine_payload(item, graph) for item in records[:limit]],
        "next_cursor": str(records[limit - 1].memory_id) if len(records) > limit else None,
    }


class FamilyRoutinesNativePlugin:
    def __init__(self, memory_service: Any, graph: Any) -> None:
        self.memory_service, self.graph = memory_service, graph

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        pass

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in FAMILY_ROUTINES_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        raise PluginValidationError("family-routines requires trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> dict[str, Any]:
        del timeout
        if name == "list_routines":
            if set(arguments) - {"person_id", "cursor", "limit"}:
                raise FamilyRoutineError("Unsupported list fields")
            return family_routines_page(
                self.memory_service, self.graph, context.household_id, **arguments
            )
        if name not in {
            "add_member",
            "create_routine",
            "update_routine",
            "disable_routine",
            "retract_routine",
        }:
            raise PluginValidationError("Unknown family-routines tool")
        if context.principal_id is None:
            raise FamilyRoutineError("A commissioned owner is required")
        principal = _person(self.graph, context.household_id, context.principal_id)
        if (
            context.origin != RequestOrigin.DIRECT_USER
            or principal.metadata.get("semantic_role") != "owner"
        ):
            raise FamilyRoutineError(
                "Only a direct request from the commissioned owner may change routines"
            )
        if name == "add_member":
            if set(arguments) != {"name"}:
                raise FamilyRoutineError("Only the member name is accepted")
            member_name = _text(arguments["name"], 1, 120, "Member name")
            if any(ord(character) < 32 or ord(character) == 127 for character in member_name):
                raise FamilyRoutineError("Member name contains unsupported control characters")
            if any(
                item.kind == NodeKind.PERSON
                and item.retired_at is None
                and normalize_alias(item.name) == normalize_alias(member_name)
                for item in self.graph.members_of_household(context.household_id)
            ):
                raise FamilyRoutineError("A member with this name already exists in this household")
            member = CanonicalNode(uuid4(), NodeKind.PERSON, member_name)
            # Existing Graph commissioning persists the plain canonical person
            # and membership together. No role, login, assurance or presence.
            self.graph.commission(
                CommissioningDocument(
                    1,
                    (self.graph.get_node(context.household_id), member),
                    (
                        CanonicalRelationship(
                            uuid4(),
                            RelationshipType.MEMBER_OF,
                            member.canonical_id,
                            context.household_id,
                        ),
                    ),
                )
            )
            saved_member = _person(self.graph, context.household_id, member.canonical_id)
            return {
                "status": "SUCCEEDED",
                "member": {"person_id": str(saved_member.canonical_id), "name": saved_member.name},
            }
        original = None
        if name != "create_routine":
            original = self.memory_service.get(_uuid(arguments.get("routine_id")))
            if (
                original is None
                or original.household_id != context.household_id
                or original.memory_type != MemoryType.EXPLICIT_FACT
                or original.provenance.kind != ProvenanceKind.EXPLICIT_INPUT
                or original.metadata.get("record_kind") != "family_routine"
            ):
                raise FamilyRoutineError("Routine does not exist in this household")
            if original.status != MemoryStatus.ACTIVE:
                raise FamilyRoutineError("Routine version changed; reload before editing")
            family_routine_payload(original, self.graph)
        if name in {"disable_routine", "retract_routine"}:
            if set(arguments) != {"routine_id"}:
                raise FamilyRoutineError("Only the current routine identifier is accepted")
            assert original is not None
            if name == "retract_routine":
                return {
                    "status": "SUCCEEDED",
                    "routine": family_routine_payload(
                        self.memory_service.retract(original.memory_id), self.graph
                    ),
                }
            fields = _fields(
                {key: value for key, value in original.metadata.items() if key in _FIELDS}
            )
            if not fields["enabled"]:
                return {
                    "status": "SUCCEEDED",
                    "routine": family_routine_payload(original, self.graph),
                }
            fields["enabled"] = False
        else:
            fields = _fields(
                {key: value for key, value in arguments.items() if key != "routine_id"}
            )
            if name == "create_routine" and "routine_id" in arguments:
                raise FamilyRoutineError("New routine identifiers are generated by Core")
        person = _person(self.graph, context.household_id, _uuid(fields["person_id"]))
        place = _place(
            self.graph,
            context.household_id,
            _uuid(fields["place_id"]) if fields["place_id"] else None,
        )
        memory = MemoryRecord.create(
            household_id=context.household_id,
            subject_id=person.canonical_id,
            memory_type=MemoryType.EXPLICIT_FACT,
            content=(
                f"Owner-declared {'enabled' if fields['enabled'] else 'disabled'} routine "
                f"expectation (not observed presence): {person.name}: {fields['label']}; "
                f"days {fields['days']}, {fields['start']}–{fields['end']} "
                f"{fields['timezone']}. {fields['notes']}"
            ),
            provenance=MemoryProvenance(
                ProvenanceKind.EXPLICIT_INPUT, f"anima:principal:{context.principal_id}"
            ),
            graph_refs=(person.canonical_id, place.canonical_id)
            if place
            else (person.canonical_id,),
            metadata={"record_kind": "family_routine", **fields},
        )
        saved = (
            self.memory_service.correct(original.memory_id, memory)
            if original
            else self.memory_service.create(memory)
        )
        return {"status": "SUCCEEDED", "routine": family_routine_payload(saved, self.graph)}


_SCHEMA = {
    "person_id": {"type": "string", "format": "uuid"},
    "label": {"type": "string", "minLength": 1, "maxLength": 120},
    "days": {
        "type": "array",
        "minItems": 1,
        "maxItems": 7,
        "uniqueItems": True,
        "items": {"type": "integer", "minimum": 0, "maximum": 6},
    },
    "start": {"type": "string", "pattern": r"^(?:[01]\d|2[0-3]):[0-5]\d$"},
    "end": {"type": "string", "pattern": r"^(?:[01]\d|2[0-3]):[0-5]\d$"},
    "timezone": {"type": "string", "minLength": 1, "maxLength": 64},
    "place_id": {"type": ["string", "null"], "format": "uuid"},
    "notes": {"type": "string", "maxLength": 1000},
    "enabled": {"type": "boolean"},
}
_ID = {"routine_id": {"type": "string", "format": "uuid"}}
_REQUIRED = ["person_id", "label", "days", "start", "end", "timezone"]
FAMILY_ROUTINES_MANIFEST = PluginManifest(
    plugin_id="anima.family-routines",
    plugin_version="1.1.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Family routines",
    description="Owner-declared expectations, never presence or authority",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.routines",),
    source="builtin:anima_ha.family_routines",
    tools=tuple(
        {
            "name": name,
            "description": description,
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
            "semantic_action": "capabilities.read"
            if name == "list_routines"
            else "capabilities.configure",
            "risk_class": "READ_ONLY" if name == "list_routines" else "SECURITY_SECURE_ACTION",
            "read_only": name == "list_routines",
            "idempotency": (
                Idempotency.IDEMPOTENT if name == "list_routines" else Idempotency.KEYED
            ).value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        }
        for name, description, properties, required in (
            (
                "add_member",
                "Add an owner-requested household member for routines; no login, role or presence",
                {"name": {"type": "string", "minLength": 1, "maxLength": 120}},
                ["name"],
            ),
            (
                "list_routines",
                "List owner-declared routine expectations, including disabled records, by page",
                {
                    "person_id": _SCHEMA["person_id"],
                    "cursor": {"type": "string", "format": "uuid"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                [],
            ),
            (
                "create_routine",
                "Record an explicit owner-requested routine, never an inferred schedule",
                _SCHEMA,
                _REQUIRED,
            ),
            (
                "update_routine",
                "Correct a current routine version with complete replacement fields",
                {**_SCHEMA, **_ID},
                ["routine_id", *_REQUIRED],
            ),
            (
                "disable_routine",
                "Disable a current routine, retaining its history",
                _ID,
                ["routine_id"],
            ),
            (
                "retract_routine",
                "Retract a current routine, retaining its history",
                _ID,
                ["routine_id"],
            ),
        )
    ),
)
