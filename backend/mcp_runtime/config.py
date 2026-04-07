"""Configuration helpers for the MCP runtime server."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class MCPServerSettings:
    """Runtime configuration for the MCP server entrypoints."""

    server_name: str = "doc-assist-mcp"
    host: str = "127.0.0.1"
    port: int = 8765
    streamable_http_path: str = "/mcp"
    enable_internal_tools: bool = False


def get_mcp_server_settings() -> MCPServerSettings:
    """Load MCP server settings from environment variables."""

    return MCPServerSettings(
        server_name=os.getenv("DOC_ASSIST_MCP_SERVER_NAME", "doc-assist-mcp"),
        host=os.getenv("DOC_ASSIST_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("DOC_ASSIST_MCP_PORT", "8765")),
        streamable_http_path=os.getenv("DOC_ASSIST_MCP_PATH", "/mcp"),
        enable_internal_tools=os.getenv("DOC_ASSIST_MCP_ENABLE_INTERNAL", "").lower() in {"1", "true", "yes"},
    )
