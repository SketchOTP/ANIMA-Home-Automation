"""Typed household-user management for the ANIMA management plane.

This is a canonical Graph projection, not a Home Assistant admin surface. It
stores bounded access/presence/profile metadata on a household PERSON node;
camera enrollment remains a separate SENTRY capture workflow.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from anima_ha.graph import PostgresHouseholdGraph
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


def user_payload(node: Any) -> dict[str, Any]:
    metadata = node.metadata
    return {
        "person_id": str(node.canonical_id),
        "name": node.name,
        "role": metadata.get("semantic_role", "member"),
        "access_level": metadata.get("sentry_access", "LIMITED"),
        "sentry_profile_id": metadata.get("sentry_profile_id"),
        "sentry_onboarding_state": metadata.get("sentry_onboarding_state", "NOT_STARTED"),
        "wifi_macs": list(metadata.get("wifi_macs", [])),
    }


class HouseholdUsersNativePlugin:
    def __init__(self, graph: PostgresHouseholdGraph) -> None:
        self.graph = graph

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in HOUSEHOLD_USERS_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del name, arguments, timeout
        raise PluginValidationError("household-users requires trusted invocation context")

    def invoke_with_invocation_context(
        self, name: str, arguments: dict[str, Any], timeout: float, context: InvocationContext
    ) -> dict[str, Any]:
        del timeout
        allowed = {
            "person_id", "name", "role", "access_level", "wifi_macs",
            "sentry_profile_id", "onboarding_state",
        }
        if set(arguments) - allowed:
            raise PluginValidationError("unknown household-user argument")
        if name == "list_users":
            return {
                "status": "SUCCEEDED",
                "items": [
                    user_payload(person)
                    for person in self.graph.members_of_household(context.household_id)
                ],
            }
        if name == "create_user":
            person = self.graph.create_person(
                context.household_id,
                str(arguments.get("name", "")),
                semantic_role=str(arguments.get("role", "member")),
                access_level=str(arguments.get("access_level", "LIMITED")),
                wifi_macs=arguments.get("wifi_macs", []),
            )
            return {"status": "SUCCEEDED", "user": user_payload(person)}
        if name == "update_user":
            try:
                person_id = UUID(str(arguments["person_id"]))
            except (KeyError, ValueError) as exc:
                raise PluginValidationError("person_id must be a UUID") from exc
            person = self.graph.update_person_profile(
                context.household_id,
                person_id,
                name=str(arguments["name"]) if "name" in arguments else None,
                semantic_role=str(arguments["role"]) if "role" in arguments else None,
                access_level=(
                    str(arguments["access_level"])
                    if "access_level" in arguments
                    else None
                ),
                wifi_macs=arguments.get("wifi_macs"),
                sentry_profile_id=(
                    str(arguments["sentry_profile_id"])
                    if "sentry_profile_id" in arguments
                    else None
                ),
                onboarding_state=(
                    str(arguments["onboarding_state"])
                    if "onboarding_state" in arguments
                    else None
                ),
            )
            return {"status": "SUCCEEDED", "user": user_payload(person)}
        raise PluginValidationError("unknown household-users tool")


HOUSEHOLD_USERS_MANIFEST = PluginManifest(
    plugin_id="anima.household-users",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Household users",
    description="Manage canonical household people, SENTRY access, and bounded device associations",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("household.identity",),
    tools=(
        {
            "name": "list_users",
            "description": "List canonical household users and bounded SENTRY/presence metadata",
            "input_schema": {"type": "object", "additionalProperties": False},
            "output_schema": {"type": "object", "required": ["status", "items"]},
            "semantic_action": "identity.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": Idempotency.IDEMPOTENT.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "create_user",
            "description": "Create a household user pending camera identity enrollment",
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "role": {"type": "string", "enum": ["member", "guest"]},
                    "access_level": {"type": "string", "enum": ["UNRESTRICTED", "LIMITED"]},
                    "wifi_macs": {
                        "type": "array", "maxItems": 8,
                        "items": {"type": "string", "maxLength": 17},
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "user"]},
            "semantic_action": "identity.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
        {
            "name": "update_user",
            "description": (
                "Update bounded household-user permissions, profile state, or "
                "Wi-Fi associations"
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "person_id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 120},
                    "role": {"type": "string", "enum": ["owner", "member", "guest"]},
                    "access_level": {"type": "string", "enum": ["UNRESTRICTED", "LIMITED"]},
                    "wifi_macs": {
                        "type": "array", "maxItems": 8,
                        "items": {"type": "string", "maxLength": 17},
                    },
                    "sentry_profile_id": {"type": "string", "maxLength": 128},
                    "onboarding_state": {
                        "type": "string",
                        "enum": ["NOT_STARTED", "PENDING_CAMERA_PROFILE", "ACTIVE", "REVOKED"],
                    },
                },
                "required": ["person_id"],
                "additionalProperties": False,
            },
            "output_schema": {"type": "object", "required": ["status", "user"]},
            "semantic_action": "identity.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": Idempotency.KEYED.value,
            "external_content_trust": ExternalContentTrust.LOCAL_TRUSTED.value,
        },
    ),
    source="builtin:anima_ha.users",
)
