"""MCP runtime registry and optional FastMCP server integration."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from .config import MCPServerSettings, get_mcp_server_settings
from .artifacts_namespace import ArtifactsNamespace
from .docs_namespace import DocsNamespace
from .errors import MCPRuntimeError
from .facts_namespace import FactsNamespace
from .models import ToolVisibility
from .prototypes_namespace import PrototypesNamespace

logger = logging.getLogger(__name__)

try:  # pragma: no cover - exercised only when MCP SDK is installed
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - default in unit tests
    FastMCP = None


@dataclass(slots=True)
class RegisteredTool:
    logical_name: str
    visibility: ToolVisibility
    handler: Callable[..., Awaitable[dict]]


class MCPRuntimeServer:
    """Registry for public/internal MCP tools with optional FastMCP export."""

    def __init__(self, settings: Optional[MCPServerSettings] = None):
        self.settings = settings or get_mcp_server_settings()
        self._tools: Dict[str, RegisteredTool] = {}

    def register_tool(
        self,
        logical_name: str,
        handler: Callable[..., Awaitable[dict]],
        visibility: ToolVisibility,
    ) -> None:
        self._tools[logical_name] = RegisteredTool(
            logical_name=logical_name,
            visibility=visibility,
            handler=handler,
        )

    def register_public_tool(self, logical_name: str, handler: Callable[..., Awaitable[dict]]) -> None:
        self.register_tool(logical_name, handler, ToolVisibility.PUBLIC)

    def register_internal_tool(self, logical_name: str, handler: Callable[..., Awaitable[dict]]) -> None:
        self.register_tool(logical_name, handler, ToolVisibility.INTERNAL)

    def list_tools(self, *, include_internal: bool = False) -> Dict[str, RegisteredTool]:
        if include_internal:
            return dict(self._tools)
        return {
            name: tool for name, tool in self._tools.items()
            if tool.visibility == ToolVisibility.PUBLIC
        }

    async def invoke(self, logical_name: str, **kwargs: Any) -> dict:
        tool = self._tools.get(logical_name)
        if tool is None:
            raise MCPRuntimeError(
                error_type="tool_not_registered",
                message=f"未注册 MCP 工具：{logical_name}",
                target=logical_name,
            )

        target = (
            kwargs.get("module_ref")
            or kwargs.get("doc_name")
            or kwargs.get("relative_path")
            or kwargs.get("path")
            or ""
        )
        logger.info("mcp_runtime: call tool=%s target=%s", logical_name, target)
        try:
            result = tool.handler(**kwargs)
            if inspect.isawaitable(result):
                payload = await result
            else:  # pragma: no cover - handlers are async today
                payload = result
            logger.info("mcp_runtime: success tool=%s target=%s", logical_name, target)
            return payload
        except MCPRuntimeError:
            logger.exception("mcp_runtime: error tool=%s target=%s", logical_name, target)
            raise
        except Exception as exc:  # pragma: no cover - defensive conversion
            logger.exception("mcp_runtime: unexpected error tool=%s target=%s", logical_name, target)
            raise MCPRuntimeError(
                error_type="runtime_error",
                message=f"MCP 工具执行失败：{logical_name}",
                target=str(target or logical_name),
                details={"exception": str(exc)},
            ) from exc

    def build_fastmcp(self, *, include_internal: bool = False):  # pragma: no cover - requires MCP SDK
        if FastMCP is None:
            raise RuntimeError("未安装 MCP Python SDK，无法创建 FastMCP server。")

        server = FastMCP(
            self.settings.server_name,
            host=self.settings.host,
            port=self.settings.port,
            streamable_http_path=self.settings.streamable_http_path,
        )
        for tool in self.list_tools(include_internal=include_internal).values():
            handler = tool.handler
            try:
                decorator = server.tool(name=tool.logical_name)
            except TypeError:
                decorator = server.tool()
                handler.__name__ = tool.logical_name
            decorator(handler)
        return server


def create_default_runtime_server(settings: Optional[MCPServerSettings] = None) -> MCPRuntimeServer:
    """Create the default runtime server with public tools registered."""

    runtime = MCPRuntimeServer(settings=settings)
    facts = FactsNamespace()
    prototypes = PrototypesNamespace()
    docs = DocsNamespace()
    artifacts = ArtifactsNamespace()

    runtime.register_public_tool("facts.list_modules", facts.list_modules)
    runtime.register_public_tool("facts.get_module", facts.get_module)
    runtime.register_public_tool("prototypes.list_pages", prototypes.list_pages)
    runtime.register_public_tool("prototypes.get_page", prototypes.get_page)
    runtime.register_public_tool("docs.list_saved", docs.list_saved)
    runtime.register_public_tool("docs.load_saved", docs.load_saved)
    runtime.register_public_tool("artifacts.read_file", artifacts.read_file)
    runtime.register_public_tool("artifacts.write_file", artifacts.write_file)
    return runtime
