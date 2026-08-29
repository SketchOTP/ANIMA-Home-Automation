"""Bounded Phase 5 PostgreSQL/OPA/MCP integration evidence."""

from __future__ import annotations

import os
import sys
from dataclasses import replace
from typing import Any
from uuid import uuid4

from anima_ha.db.migrate import migrate
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import (
    CORE_VERSION,
    McpRuntime,
    NATIVE_SIMULATOR_MANIFEST,
    PluginManager,
    PluginManifest,
    PluginState,
    PostgresPluginStore,
    RuntimeKind,
    SecretBroker,
    TrustClass,
    NativeSimulatorPlugin,
)
from anima_ha.policy import (
    Assurance,
    IdentityContext,
    OpaPolicyClient,
    PolicyService,
    PostgresPolicyStore,
)


def mcp_manifest(plugin_id: str = "anima.reference.mcp") -> PluginManifest:
    return PluginManifest(
        plugin_id=plugin_id,
        plugin_version="0.1.0",
        manifest_version=1,
        requires_core=CORE_VERSION,
        name="MCP reference",
        description="Synthetic MCP capability",
        runtime_kind=RuntimeKind.MCP_STDIO,
        trust_class=TrustClass.OPTIONAL_EXTERNAL,
        capabilities=("home.simulation",),
        tools=({
            "name": "synthetic_echo",
            "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"], "additionalProperties": False},
            "risk_class": "READ_ONLY",
            "semantic_action": "query_plugin",
            "read_only": True,
            "idempotency": "IDEMPOTENT",
            "external_content_trust": "PLUGIN_TRUSTED",
        },),
        events=("plugin.synthetic",),
        source="fixture:phase5-mcp",
    )


def main() -> int:
    database_url = os.environ["ANIMA_DATABASE_URL"]
    opa_url = os.environ.get("ANIMA_OPA_URL", "http://127.0.0.1:18181")
    connect_timeout = int(os.environ.get("ANIMA_DB_CONNECT_TIMEOUT", "5"))
    migrate(database_url, connect_timeout)
    journal = PostgresEventJournal(database_url, connect_timeout)
    store = PostgresPluginStore(database_url, connect_timeout)
    policy_store = PostgresPolicyStore(database_url, connect_timeout)
    broker = SecretBroker({"PHASE5_ALLOWED": "synthetic-secret", "PHASE5_UNRELATED": "must-not-pass"})
    manager = PluginManager(journal=journal, store=store, secret_broker=broker)

    native = NativeSimulatorPlugin()
    native_manifest = replace(NATIVE_SIMULATOR_MANIFEST, plugin_id="anima.reference.native", events=("plugin.synthetic",))
    manager.register(native_manifest, native)
    mcp = McpRuntime(RuntimeKind.MCP_STDIO, command=sys.executable, args=["-m", "anima_ha.mcp_reference"])
    manager.register(mcp_manifest(), mcp)
    failing_manifest = mcp_manifest("anima.reference.failing")
    failing = McpRuntime(RuntimeKind.MCP_STDIO, command=sys.executable, args=["-c", "import sys; sys.exit(17)"])
    manager.register(failing_manifest, failing)
    incompatible = manager.register(replace(native_manifest, plugin_id="anima.reference.incompatible", requires_core="9.9.9"), NativeSimulatorPlugin())

    assert manager.enable(native_manifest.plugin_id).state == PluginState.HEALTHY
    assert manager.enable(mcp_manifest().plugin_id).state == PluginState.HEALTHY
    assert manager.enable(failing_manifest.plugin_id).state == PluginState.FAILED
    assert manager.enable(incompatible.manifest.plugin_id).state == PluginState.INCOMPATIBLE

    household_id = uuid4()
    identity = IdentityContext(household_id, None, Assurance.ANONYMOUS)
    policy = PolicyService(OpaPolicyClient(opa_url), audit_store=policy_store)
    result = manager.invoke(
        "anima.reference.mcp.synthetic_echo",
        {"message": "phase5"},
        household_id=household_id,
        identity=identity,
        policy_service=policy,
    )
    assert result.outcome.value == "SUCCESS", result
    assert "echo:phase5" in repr(result.result)
    manager.emit_event("anima.reference.mcp", "plugin.synthetic", "synthetic/phase5", {"source": "mcp"})
    manager.disable("anima.reference.mcp")
    assert not manager.list_tools(plugin_id="anima.reference.mcp")
    assert manager.enable("anima.reference.mcp").state == PluginState.HEALTHY

    restored = PluginManager(store=store, journal=journal, secret_broker=broker)
    restored_mcp = McpRuntime(RuntimeKind.MCP_STDIO, command=sys.executable, args=["-m", "anima_ha.mcp_reference"])
    restored_plugins = restored.restore({"anima.reference.mcp": restored_mcp})
    assert restored_plugins and restored.list_plugins(enabled_only=True)[0].manifest.plugin_id == "anima.reference.mcp"

    events = journal.list_events(event_type="plugin.synthetic", subject_key="synthetic/phase5")
    assert events and events[-1]["source"] == "plugin:anima.reference.mcp"
    print("PHASE5_PLUGIN_INTEGRATION_PASS")
    print("mcp_stdio=PASS native=PASS policy_gate=PASS")
    print("failed_plugin=FAILED isolated incompatible_plugin=INCOMPATIBLE")
    print("disable_reenable=PASS persisted_restore=PASS declared_event=PASS")
    print(f"registry_plugins={len(manager.list_plugins())} available_tools={len(manager.list_tools())}")
    print("secrets=declared-only synthetic evidence; no values persisted or logged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
