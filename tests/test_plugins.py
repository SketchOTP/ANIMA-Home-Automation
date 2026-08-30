from __future__ import annotations

import sys
from dataclasses import replace
from typing import Any
from uuid import uuid4

import pytest

from anima_ha.plugins import (
    CORE_VERSION,
    ENTRY_POINT_GROUP,
    ExternalContentTrust,
    InvocationOutcome,
    McpRuntime,
    PluginManager,
    PluginManifest,
    PluginState,
    PluginValidationError,
    ProviderExecutionContext,
    RuntimeKind,
    SecretBroker,
    TrustClass,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService


class AllowEvaluator:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        return {"decision": "ALLOW", "reason_code": "READ_ONLY_ALLOWED", "policy_version": "test"}


class EchoNative:
    def __init__(self) -> None:
        self.secret_env: dict[str, str] = {}
        self.execution_contexts: list[ProviderExecutionContext | None] = []

    def start(self, secret_env: dict[str, str]) -> None:
        self.secret_env = dict(secret_env)

    def stop(self) -> None:
        self.secret_env = {}

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "read",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
            }
        ]

    def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext | None = None,
    ) -> Any:
        self.execution_contexts.append(execution_context)
        if name != "read":
            raise PluginValidationError("unknown native tool")
        return {"value": arguments["value"]}

    def invoke_with_context(
        self,
        name: str,
        arguments: dict[str, Any],
        timeout: float,
        execution_context: ProviderExecutionContext,
    ) -> Any:
        return self.invoke(name, arguments, timeout, execution_context)


def manifest(
    plugin_id: str = "anima.test.native",
    *,
    runtime: RuntimeKind = RuntimeKind.TRUSTED_NATIVE,
    required_secrets: tuple[str, ...] = (),
    events: tuple[str, ...] = (),
    risk_class: str = "READ_ONLY",
) -> PluginManifest:
    trust = (
        TrustClass.TRUSTED_NATIVE
        if runtime == RuntimeKind.TRUSTED_NATIVE
        else TrustClass.OPTIONAL_EXTERNAL
    )
    return PluginManifest(
        plugin_id=plugin_id,
        plugin_version="0.1.0",
        manifest_version=1,
        requires_core=CORE_VERSION,
        name="test plugin",
        description="test plugin",
        runtime_kind=runtime,
        trust_class=trust,
        capabilities=("test",),
        tools=(
            {
                "name": "read",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                "risk_class": risk_class,
                "semantic_action": "query_plugin",
                "read_only": True,
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "LOCAL_TRUSTED",
            },
        ),
        events=events,
        required_secrets=required_secrets,
        configuration_schema={
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "additionalProperties": False,
        },
    )


def test_manifest_bounds_and_unknown_versions_fail_closed() -> None:
    with pytest.raises(PluginValidationError):
        PluginManifest.from_dict({"plugin_id": "anima.bad"})
    with pytest.raises(PluginValidationError):
        PluginManifest(
            plugin_id="anima.bad",
            plugin_version="1",
            manifest_version=1,
            requires_core=CORE_VERSION,
            name="bad",
            description="bad",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("test",),
            tools=({"name": "bad", "input_schema": {"$ref": "https://example.invalid/schema"}},),
        )


def test_entry_point_discovery_is_separate_from_enablement() -> None:
    manager = PluginManager()
    discovered = manager.discover_native()
    assert ENTRY_POINT_GROUP == "anima_ha.plugins"
    assert any(item.plugin_id == "anima.reference.native-simulator" for item in discovered)
    assert manager.list_plugins() == []


def test_native_lifecycle_policy_gate_and_disable() -> None:
    manager = PluginManager()
    native = EchoNative()
    plugin = manager.register(manifest(), native)
    assert plugin.state == PluginState.REGISTERED
    assert manager.enable(plugin.manifest.plugin_id).state == PluginState.HEALTHY
    identity = IdentityContext(uuid4(), None, Assurance.ANONYMOUS)
    tool_id = "anima.test.native.read"
    result = manager.invoke(
        tool_id, {"value": "x"}, household_id=identity.household_id, identity=identity
    )
    assert result.outcome == InvocationOutcome.POLICY_DENIED
    result = manager.invoke(
        tool_id,
        {"value": "x"},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert result.outcome == InvocationOutcome.SUCCESS
    context = ProviderExecutionContext(uuid4(), "anima-local-key", "provider-key")
    result = manager.invoke(
        tool_id,
        {"value": "y"},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
        execution_context=context,
    )
    assert result.outcome == InvocationOutcome.SUCCESS
    assert native.execution_contexts[-1] == context
    manager.disable(plugin.manifest.plugin_id)
    assert manager.list_tools() == []


def test_secret_scope_and_declared_event_ingress() -> None:
    class Journal:
        def __init__(self) -> None:
            self.events: list[Any] = []

        def append(self, event: Any) -> None:
            self.events.append(event)

    journal = Journal()
    manager = PluginManager(
        journal=journal,
        secret_broker=SecretBroker(
            {"TEST_ALLOWED": "redacted-value", "TEST_UNRELATED": "should-not-pass"}
        ),
    )
    plugin = EchoNative()
    manager.register(
        manifest(required_secrets=("TEST_ALLOWED",), events=("plugin.synthetic",)), plugin
    )
    manager.enable("anima.test.native")
    assert plugin.secret_env == {"TEST_ALLOWED": "redacted-value"}
    manager.emit_event("anima.test.native", "plugin.synthetic", "synthetic/subject", {"ok": True})
    assert journal.events[-1].source == "plugin:anima.test.native"
    assert "redacted-value" not in repr(journal.events)


def test_mcp_stdio_reference_is_out_of_process_and_normalized() -> None:
    runtime = McpRuntime(
        RuntimeKind.MCP_STDIO, command=sys.executable, args=["-m", "anima_ha.mcp_reference"]
    )
    manager = PluginManager()
    plugin = manager.register(
        PluginManifest(
            plugin_id="anima.test.mcp",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core=CORE_VERSION,
            name="mcp",
            description="mcp",
            runtime_kind=RuntimeKind.MCP_STDIO,
            trust_class=TrustClass.OPTIONAL_EXTERNAL,
            capabilities=("test",),
            tools=(
                {
                    "name": "synthetic_echo",
                    "input_schema": {
                        "type": "object",
                        "properties": {"message": {"type": "string"}},
                        "required": ["message"],
                        "additionalProperties": False,
                    },
                    "risk_class": "READ_ONLY",
                    "semantic_action": "query_plugin",
                    "read_only": True,
                    "idempotency": "IDEMPOTENT",
                    "external_content_trust": "PLUGIN_TRUSTED",
                },
            ),
        ),
        runtime,
    )
    assert manager.enable(plugin.manifest.plugin_id).state == PluginState.HEALTHY
    identity = IdentityContext(uuid4(), None, Assurance.ANONYMOUS)
    result = manager.invoke(
        "anima.test.mcp.synthetic_echo",
        {"message": "hello"},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert result.outcome == InvocationOutcome.SUCCESS
    assert result.external_content_trust == ExternalContentTrust.PLUGIN_TRUSTED


def test_failure_and_timeout_are_contained() -> None:
    class Failing(EchoNative):
        def list_tools(self) -> list[dict[str, Any]]:
            raise RuntimeError("startup crash")

    class Hanging(EchoNative):
        def invoke(
            self,
            name: str,
            arguments: dict[str, Any],
            timeout: float,
            execution_context: ProviderExecutionContext | None = None,
        ) -> Any:
            raise TimeoutError("bounded timeout")

    manager = PluginManager()
    failed = manager.register(manifest("anima.test.failed"), Failing())
    assert manager.enable(failed.manifest.plugin_id).state == PluginState.FAILED
    hanging = manager.register(manifest("anima.test.hanging"), Hanging())
    manager.enable(hanging.manifest.plugin_id)
    identity = IdentityContext(uuid4(), None, Assurance.ANONYMOUS)
    result = manager.invoke(
        "anima.test.hanging.read",
        {"value": "x"},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert result.outcome == InvocationOutcome.PLUGIN_TIMEOUT


def test_incompatible_plugins_and_invalid_results_fail_closed() -> None:
    manager = PluginManager()
    incompatible = manager.register(
        PluginManifest(
            plugin_id="anima.test.incompatible",
            plugin_version="0.1.0",
            manifest_version=1,
            requires_core="9.9.9",
            name="bad",
            description="bad",
            runtime_kind=RuntimeKind.TRUSTED_NATIVE,
            trust_class=TrustClass.TRUSTED_NATIVE,
            capabilities=("test",),
            tools=manifest().tools,
        ),
        EchoNative(),
    )
    assert manager.enable(incompatible.manifest.plugin_id).state == PluginState.INCOMPATIBLE

    bad_manifest = manifest("anima.test.bad-result")
    bad_manifest = replace(
        bad_manifest,
        tools=(
            {**bad_manifest.tools[0], "output_schema": {"type": "object", "required": ["status"]}},
        ),
    )
    manager.register(bad_manifest, EchoNative())
    manager.enable(bad_manifest.plugin_id)
    identity = IdentityContext(uuid4(), None, Assurance.ANONYMOUS)
    result = manager.invoke(
        "anima.test.bad-result.read",
        {"value": "x"},
        household_id=identity.household_id,
        identity=identity,
        policy_service=PolicyService(AllowEvaluator()),
    )
    assert result.outcome == InvocationOutcome.INVALID_RESULT
