"""Standalone entrypoint for the Doc Assist MCP server."""

from __future__ import annotations

import argparse

from mcp_runtime import create_default_runtime_server, get_mcp_server_settings


def main() -> None:
    settings = get_mcp_server_settings()
    parser = argparse.ArgumentParser(description="Run the Doc Assist MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--include-internal", action="store_true", default=settings.enable_internal_tools)
    args = parser.parse_args()

    runtime = create_default_runtime_server(settings=settings)
    server = runtime.build_fastmcp(include_internal=args.include_internal)

    if args.transport == "stdio":
        server.run()
        return

    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
