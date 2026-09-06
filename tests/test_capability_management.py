from __future__ import annotations

from typing import Any
from uuid import uuid4

from anima_ha.capability_management import (
    CAPABILITY_MANAGEMENT_MANIFEST,
    CapabilityManagementNativePlugin,
)
from anima_ha.plugins import (
    CORE_VERSION,
    MANIFEST_VERSION,
    NativeRuntime,
    PluginManager,
    PluginManifest,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService


class AllowEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {"decision": "ALLOW", "reason_code": "TEST_ALLOW", "policy_version": "test"}


class StatusPlugin:
    def start(self, secret_env: dict[str, str]) -> None:
        del secret_env

    def stop(self) -> None:
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": "status", "input_schema": {"type": "object"}}]

    def invoke(self, name: str, arguments: dict[str, Any], timeout: float) -> dict[str, str]:
        del arguments, timeout
        if name != "status":
            raise ValueError("unknown tool")
        return {"status": "ready"}


def optional_manifest() -> PluginManifest:
    return PluginManifest(
        plugin_id="anima.external.weather",
        plugin_version="1.0.0",
        manifest_version=MANIFEST_VERSION,
        requires_core=CORE_VERSION,
        name="Weather",
        description="Test optional integration",
        runtime_kind=RuntimeKind.TRUSTED_NATIVE,
        trust_class=TrustClass.TRUSTED_NATIVE,
        capabilities=("weather",),
        tools=({"name": "status", "read_only": True, "risk_class": "READ_ONLY"},),
    )


def test_management_lists_only_registered_public_optional_integrations() -> None:
    manager = PluginManager()
    manager.register(optional_manifest(), NativeRuntime(StatusPlugin()))
    management = CapabilityManagementNativePlugin(manager)
    assert [item["plugin_id"] for item in management.integrations()] == [
        "anima.external.weather"
    ]
    assert all("configuration" not in item for item in management.integrations())


def test_management_enable_disable_uses_core_policy_and_server_owned_target() -> None:
    manager = PluginManager()
    manager.register(optional_manifest(), NativeRuntime(StatusPlugin()))
    manager.register(
        CAPABILITY_MANAGEMENT_MANIFEST,
        NativeRuntime(CapabilityManagementNativePlugin(manager)),
    )
    manager.enable(CAPABILITY_MANAGEMENT_MANIFEST.plugin_id)
    identity = IdentityContext(uuid4(), None, Assurance.AUTHENTICATED)
    policy = PolicyService(AllowEvaluator())
    tool_id = "anima.capability-management.set_integration_enabled"

    disabled = manager.invoke(
        tool_id,
        {"plugin_id": "anima.external.weather", "enabled": False},
        household_id=identity.household_id,
        identity=identity,
        policy_service=policy,
    )
    assert disabled.outcome.value == "SUCCESS"
    assert disabled.result["integration"]["enabled"] is False

    enabled = manager.invoke(
        tool_id,
        {"plugin_id": "anima.external.weather", "enabled": True},
        household_id=identity.household_id,
        identity=identity,
        policy_service=policy,
    )
    assert enabled.outcome.value == "SUCCESS"
    assert enabled.result["integration"]["state"] == "HEALTHY"

