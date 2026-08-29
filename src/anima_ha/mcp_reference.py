"""Small out-of-process MCP reference plugin used only by Phase 5 tests."""

from __future__ import annotations

from mcp.server import MCPServer

server = MCPServer(name="anima-reference-mcp", version="0.1.0")


@server.tool(name="synthetic_echo", description="Return a synthetic echo response")
def synthetic_echo(message: str) -> str:
    return f"echo:{message}"


def main() -> int:
    server.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
