"""Typed ANIMA-owned room and zone management.

This capability changes the canonical household topology only.  It does not
edit Home Assistant configuration and never accepts household authority from
model- or browser-controlled arguments.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from anima_ha.graph import NodeKind, PostgresHouseholdGraph
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


def _space_payload(node: Any, parent_id: UUID | None = None) -> dict[str, str | None]:
    return {
        "place_id": str(node.canonical_id),
        "name": node.name,
        "kind": node.kind.value,
        "parent_id": str(parent_id) if parent_id else None,
    }


class HouseholdSpacesNativePlugin:
    def __init__(self, graph: PostgresHouseholdGraph) -> None:
        self.graph = graph

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in HOUSEHOLD_SPACES_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("household-spaces requires trusted invocation context")

    def _list_resources(
        self, arguments: dict[str, Any], context: InvocationContext
    ) -> dict[str, Any]:
        if arguments.keys() - {"place_id", "limit", "cursor"}:
            raise PluginValidationError("unknown resource lookup argument")
        limit = arguments.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= 50:
            raise PluginValidationError("limit must be an integer between 1 and 50")
        root = self.graph.get_node(context.household_id)
        if root is None or root.kind != NodeKind.HOUSEHOLD or root.retired_at is not None:
            raise PluginValidationError("household is not commissioned")
        try:
            place_id = UUID(str(arguments.get("place_id", context.household_id)))
        except ValueError as exc:
            raise PluginValidationError("invalid place_id") from exc
        if place_id != context.household_id and place_id not in {
            place.canonical_id for place in self.graph.places_in_household(context.household_id)
        }:
            raise PluginValidationError("place is not in the household")

        # Scope-bound keyset pagination remains stable when names change or earlier
        # resources disappear. The cursor is a position, never an authority grant.
        prefix = f"v1/{context.household_id}/{place_id}/"
        after = -1
        if "cursor" in arguments:
            cursor = arguments["cursor"]
            if not isinstance(cursor, str) or not cursor.startswith(prefix) or len(cursor) > 120:
                raise PluginValidationError("invalid resource cursor for this scope")
            try:
                after = UUID(cursor[len(prefix) :]).int
            except ValueError as exc:
                raise PluginValidationError("invalid resource cursor") from exc
        resources = {
            node.canonical_id: node
            for node in self.graph.resources_in_place(place_id)
            if node.retired_at is None and node.kind in {NodeKind.RESOURCE, NodeKind.SENSOR}
        }
        remaining = sorted(key for key in resources if key.int > after)
        selected = remaining[:limit]
        items = []
        for resource_id in selected:
            resource = resources[resource_id]
            capabilities = {
                node.canonical_id: node
                for node in self.graph.resource_capabilities(resource_id)
                if node.retired_at is None and node.kind == NodeKind.CAPABILITY
            }
            ordered = [capabilities[key] for key in sorted(capabilities)]
            items.append(
                {
                    "resource_id": str(resource_id),
                    "name": resource.name[:120],
                    "kind": resource.kind.value,
                    "capabilities": [
                        {
                            "capability_id": str(node.canonical_id),
                            "name": node.name[:120],
                            "type": (
                                node.metadata["capability_type"][:120]
                                if isinstance(node.metadata.get("capability_type"), str)
                                else None
                            ),
                        }
                        for node in ordered[:50]
                    ],
                    "capabilities_truncated": len(ordered) > 50,
                }
            )
        return {
            "status": "SUCCEEDED",
            "items": items,
            "next_cursor": prefix + str(selected[-1]) if len(remaining) > limit else None,
        }

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> Any:
        del timeout
        if name == "list_resources":
            return self._list_resources(arguments, context)
        if name == "list_spaces":
            root = self.graph.get_node(context.household_id)
            if root is None or root.kind != NodeKind.HOUSEHOLD:
                raise PluginValidationError("household is not commissioned")
            return {
                "status": "SUCCEEDED",
                "items": [_space_payload(root)]
                + [
                    _space_payload(
                        item, self.graph.parent_of_place(context.household_id, item.canonical_id)
                    )
                    for item in self.graph.places_in_household(context.household_id)
                ],
            }
        if name == "create_space":
            parent_id = UUID(str(arguments["parent_id"]))
            node = self.graph.create_place(
                context.household_id,
                parent_id,
                str(arguments["name"]),
                NodeKind(str(arguments["kind"])),
            )
            return {"status": "SUCCEEDED", "space": _space_payload(node, parent_id)}
        if name == "rename_space":
            place_id = UUID(str(arguments["place_id"]))
            node = self.graph.rename_place(context.household_id, place_id, str(arguments["name"]))
            return {
                "status": "SUCCEEDED",
                "space": _space_payload(
                    node, self.graph.parent_of_place(context.household_id, place_id)
                ),
            }
        if name == "move_space":
            node = self.graph.move_place(
                context.household_id,
                UUID(str(arguments["place_id"])),
                UUID(str(arguments["parent_id"])),
            )
            return {
                "status": "SUCCEEDED",
                "space": _space_payload(
                    node, self.graph.parent_of_place(context.household_id, node.canonical_id)
                ),
            }
        if name == "remove_space":
            node = self.graph.retire_place(context.household_id, UUID(str(arguments["place_id"])))
            return {"status": "SUCCEEDED", "removed": _space_payload(node)}
        raise PluginValidationError("unknown household-spaces tool")


HOUSEHOLD_SPACES_MANIFEST = PluginManifest(
    plugin_id="anima.household-spaces",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Rooms and zones",
    description="Manage bounded canonical household rooms and zones",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.topology",),
    tools=(
        {
            "name": "list_resources",
            "description": (
                "Find commissioned household resource and capability IDs for read_state. "
                "Optionally filter to a household place and descendants; follow next_cursor. "
                "At most 50 capabilities per resource; capabilities_truncated reports overflow."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string", "format": "uuid"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                    "cursor": {"type": "string", "minLength": 1, "maxLength": 120},
                },
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "items", "next_cursor"],
                "properties": {
                    "status": {"const": "SUCCEEDED"},
                    "next_cursor": {"type": ["string", "null"], "maxLength": 120},
                    "items": {
                        "type": "array",
                        "maxItems": 50,
                        "items": {
                            "type": "object",
                            "required": [
                                "resource_id",
                                "name",
                                "kind",
                                "capabilities",
                                "capabilities_truncated",
                            ],
                            "properties": {
                                "resource_id": {"type": "string", "format": "uuid"},
                                "name": {"type": "string", "maxLength": 120},
                                "kind": {"enum": ["RESOURCE", "SENSOR"]},
                                "capabilities_truncated": {"type": "boolean"},
                                "capabilities": {
                                    "type": "array",
                                    "maxItems": 50,
                                    "items": {
                                        "type": "object",
                                        "required": ["capability_id", "name", "type"],
                                        # Keep within the existing depth-eight schema
                                        # boundary; values are bounded by the projector.
                                        "maxProperties": 3,
                                    },
                                },
                            },
                            "additionalProperties": False,
                        },
                    },
                },
                "additionalProperties": False,
            },
            "semantic_action": "capabilities.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "list_spaces",
            "description": "List the household rooms and zones",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "output_schema": {
                "type": "object",
                "required": ["status", "items"],
                "properties": {"status": {"const": "SUCCEEDED"}, "items": {"type": "array"}},
                "additionalProperties": False,
            },
            "semantic_action": "capabilities.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "create_space",
            "description": "Create one room or zone inside the household graph",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "kind": {"type": "string", "enum": ["ROOM", "ZONE"]},
                    "parent_id": {"type": "string", "format": "uuid"},
                },
                "required": ["name", "kind", "parent_id"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "space"]},
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "rename_space",
            "description": "Rename one room or zone in the household graph",
            "input_schema": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                },
                "required": ["place_id", "name"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "space"]},
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "move_space",
            "description": "Move one room or zone to another household container",
            "input_schema": {
                "type": "object",
                "properties": {
                    "place_id": {"type": "string", "format": "uuid"},
                    "parent_id": {"type": "string", "format": "uuid"},
                },
                "required": ["place_id", "parent_id"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "space"]},
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "remove_space",
            "description": "Remove an empty room or zone from the canonical household map",
            "input_schema": {
                "type": "object",
                "properties": {"place_id": {"type": "string", "format": "uuid"}},
                "required": ["place_id"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "removed"]},
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
    ),
    source="builtin:anima_ha.household_spaces",
)
