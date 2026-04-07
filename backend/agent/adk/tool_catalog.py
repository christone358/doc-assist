"""Host-side MCP tool catalog and role-specific tool views."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Literal, TYPE_CHECKING

from agent.adk.ask_user_tool import create_ask_user_tool
from agent.adk.draft_tool import create_get_current_draft_tool
from agent.adk.execute_skill_tool import create_execute_skill_tool
from agent.adk.mcp_tools import (
    create_internal_skill_mcp_tool,
    create_public_mcp_tool,
    get_public_runtime,
    list_internal_skill_tool_specs,
    list_public_tool_specs,
)
from agent.adk.write_document_tool import create_write_document_tool

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext
    from agent.models import SkillInfo


AgentRole = Literal["main_agent", "skill_subagent"]
ToolVisibility = Literal["public", "internal", "local"]


@dataclass(frozen=True)
class ToolCatalogEntry:
    """Metadata for a host-managed tool entry."""

    tool_id: str
    logical_name: str
    runtime_name: str
    source_server: str
    visibility: ToolVisibility
    allowed_roles: tuple[AgentRole, ...]
    schema_metadata: Dict[str, Any]
    prompt_summary: str
    sort_order: int
    factory: Callable[[], Any]


@dataclass(frozen=True)
class ToolView:
    """A role-specific projection over the host-side tool catalog."""

    role: AgentRole
    tool_ids: tuple[str, ...]
    tools: tuple[Any, ...]
    catalog: Dict[str, ToolCatalogEntry]


_KNOWN_TOOL_SUMMARIES: Dict[str, str] = {
    "facts.list_modules": "获取当前项目模块清单。",
    "facts.get_module": "按模块引用加载模块聚合根事实主档；若引用有歧义，应进一步 ask_user 澄清。",
    "prototypes.list_pages": "列出某模块关联的原型页面清单与匹配结果。",
    "prototypes.get_page": "读取单个原型页面的结构化页面事实和摘要。",
    "docs.list_saved": "列出历史已保存文档的元数据清单，不含正文。",
    "docs.load_saved": "加载历史已保存文档的最新版本或指定版本，作为只读参考或后续基线。",
    "artifacts.read_file": "读取工作区内指定路径的本地文件信息；文本文件可按需返回正文并注入当前写作上下文。",
    "artifacts.write_file": "将生成结果写入工作区内指定本地路径，可用于在运行时落盘输出文件。",
    "skill.list_resources": "列出当前 Skill 可用参考文件、模板和脚本资源。",
    "skill.read_resource": "读取当前 Skill 根目录内的文本资源。",
    "skill.run_script": "执行当前 Skill 根目录内的 Python 脚本。",
    "execute_skill": "委托对应 Skill 的专业子 Agent 完成文档编写或修订。`user_intent` 须包含写作对象名称、文档类型和写作重点，不得直接透传用户原文。",
    "ask_user": "仅在无法继续执行时使用，用于澄清写作对象、文档类型、版本来源或其他关键信息。",
    "get_current_draft": "读取当前对话已有的文档草稿；修改场景应先调用。",
    "write_document": "生成或修改文档正文；未调用此工具时不得声称“已完成”。",
}

_LOCAL_TOOL_ORDERS = {
    "execute_skill": 900,
    "ask_user": 980,
    "get_current_draft": 50,
    "write_document": 950,
}

_ROLE_SORT_OVERRIDES: Dict[AgentRole, Dict[str, int]] = {
    "main_agent": {
        "facts.list_modules": 100,
        "facts.get_module": 110,
        "prototypes.list_pages": 200,
        "prototypes.get_page": 210,
        "docs.list_saved": 300,
        "docs.load_saved": 310,
        "artifacts.read_file": 400,
        "artifacts.write_file": 410,
        "execute_skill": 900,
        "ask_user": 980,
    },
    "skill_subagent": {
        "get_current_draft": 50,
        "docs.list_saved": 100,
        "docs.load_saved": 110,
        "artifacts.read_file": 150,
        "artifacts.write_file": 160,
        "facts.list_modules": 200,
        "facts.get_module": 210,
        "prototypes.list_pages": 300,
        "prototypes.get_page": 310,
        "skill.list_resources": 400,
        "skill.read_resource": 410,
        "skill.run_script": 420,
        "write_document": 950,
        "ask_user": 980,
    },
}


def _build_schema_metadata(handler: Callable[..., Any]) -> Dict[str, Any]:
    signature = inspect.signature(handler)
    params = []
    for param in signature.parameters.values():
        if param.name in {"tool_context"}:
            continue
        label = param.name
        if param.default is not inspect.Signature.empty:
            label += "?"
        params.append(label)
    return {"params": params, "returns": "str"}


def _default_tool_summary(logical_name: str) -> str:
    namespace = logical_name.split(".", 1)[0] if "." in logical_name else "tool"
    return f"调用 `{namespace}` 命名空间下的工具 `{logical_name}`。"


def _tool_label(entry: ToolCatalogEntry) -> str:
    params = entry.schema_metadata.get("params", [])
    return f"{entry.runtime_name}({', '.join(params)})"


def render_tool_section(tool_view: ToolView, heading: str) -> str:
    lines = [heading, ""]
    for tool_id in tool_view.tool_ids:
        entry = tool_view.catalog[tool_id]
        lines.append(f"- **{_tool_label(entry)}**：")
        lines.append(f"  {entry.prompt_summary}")
        lines.append("")
    return "\n".join(lines).strip()


def _make_local_entry(
    tool_id: str,
    source_server: str,
    allowed_roles: tuple[AgentRole, ...],
    sort_order: int,
    factory: Callable[[], Any],
    handler: Callable[..., Any],
) -> ToolCatalogEntry:
    return ToolCatalogEntry(
        tool_id=tool_id,
        logical_name=tool_id,
        runtime_name=tool_id,
        source_server=source_server,
        visibility="local",
        allowed_roles=allowed_roles,
        schema_metadata=_build_schema_metadata(handler),
        prompt_summary=_KNOWN_TOOL_SUMMARIES[tool_id],
        sort_order=sort_order,
        factory=factory,
    )


def build_mcp_tool_catalog(
    ctx: "ConversationContext",
    *,
    runtime=None,
    skill: "SkillInfo" | None = None,
) -> Dict[str, ToolCatalogEntry]:
    """Collect host-managed MCP tool entries for the current context."""
    runtime = get_public_runtime(runtime)
    catalog: Dict[str, ToolCatalogEntry] = {}

    for spec in list_public_tool_specs(runtime):
        catalog[spec.logical_name] = ToolCatalogEntry(
            tool_id=spec.logical_name,
            logical_name=spec.logical_name,
            runtime_name=spec.logical_name.replace(".", "_"),
            source_server=spec.source_server,
            visibility="public",
            allowed_roles=("main_agent", "skill_subagent"),
            schema_metadata=_build_schema_metadata(spec.handler),
            prompt_summary=_KNOWN_TOOL_SUMMARIES.get(spec.logical_name, _default_tool_summary(spec.logical_name)),
            sort_order=1000 if "." not in spec.logical_name else 0,
            factory=lambda logical_name=spec.logical_name: create_public_mcp_tool(ctx, logical_name, runtime=runtime),
        )

    for tool_id, entry in list(catalog.items()):
        namespace = tool_id.split(".", 1)[0] if "." in tool_id else "zz"
        namespace_base = {"facts": 100, "prototypes": 200, "docs": 300, "artifacts": 400}.get(namespace, 800)
        catalog[tool_id] = ToolCatalogEntry(
            tool_id=entry.tool_id,
            logical_name=entry.logical_name,
            runtime_name=entry.runtime_name,
            source_server=entry.source_server,
            visibility=entry.visibility,
            allowed_roles=entry.allowed_roles,
            schema_metadata=entry.schema_metadata,
            prompt_summary=entry.prompt_summary,
            sort_order={
                "facts.list_modules": 100,
                "facts.get_module": 110,
                "prototypes.list_pages": 200,
                "prototypes.get_page": 210,
                "docs.list_saved": 300,
                "docs.load_saved": 310,
                "artifacts.read_file": 400,
                "artifacts.write_file": 410,
            }.get(tool_id, namespace_base + 50),
            factory=entry.factory,
        )

    if skill is not None and getattr(skill, "skill_md_path", None):
        for spec in list_internal_skill_tool_specs(skill):
            catalog[spec.logical_name] = ToolCatalogEntry(
                tool_id=spec.logical_name,
                logical_name=spec.logical_name,
                runtime_name=spec.logical_name.replace(".", "_"),
                source_server=spec.source_server,
                visibility="internal",
                allowed_roles=("skill_subagent",),
                schema_metadata=_build_schema_metadata(spec.handler),
                prompt_summary=_KNOWN_TOOL_SUMMARIES.get(spec.logical_name, _default_tool_summary(spec.logical_name)),
                sort_order={"skill.list_resources": 400, "skill.read_resource": 410, "skill.run_script": 420}.get(spec.logical_name, 450),
                factory=lambda logical_name=spec.logical_name: create_internal_skill_mcp_tool(ctx, skill, logical_name),
            )

    return catalog


def get_tool_runtime_name(tool_view: ToolView, logical_name: str, default: str | None = None) -> str:
    """Resolve the provider-facing runtime name for a logical tool id."""
    entry = tool_view.catalog.get(logical_name)
    if entry is not None:
        return entry.runtime_name
    return default or logical_name


def _visible_entries(catalog: Dict[str, ToolCatalogEntry], role: AgentRole) -> list[ToolCatalogEntry]:
    overrides = _ROLE_SORT_OVERRIDES.get(role, {})
    return sorted(
        [entry for entry in catalog.values() if role in entry.allowed_roles],
        key=lambda entry: (overrides.get(entry.tool_id, entry.sort_order), entry.logical_name),
    )


def build_main_agent_tool_view(
    ctx: "ConversationContext",
    skills_map: Dict[str, "SkillInfo"],
    *,
    runtime=None,
) -> ToolView:
    """Project the host-side tool catalog for the main orchestrator."""
    catalog = build_mcp_tool_catalog(ctx, runtime=runtime)

    execute_skill_tool = create_execute_skill_tool(ctx, skills_map)
    ask_user_tool = create_ask_user_tool(ctx)
    catalog["execute_skill"] = _make_local_entry(
        "execute_skill",
        source_server="host-local",
        allowed_roles=("main_agent",),
        sort_order=_LOCAL_TOOL_ORDERS["execute_skill"],
        factory=lambda tool=execute_skill_tool: tool,
        handler=execute_skill_tool,
    )
    catalog["ask_user"] = _make_local_entry(
        "ask_user",
        source_server="host-local",
        allowed_roles=("main_agent",),
        sort_order=_LOCAL_TOOL_ORDERS["ask_user"],
        factory=lambda tool=ask_user_tool: tool,
        handler=ask_user_tool,
    )

    entries = _visible_entries(catalog, "main_agent")
    tool_ids = tuple(entry.tool_id for entry in entries)
    tools = tuple(entry.factory() for entry in entries)
    return ToolView(role="main_agent", tool_ids=tool_ids, tools=tools, catalog=catalog)


def build_skill_subagent_tool_view(
    ctx: "ConversationContext",
    skill: "SkillInfo",
    skills_map: Dict[str, "SkillInfo"],
    *,
    runtime=None,
) -> ToolView:
    """Project the host-side tool catalog for a skill sub-agent."""
    catalog = build_mcp_tool_catalog(ctx, runtime=runtime, skill=skill)

    get_current_draft_tool = create_get_current_draft_tool(ctx)
    write_document_tool = create_write_document_tool(ctx, skills_map)
    ask_user_tool = create_ask_user_tool(ctx)

    catalog["get_current_draft"] = _make_local_entry(
        "get_current_draft",
        source_server="host-local",
        allowed_roles=("skill_subagent",),
        sort_order=_LOCAL_TOOL_ORDERS["get_current_draft"],
        factory=lambda tool=get_current_draft_tool: tool,
        handler=get_current_draft_tool,
    )
    catalog["write_document"] = _make_local_entry(
        "write_document",
        source_server="host-local",
        allowed_roles=("skill_subagent",),
        sort_order=_LOCAL_TOOL_ORDERS["write_document"],
        factory=lambda tool=write_document_tool: tool,
        handler=write_document_tool,
    )
    catalog["ask_user"] = _make_local_entry(
        "ask_user",
        source_server="host-local",
        allowed_roles=("skill_subagent",),
        sort_order=_LOCAL_TOOL_ORDERS["ask_user"],
        factory=lambda tool=ask_user_tool: tool,
        handler=ask_user_tool,
    )

    entries = _visible_entries(catalog, "skill_subagent")
    tool_ids = tuple(entry.tool_id for entry in entries)
    tools = tuple(entry.factory() for entry in entries)
    return ToolView(role="skill_subagent", tool_ids=tool_ids, tools=tools, catalog=catalog)
