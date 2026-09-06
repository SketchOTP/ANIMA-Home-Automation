"""Core-owned, bounded integration lifecycle management.

This is intentionally smaller than an administrator backdoor.  The browser
and SENTRY may request only enable/disable for integrations that Core has
already registered in its composition root.  Credentials, hosts,
configuration, and arbitrary plugin IDs never come from the caller.
"""

from __future__ import annotations

from typing import Any

from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    PluginManager,
    PluginManifest,
    PluginState,
    RuntimeKind,
    TrustClass,
)

MANAGEABLE_INTEGRATIONS = frozenset(
    {
        "anima.external.weather",
        "anima.external.discovery",
        "anima.external.shopping.upcitemdb",
        "anima.external.recipes",
        "anima.external.notifications",
        "anima.provider.home-assistant",
    }
)


def _public_plugin(plugin: Any) -> dict[str, Any]:
    """Return health and identity only; never expose configuration or errors."""
    state = plugin.state.value if isinstance(plugin.state, PluginState) else str(plugin.state)
    result: dict[str, Any] = {
        "plugin_id": plugin.manifest.plugin_id,
        "name": plugin.manifest.name,
        "description": plugin.manifest.description,
        "state": state,
        "enabled": bool(plugin.enabled),
        "capabilities": list(plugin.manifest.capabilities),
        "manageable": plugin.manifest.plugin_id in MANAGEABLE_INTEGRATIONS,
        "error": "integration_failed" if state in {"FAILED", "INCOMPATIBLE"} else None,
    }
    # The HA adapter owns its endpoint and credentials.  Only its bounded
    # operational status is projected to the owner-facing management plane.
    runtime = getattr(plugin, "runtime", None)
    native = getattr(runtime, "plugin", None)
    safe_status = getattr(native, "safe_status", None)
    if callable(safe_status) and plugin.manifest.plugin_id == "anima.provider.home-assistant":
        status = dict(safe_status())
        result["health"] = {
            key: status[key]
            for key in (
                "health",
                "connected_version",
                "last_successful_state_sync",
                "last_received_event",
                "subscriptions_active",
                "discovered_counts",
                "mapped_count",
                "unmapped_count",
                "reconnect_attempt",
                "last_error_category",
            )
            if key in status
        }
    return result


class CapabilityManagementNativePlugin:
    """Implement typed integration-management and recovery operations."""

    def __init__(self, manager: PluginManager) -> None:
        self.manager = manager

    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [dict(item) for item in CAPABILITY_MANAGEMENT_MANIFEST.tools]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> Any:
        del timeout
        if name == "list_integrations":
            return {"status": "SUCCEEDED", "items": self.integrations()}
        if name != "set_integration_enabled":
            raise ValueError("unknown capability-management tool")
        plugin_id = str(arguments["plugin_id"])
        if plugin_id not in MANAGEABLE_INTEGRATIONS:
            raise ValueError("integration is not Core-manageable")
        if plugin_id not in self.manager.plugins:
            return {
                "status": "UNAVAILABLE",
                "plugin_id": plugin_id,
                "reason": "integration_not_registered",
                "integration": {
                    "plugin_id": plugin_id,
                    "name": plugin_id,
                    "description": "Not registered by the current Core composition",
                    "state": "UNAVAILABLE",
                    "enabled": False,
                    "capabilities": [],
                    "manageable": True,
                    "error": "integration_not_registered",
                },
            }
        enabled = bool(arguments["enabled"])
        plugin = self.manager.enable(plugin_id) if enabled else self.manager.disable(plugin_id)
        return {
            "status": "SUCCEEDED" if plugin.enabled == enabled else "FAILED",
            "plugin_id": plugin_id,
            "integration": _public_plugin(plugin),
        }

    def integrations(self) -> list[dict[str, Any]]:
        return sorted(
            (
                _public_plugin(plugin)
                for plugin in self.manager.list_plugins()
                if plugin.manifest.plugin_id in MANAGEABLE_INTEGRATIONS
            ),
            key=lambda item: str(item["plugin_id"]),
        )


CAPABILITY_MANAGEMENT_MANIFEST = PluginManifest(
    plugin_id="anima.capability-management",
    plugin_version="1.0.0",
    manifest_version=MANIFEST_VERSION,
    requires_core=CORE_VERSION,
    name="Integration management",
    description="Manage registered ANIMA integrations through typed Core operations",
    runtime_kind=RuntimeKind.TRUSTED_NATIVE,
    trust_class=TrustClass.TRUSTED_NATIVE,
    capabilities=("capability.management",),
    tools=(
        {
            "name": "list_integrations",
            "description": "List registered integrations and bounded health state",
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "items"],
                "properties": {
                    "status": {"const": "SUCCEEDED"},
                    "items": {"type": "array"},
                },
                "additionalProperties": False,
            },
            "semantic_action": "capabilities.read",
            "risk_class": "READ_ONLY",
            "read_only": True,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "LOCAL_TRUSTED",
        },
        {
            "name": "set_integration_enabled",
            "description": "Enable or disable one Core-registered optional integration",
            "input_schema": {
                "type": "object",
                "properties": {
                    "plugin_id": {"type": "string", "enum": sorted(MANAGEABLE_INTEGRATIONS)},
                    "enabled": {"type": "boolean"},
                },
                "required": ["plugin_id", "enabled"],
                "additionalProperties": False,
            },
            "output_schema": {
                "type": "object",
                "required": ["status", "plugin_id", "integration"],
                "properties": {
                    "status": {"enum": ["SUCCEEDED", "FAILED", "UNAVAILABLE"]},
                    "plugin_id": {"type": "string"},
                    "integration": {"type": "object"},
                },
                "additionalProperties": False,
            },
            "semantic_action": "capabilities.configure",
            "risk_class": "SECURITY_SECURE_ACTION",
            "read_only": False,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "LOCAL_TRUSTED",
        },
    ),
    source="builtin:anima_ha.capability_management",
)


def integration_items(manager: PluginManager) -> list[dict[str, Any]]:
    """Project the same bounded list used by the management tool."""
    return CapabilityManagementNativePlugin(manager).integrations()
