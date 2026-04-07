import json
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@pytest.mark.asyncio
async def test_official_mcp_stdio_client_can_discover_and_call_public_tools():
    backend_root = Path(__file__).resolve().parents[1]
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["mcp_server.py", "--transport", "stdio"],
        cwd=str(backend_root),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]

            assert init.serverInfo.name == "doc-assist-mcp"
            assert tool_names == [
                "facts.list_modules",
                "facts.get_module",
                "prototypes.list_pages",
                "prototypes.get_page",
                "docs.list_saved",
                "docs.load_saved",
            ]

            result = await session.call_tool("facts.list_modules", {})
            assert result.content

            payload = json.loads(result.content[0].text)
            assert "modules" in payload
            assert payload["count"] >= 1
