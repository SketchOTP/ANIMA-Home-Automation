"""Exercise a real out-of-process MCP plugin and its failure isolation.

The target uses the production PluginManager and McpRuntime against a small
test-only stdio MCP process. It proves that a disabled/re-enabled plugin gets
a fresh process and that a failing process removes only its own tools while an
unrelated plugin remains healthy. Durable evidence is limited to plugin
identity, lifecycle, and process metadata.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg

from anima_ha.db.migrate import migrate
from anima_ha.journal import PostgresEventJournal
from anima_ha.plugins import (
    CORE_VERSION,
    McpRuntime,
    PluginManager,
    PluginManifest,
    PluginState,
    PostgresPluginStore,
    RuntimeKind,
    TrustClass,
)
from anima_ha.policy import Assurance, IdentityContext, PolicyService

DATABASE_URL = os.environ.get("ANIMA_DATABASE_URL", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ID = uuid4()
HOUSEHOLD_ID = UUID("ecbd0d84-6f5f-40f8-928f-1d5dfe758dd7")


class ReadOnlyPolicy:
    def evaluate(self, document: dict[str, Any]) -> dict[str, Any]:
        del document
        return {
            "decision": "ALLOW",
            "reason_code": "READ_ONLY_ALLOWED",
            "policy_version": "phase14-plugin-process",
        }


def manifest(plugin_id: str, name: str) -> PluginManifest:
    return PluginManifest(
        plugin_id=plugin_id,
        plugin_version="1.0.0",
        manifest_version=1,
        requires_core=CORE_VERSION,
        name=name,
        description="Phase 14 out-of-process MCP fixture",
        runtime_kind=RuntimeKind.MCP_STDIO,
        trust_class=TrustClass.OPTIONAL_EXTERNAL,
        capabilities=("phase14.process",),
        tools=(
            {
                "name": "process_probe",
                "description": "Return a bounded process identity probe",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string", "maxLength": 64}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                "read_only": True,
                "risk_class": "READ_ONLY",
                "semantic_action": "query_plugin",
                "idempotency": "IDEMPOTENT",
                "external_content_trust": "PLUGIN_TRUSTED",
            },
        ),
        source="fixture:phase14-mcp-process",
    )


def probe(manager: PluginManager, tool_id: str, value: str) -> tuple[str, str]:
    result = manager.invoke(
        tool_id,
        {"value": value},
        household_id=HOUSEHOLD_ID,
        identity=IdentityContext(HOUSEHOLD_ID, None, Assurance.ANONYMOUS),
        policy_service=PolicyService(ReadOnlyPolicy()),
    )
    if result.outcome.value != "SUCCESS":
        raise AssertionError(f"MCP process probe failed: {result}")
    content = result.result.get("content", []) if isinstance(result.result, dict) else []
    if not content or not isinstance(content[0], str):
        raise AssertionError(f"MCP process response was not bounded text: {result.result!r}")
    raw = content[0]
    prefix, returned_value = raw.split(";value=", 1)
    pid = prefix.removeprefix("pid=")
    if not pid.isdigit() or returned_value != value:
        raise AssertionError(f"unexpected process probe: {raw!r}")
    return pid, raw


def scalar(query: str, *args: object) -> int:
    with psycopg.connect(DATABASE_URL) as connection, connection.cursor() as cursor:
        cursor.execute(query, args)
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def main() -> int:
    if not DATABASE_URL:
        raise RuntimeError("ANIMA_DATABASE_URL is required")
    migrate(DATABASE_URL, 5)
    journal = PostgresEventJournal(DATABASE_URL)
    manager = PluginManager(journal=journal, store=PostgresPluginStore(DATABASE_URL))

    healthy_id = f"anima.phase14.mcp.process.{RUN_ID}"
    failed_id = f"anima.phase14.mcp.failed.{RUN_ID}"
    healthy_runtime = McpRuntime(
        RuntimeKind.MCP_STDIO,
        command=sys.executable,
        args=["scripts/phase14_mcp_process_fixture.py"],
        cwd=ROOT,
    )
    failed_runtime = McpRuntime(
        RuntimeKind.MCP_STDIO,
        command=sys.executable,
        args=["-c", "import sys; sys.exit(17)"],
        cwd=ROOT,
    )
    manager.register(manifest(healthy_id, "Phase 14 process fixture"), healthy_runtime)
    manager.register(manifest(failed_id, "Phase 14 failed process fixture"), failed_runtime)

    healthy = manager.enable(healthy_id)
    if healthy.state != PluginState.HEALTHY:
        raise AssertionError(f"healthy MCP plugin did not start: {healthy}")
    first_pid, first_probe = probe(manager, f"{healthy_id}.process_probe", "first")
    manager.disable(healthy_id)
    if manager.list_tools(plugin_id=healthy_id):
        raise AssertionError("disabled MCP plugin left tools registered")
    healthy = manager.enable(healthy_id)
    if healthy.state != PluginState.HEALTHY:
        raise AssertionError("MCP plugin did not re-enable")
    second_pid, second_probe = probe(manager, f"{healthy_id}.process_probe", "second")
    if first_pid == second_pid:
        raise AssertionError("re-enable did not exercise a fresh MCP process")

    failed = manager.enable(failed_id)
    if failed.state != PluginState.FAILED or manager.list_tools(plugin_id=failed_id):
        raise AssertionError("failed MCP process was not isolated and disabled")
    if manager.plugins[healthy_id].state != PluginState.HEALTHY:
        raise AssertionError("failed MCP process affected healthy plugin")
    failed_audits = scalar(
        "SELECT count(*) FROM anima_event_journal WHERE source=%s AND event_type=%s "
        "AND subject_key=%s",
        "anima.plugins",
        "plugin.failed",
        f"plugin/{failed_id}",
    )
    if failed_audits < 1:
        raise AssertionError("failed MCP process did not create a durable audit")

    healthy_state_after_failure = manager.plugins[healthy_id].state.value
    manager.disable(healthy_id)
    print(
        json.dumps(
            {
                "scenario_id": "PLUGIN_PROCESS_RESTART_AND_FAILURE_ISOLATION",
                "status": "PASS",
                "evidence_level": "POSTGRES_MCP_PROCESS",
                "healthy_plugin": healthy_id,
                "failed_plugin": failed_id,
                "first_process": first_pid,
                "second_process": second_pid,
                "process_replaced": True,
                "first_probe": first_probe,
                "second_probe": second_probe,
                "failed_plugin_state": failed.state.value,
                "healthy_plugin_state_after_failure": healthy_state_after_failure,
                "failed_plugin_audits": failed_audits,
                "phase15": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
