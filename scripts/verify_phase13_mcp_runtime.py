"""Exercise the ANIMA household bundle through the installed MCP runtime.

The service below is a local deterministic contract fixture.  It is deliberately
not ANIMA Core: the purpose is to prove the client-only bundle, stdio transport,
schemas, binding flow, and request lifecycle without requiring household
credentials or a production database.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "integrations/sentry/anima-household"
LAUNCHER = PLUGIN / "scripts/launch_anima_household_mcp"
TOKEN = "runtime-certification-token-" + "x" * 32
HOUSEHOLD = "00000000-0000-0000-0000-000000000012"
DIRECT_REQUEST = "00000000-0000-0000-0000-000000000101"
QUEUED_REQUEST = "00000000-0000-0000-0000-000000000102"


class FixtureState:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def record(self, path: str, payload: dict[str, Any]) -> None:
        with self.lock:
            self.paths.append(path)
            self.payloads.append(payload)


class FixtureHandler(BaseHTTPRequestHandler):
    server: FixtureServer

    def _json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict):
            raise ValueError("fixture request is not an object")
        return value

    def _write(self, value: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._write({"error": "unauthorized"}, 401)
            return
        payload = self._json()
        self.server.state.record(self.path, payload)
        if self.path == "/v1/health":
            self._write(
                {
                    "status": "available",
                    "provider_id": "sentry",
                    "household_id": HOUSEHOLD,
                }
            )
            return
        if self.path == "/v1/interactions/direct":
            self._write(
                {
                    "status": "CLAIMED",
                    "request_id": DIRECT_REQUEST,
                    "household_id": HOUSEHOLD,
                    "origin": "DIRECT_SENTRY_INTERACTION",
                    "binding": "binding-direct",
                }
            )
            return
        if self.path == "/v1/interactions/open":
            self._write(
                {
                    "status": "CLAIMED",
                    "request_id": QUEUED_REQUEST,
                    "household_id": HOUSEHOLD,
                    "origin": "AUTONOMOUS_ATTENTION",
                    "binding": "binding-queued",
                }
            )
            return
        parts = self.path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["v1", "requests"]:
            self._write({"error": "not found"}, 404)
            return
        request_id = parts[2]
        operation = parts[3]
        binding = "binding-direct" if request_id == DIRECT_REQUEST else "binding-queued"
        if payload.get("binding") != binding:
            self._write({"error": "binding mismatch"}, 409)
            return
        if operation == "context":
            self._write(
                {
                    "request_id": request_id,
                    "household_id": HOUSEHOLD,
                    "context_packet_id": "00000000-0000-0000-0000-000000000201",
                    "context_digest": "fixture-context-digest",
                    "authority": {"state": "bounded"},
                }
            )
        elif operation == "tools":
            self._write(
                {
                    "tools": [
                        {
                            "tool_id": "anima.home_assistant.get_state",
                            "plugin_id": "anima.home_assistant",
                            "version": "1",
                            "schema_digest": "fixture-read-schema",
                            "read_only": True,
                            "availability": True,
                        },
                        {
                            "tool_id": "anima.home_assistant.set_power",
                            "plugin_id": "anima.home_assistant",
                            "version": "1",
                            "schema_digest": "fixture-write-schema",
                            "read_only": False,
                            "availability": True,
                        },
                    ]
                }
            )
        elif operation == "provider-start":
            self._write({"status": "PROVIDER_RUNNING"})
        elif operation == "invoke":
            self._write(
                {
                    "status": "SUCCEEDED",
                    "tool_id": payload.get("tool_id"),
                    "evidence": {"verification": "fixture-observed"},
                }
            )
        elif operation == "result":
            self._write({"status": "RECORDED"})
        elif operation == "status":
            self._write(
                {
                    "request_id": request_id,
                    "lifecycle": "COMPLETED",
                    "provider_invocation_started": True,
                    "attempt_count": 1,
                }
            )
        else:
            self._write({"error": "not found"}, 404)

    def log_message(self, format: str, *args: Any) -> None:
        del format, args


class FixtureServer(ThreadingHTTPServer):
    def __init__(self, state: FixtureState) -> None:
        super().__init__(("127.0.0.1", 0), FixtureHandler)
        self.state = state


def _value(result: Any) -> dict[str, Any]:
    for name in ("structured_content", "structuredContent"):
        structured = getattr(result, name, None)
        if isinstance(structured, dict) and structured:
            candidate = structured.get("result", structured)
            if isinstance(candidate, dict):
                return candidate
    for item in getattr(result, "content", ()):
        text = getattr(item, "text", None)
        if isinstance(text, str):
            decoded = json.loads(text)
            if isinstance(decoded, dict):
                return decoded
    raise AssertionError("MCP result did not contain a JSON object")


def _field(value: Any, *names: str) -> Any:
    for name in names:
        found = getattr(value, name, None)
        if found is not None:
            return found
    return None


async def _session(
    *,
    endpoint: str,
    token_path: Path,
    sentry_request_id: str,
    direct: bool,
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.update(
        {
            "ANIMA_PYTHON": sys.executable,
            "ANIMA_SENTRY_ENDPOINT": endpoint,
            "ANIMA_SENTRY_CLIENT_TOKEN_FILE": str(token_path),
            "ANIMA_SENTRY_WORKER_ID": "r4-runtime-certification",
            "PYTHONPATH": "",
        }
    )
    parameters = StdioServerParameters(command=str(LAUNCHER), args=[], env=environment)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            initialized = await client.initialize()
            listed = await client.list_tools()
            names = {str(_field(tool, "name")) for tool in listed.tools}
            expected = {
                "anima_health",
                "anima_open_interaction",
                "anima_open_direct_interaction",
                "anima_get_context",
                "anima_list_tools",
                "anima_invoke",
                "anima_provider_start",
                "anima_submit_result",
                "anima_status",
            }
            if not expected.issubset(names):
                raise AssertionError(f"MCP catalogue missing tools: {sorted(expected - names)}")
            for tool in listed.tools:
                schema = _field(tool, "input_schema", "inputSchema")
                if not isinstance(schema, dict) or schema.get("type") != "object":
                    raise AssertionError(f"invalid schema for {tool.name}")

            health = _value(await client.call_tool("anima_health", {}))
            if health.get("status") != "available":
                raise AssertionError("fixture health did not report available")
            if direct:
                opened = _value(
                    await client.call_tool(
                        "anima_open_direct_interaction",
                        {
                            "sentry_request_id": sentry_request_id,
                            "user_text": "What is the current test-device state?",
                            "source_surface": "sentry-shadow",
                        },
                    )
                )
            else:
                opened = _value(
                    await client.call_tool(
                        "anima_open_interaction",
                        {
                            "sentry_request_id": sentry_request_id,
                            "source_surface": "sentry-shadow",
                        },
                    )
                )
            request_id = str(opened["request_id"])
            context = _value(
                await client.call_tool("anima_get_context", {"request_id": request_id})
            )
            catalogue = _value(
                await client.call_tool("anima_list_tools", {"request_id": request_id})
            )
            start = _value(
                await client.call_tool("anima_provider_start", {"request_id": request_id})
            )
            read_result = _value(
                await client.call_tool(
                    "anima_invoke",
                    {
                        "request_id": request_id,
                        "tool_id": "anima.home_assistant.get_state",
                        "arguments": {"resource_id": "resource-1"},
                        "ordinal": 1,
                    },
                )
            )
            write_result = _value(
                await client.call_tool(
                    "anima_invoke",
                    {
                        "request_id": request_id,
                        "tool_id": "anima.home_assistant.set_power",
                        "arguments": {
                            "resource_id": "resource-1",
                            "desired_on": True,
                        },
                        "ordinal": 2,
                    },
                )
            )
            submitted = _value(
                await client.call_tool(
                    "anima_submit_result",
                    {
                        "request_id": request_id,
                        "status": "RESPONSE",
                        "response": "The test device is on.",
                    },
                )
            )
            status = _value(await client.call_tool("anima_status", {"request_id": request_id}))
            return {
                "request_origin": opened.get("origin"),
                "request_id": request_id,
                "context_household": context.get("household_id"),
                "bound_tools": len(catalogue.get("tools", [])),
                "provider_start": start.get("status"),
                "read_status": read_result.get("status"),
                "governed_mutation_status": write_result.get("status"),
                "result_submission": submitted.get("status"),
                "terminal_lifecycle": status.get("lifecycle"),
                "protocol": _field(initialized, "protocol_version", "protocolVersion"),
                "server_name": _field(_field(initialized, "server_info", "serverInfo"), "name"),
                "tool_count": len(listed.tools),
            }


def main() -> int:
    if not LAUNCHER.is_file():
        raise SystemExit(f"missing ANIMA MCP launcher: {LAUNCHER}")
    with tempfile.TemporaryDirectory(prefix="anima-sentry-mcp-r4-") as directory:
        token_path = Path(directory) / "client-token"
        token_path.write_text(TOKEN, encoding="utf-8")
        os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)
        state = FixtureState()
        fixture = FixtureServer(state)
        thread = threading.Thread(target=fixture.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = f"http://127.0.0.1:{fixture.server_port}"
            direct = asyncio.run(
                _session(
                    endpoint=endpoint,
                    token_path=token_path,
                    sentry_request_id="direct-runtime-request",
                    direct=True,
                )
            )
            queued = asyncio.run(
                _session(
                    endpoint=endpoint,
                    token_path=token_path,
                    sentry_request_id="queued-runtime-request",
                    direct=False,
                )
            )
        finally:
            fixture.shutdown()
            fixture.server_close()
            thread.join(timeout=2)
    paths = list(state.paths)
    if paths.index("/v1/interactions/direct") >= paths.index(
        "/v1/requests/" + DIRECT_REQUEST + "/provider-start"
    ):
        raise AssertionError("direct provider start did not follow direct interaction")
    if paths.index("/v1/interactions/open") >= paths.index(
        "/v1/requests/" + QUEUED_REQUEST + "/provider-start"
    ):
        raise AssertionError("queued provider start did not follow queue claim")
    print(
        json.dumps(
            {
                "status": "PASSED",
                "evidence_level": "DETERMINISTIC",
                "runtime": {
                    "python": sys.version.split()[0],
                    "mcp": __import__("importlib.metadata").metadata.version("mcp"),
                },
                "direct": direct,
                "queued": queued,
                "transport_paths": len(paths),
                "provider_calls": sum(path.endswith("/invoke") for path in paths),
                "schemas_validated": True,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
