"""Tiny test-only MCP process used by the Phase 14 plugin restart target."""

from __future__ import annotations

import os

from mcp.server import MCPServer

server = MCPServer(name="anima-phase14-process-fixture", version="1.0.0")


@server.tool(name="process_probe", description="Return a bounded process identity probe")
def process_probe(value: str) -> str:
    return f"pid={os.getpid()};value={value}"


def main() -> int:
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
