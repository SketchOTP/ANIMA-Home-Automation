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


def _space_payload(node: Any) -> dict[str, str]:
    return {"place_id": str(node.canonical_id), "name": node.name, "kind": node.kind.value}


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

    def invoke_with_invocation_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        context: InvocationContext,
    ) -> Any:
        del timeout
        if name == "list_spaces":
            root = self.graph.get_node(context.household_id)
            if root is None or root.kind != NodeKind.HOUSEHOLD:
                raise PluginValidationError("household is not commissioned")
            return {
                "status": "SUCCEEDED",
                "items": [_space_payload(root)]
                + [
                    _space_payload(item)
                    for item in self.graph.places_in_household(context.household_id)
                ],
            }
        if name == "create_space":
            node = self.graph.create_place(
                context.household_id,
                UUID(str(arguments["parent_id"])),
                str(arguments["name"]),
                NodeKind(str(arguments["kind"])),
            )
            return {"status": "SUCCEEDED", "space": _space_payload(node)}
        if name == "rename_space":
            node = self.graph.rename_place(
                context.household_id, UUID(str(arguments["place_id"])), str(arguments["name"])
            )
            return {"status": "SUCCEEDED", "space": _space_payload(node)}
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
    ),
    source="builtin:anima_ha.household_spaces",
)
