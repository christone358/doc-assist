"""ADK tool wrappers backed by the MCP runtime adapters."""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, TYPE_CHECKING

from mcp_runtime import create_default_runtime_server
from mcp_runtime.errors import MCPRuntimeError
from mcp_runtime.skill_namespace import SkillNamespace

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)

_PUBLIC_RUNTIME = create_default_runtime_server()


@dataclass(frozen=True)
class DiscoveredToolSpec:
    logical_name: str
    source_server: str
    visibility: str
    handler: Callable[..., Awaitable[dict]]


_PUBLIC_TOOL_PRIORITY = {
    "facts.list_modules": 100,
    "facts.get_module": 110,
    "prototypes.list_pages": 200,
    "prototypes.get_page": 210,
    "docs.list_saved": 300,
    "docs.load_saved": 310,
    "artifacts.read_file": 400,
    "artifacts.write_file": 410,
}

_SKILL_TOOL_PRIORITY = {
    "skill.list_resources": 400,
    "skill.read_resource": 410,
    "skill.run_script": 420,
}


def sanitize_tool_name(logical_name: str) -> str:
    return logical_name.replace(".", "_")


def _set_tool_name(func, logical_name: str):
    func.__name__ = sanitize_tool_name(logical_name)
    setattr(func, "logical_name", logical_name)
    return func


def _set_tool_signature(func, handler: Callable[..., Any]):
    handler_signature = inspect.signature(handler)
    func.__signature__ = handler_signature.replace(return_annotation=str)
    handler_annotations = dict(getattr(handler, "__annotations__", {}))
    handler_annotations["return"] = str
    func.__annotations__ = handler_annotations
    return func


def _tool_priority(logical_name: str, priority_map: Dict[str, int], fallback_base: int) -> tuple[int, str]:
    namespace = logical_name.split(".", 1)[0] if "." in logical_name else "zz"
    namespace_bias = {
        "facts": fallback_base,
        "prototypes": fallback_base + 100,
        "docs": fallback_base + 200,
        "artifacts": fallback_base + 300,
        "skill": fallback_base + 400,
    }.get(namespace, fallback_base + 900)
    return (priority_map.get(logical_name, namespace_bias), logical_name)


def get_public_runtime(runtime=None):
    return runtime or _PUBLIC_RUNTIME


def list_public_tool_specs(runtime=None) -> Tuple[DiscoveredToolSpec, ...]:
    runtime = get_public_runtime(runtime)
    tools = runtime.list_tools(include_internal=False)
    ordered_names = sorted(
        tools.keys(),
        key=lambda logical_name: _tool_priority(logical_name, _PUBLIC_TOOL_PRIORITY, 1000),
    )
    return tuple(
        DiscoveredToolSpec(
            logical_name=logical_name,
            source_server="mcp-runtime-public",
            visibility="public",
            handler=tools[logical_name].handler,
        )
        for logical_name in ordered_names
    )


def list_internal_skill_tool_specs(skill: Any) -> Tuple[DiscoveredToolSpec, ...]:
    namespace = SkillNamespace(skill)
    handlers = {
        "skill.list_resources": namespace.list_resources,
        "skill.read_resource": namespace.read_resource,
        "skill.run_script": namespace.run_script,
    }
    ordered_names = sorted(
        handlers.keys(),
        key=lambda logical_name: _tool_priority(logical_name, _SKILL_TOOL_PRIORITY, 4000),
    )
    return tuple(
        DiscoveredToolSpec(
            logical_name=logical_name,
            source_server=f"skill:{skill.id}",
            visibility="internal",
            handler=handlers[logical_name],
        )
        for logical_name in ordered_names
    )


def _pretty_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _module_summary_line(module: Dict[str, Any]) -> str:
    system = module.get("system") or "待补充系统"
    subsystem = module.get("subsystem") or "未设置子系统"
    return f"- {system} / {subsystem} / {module.get('name', '')} ({module.get('id', '')})"


async def _emit_resource_event(
    ctx: "ConversationContext",
    tool_name: str,
    display_text: str,
    output_preview: Optional[str] = None,
    output_detail: Optional[str] = None,
    **data: Any,
) -> None:
    from agent.adk.runner_adapter import emit_execution_event
    from agent.models import ExecutionActor, ExecutionEventStatus, ExecutionPhase

    await emit_execution_event(
        ctx,
        execution_id=ctx.current_execution_id or ctx.orchestrator_execution_id,
        parent_execution_id=ctx.orchestrator_execution_id if ctx.current_execution_id else None,
        actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
        phase=ExecutionPhase.RESOURCE,
        name=tool_name,
        status=ExecutionEventStatus.COMPLETED,
        display_text=display_text,
        data={
            "tool": tool_name,
            "parent_node_id": ctx.current_skill_node_id if ctx.current_execution_id else None,
            "output_preview": output_preview or display_text,
            "output_detail": output_detail if output_detail is not None else (output_preview or display_text),
            **data,
        },
    )


def _build_tool_wrapper(
    logical_name: str,
    handler: Callable[..., Any],
    invoke: Callable[..., Awaitable[dict]],
    on_result: Callable[[dict, Dict[str, Any]], Awaitable[str]],
    on_error: Optional[Callable[[MCPRuntimeError, Dict[str, Any]], str]] = None,
):
    signature = inspect.signature(handler)

    async def tool_wrapper(*args, **kwargs) -> str:
        try:
            bound = signature.bind_partial(*args, **kwargs)
        except TypeError as exc:
            return f"参数错误：{logical_name} - {exc}"
        params = dict(bound.arguments)
        try:
            result = await invoke(**params)
        except MCPRuntimeError as exc:
            if on_error is not None:
                return on_error(exc, params)
            return exc.message
        return await on_result(result, params)

    _set_tool_name(tool_wrapper, logical_name)
    _set_tool_signature(tool_wrapper, handler)
    return tool_wrapper


def create_public_mcp_tool(ctx: "ConversationContext", logical_name: str, runtime=None):
    runtime = get_public_runtime(runtime)
    public_specs = {spec.logical_name: spec for spec in list_public_tool_specs(runtime)}
    spec = public_specs.get(logical_name)
    if spec is None:
        raise ValueError(f"未发现 public MCP 工具：{logical_name}")

    if logical_name == "facts.list_modules":
        async def on_result(result: dict, _params: Dict[str, Any]) -> str:
            overview = result.get("overview_markdown", "").strip()
            modules = result.get("modules", [])
            if overview:
                ctx.loaded_facts_parts.append(f"### [Facts: modules]\n{overview}")
                ctx.collected_facts_parts.append(f"### [Facts: modules]\n{overview}")
                text = overview
            else:
                text = "\n".join(["# 模块清单", *[_module_summary_line(item) for item in modules]]) or "暂无模块信息。"
                ctx.loaded_facts_parts.append(f"### [Facts: modules]\n{text}")
                ctx.collected_facts_parts.append(f"### [Facts: modules]\n{text}")

            summary = f"已加载模块清单：{len(modules)} 个模块"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=text,
                count=len(modules),
            )
            return text

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "facts.get_module":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            module_ref = params.get("module_ref", "")
            content = result.get("content", "")
            module = result.get("module", {})
            ctx.loaded_facts_parts.append(f"### [Facts: module {module.get('id', module_ref)}]\n{content}")
            ctx.collected_facts_parts.append(f"### [Facts: module {module.get('id', module_ref)}]\n{content}")
            ctx.current_module_id = module.get("id") or ctx.current_module_id
            ctx.current_module_name = module.get("name") or ctx.current_module_name
            ctx.current_system_name = module.get("system") or ctx.current_system_name
            ctx.current_subsystem_name = module.get("subsystem") or ctx.current_subsystem_name
            summary = f"已加载模块事实主档：{module.get('name', module_ref)}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=content,
                module_id=module.get("id"),
            )
            return content

        def on_error(exc: MCPRuntimeError, params: Dict[str, Any]) -> str:
            if exc.error_type == "ambiguous_module_ref":
                candidates = exc.details.get("candidates", [])
                lines = [f"模块引用存在歧义：{params.get('module_ref', '')}"]
                lines.extend(_module_summary_line(item) for item in candidates[:8])
                return "\n".join(lines)
            return exc.message

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
            on_error=on_error,
        )

    if logical_name == "prototypes.list_pages":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            module_ref = params.get("module_ref", "")
            module = result.get("module", {})
            pages = result.get("pages", [])
            summary_text = result.get("llm_summary", "").strip()
            lines = [summary_text] if summary_text else [f"模块 {module_ref} 关联页面："]
            for item in pages:
                suffix_parts = []
                if item.get("title"):
                    suffix_parts.append(f"标题：{item['title']}")
                if item.get("relative_path"):
                    suffix_parts.append(f"路径：{item['relative_path']}")
                if item.get("match_status") and item.get("match_status") != "matched":
                    suffix_parts.append(f"状态：{item['match_status']}")
                suffix = f"（{'；'.join(suffix_parts)}）" if suffix_parts else ""
                lines.append(f"- {item.get('page_name', '')}{suffix}")

            text = "\n".join(lines).strip()
            matched = sum(1 for item in pages if item.get("match_status") == "matched")
            ambiguous = sum(1 for item in pages if item.get("match_status") == "ambiguous")
            unmatched = sum(1 for item in pages if item.get("match_status") == "unmatched")
            status_parts = [f"已匹配 {matched} 页"]
            if ambiguous:
                status_parts.append(f"歧义 {ambiguous} 页")
            if unmatched:
                status_parts.append(f"待确认 {unmatched} 页")
            status_text = "，".join(status_parts)
            ctx.loaded_facts_parts.append(f"### [Prototype Pages: {module.get('id', module_ref)}]\n{text}")
            summary = f"已加载原型页面清单：{module.get('name', module_ref)}，共 {len(pages)} 页，{status_text}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=text,
                count=len(pages),
                matched=matched,
                ambiguous=ambiguous,
                unmatched=unmatched,
            )
            return text

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "prototypes.get_page":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            page_ref = params.get("page_ref", "")
            page = result.get("page", {})
            fact = result.get("fact", {})
            summary_text = result.get("llm_summary", "").strip()
            warnings = result.get("parser_warnings", [])

            text_parts = [part for part in [summary_text] if part]
            if warnings:
                text_parts.append("解析告警：" + "；".join(warnings))
            detail_json = _pretty_json(fact)
            block = "\n\n".join(part for part in ["\n".join(text_parts).strip(), detail_json] if part).strip()
            ctx.loaded_facts_parts.append(f"### [Prototype Page: {page.get('page_ref', page_ref)}]\n{block}")
            summary = f"已加载原型页面详情：{page.get('page_name', page_ref)}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=block,
                page_ref=page.get("page_ref", page_ref),
            )
            return block

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "docs.list_saved":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            documents = result.get("documents", [])
            if not documents:
                return "暂无历史已保存文档。"
            lines = ["历史已保存文档清单："]
            for item in documents:
                lines.append(
                    f"- [{item['doc_type']}] {item['doc_name']} 最新版本：v{item['latest_version']}，日期：{item['latest_date']}"
                )
            summary = f"已查询历史文档清单：{len(documents)} 份"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail="\n".join(lines),
                count=len(documents),
                doc_type=params.get("doc_type"),
            )
            return "\n".join(lines)

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "docs.load_saved":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            content = result.get("content", "")
            doc_name = params.get("doc_name", "")
            ctx.loaded_base_draft = content
            ctx.loaded_base_doc_name = result.get("doc_name") or doc_name
            ctx.current_module_name = result.get("doc_name") or ctx.current_module_name
            ctx.loaded_docs_parts.append(
                f"### [Saved Document: {result.get('doc_type')} / {result.get('doc_name')} / v{result.get('version')}]\n{content}"
            )
            summary = (
                f"已加载 {result.get('doc_name')} v{result.get('version')} · "
                f"{result.get('date')}，共 {len(content)} 字，就绪"
            )
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=(
                    f"文档：{result.get('doc_name')}\n"
                    f"类型：{result.get('doc_type')}\n"
                    f"版本：v{result.get('version')}\n"
                    f"日期：{result.get('date')}\n"
                    f"正文长度：{len(content)} 字"
                ),
                doc_type=result.get("doc_type"),
                doc_name=result.get("doc_name"),
                version=result.get("version"),
            )
            return summary

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "artifacts.read_file":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            file_info = result.get("file", {})
            path = file_info.get("path") or params.get("path", "")
            size_bytes = file_info.get("size_bytes", 0)
            include_content = params.get("include_content", True)
            is_text = file_info.get("is_text", False)
            content = result.get("content", "")
            truncated = result.get("content_truncated", False)
            text_parts = [
                f"路径：{path}",
                f"大小：{size_bytes} bytes",
                f"MIME：{file_info.get('mime_type', 'application/octet-stream')}",
            ]
            if include_content and is_text and content:
                text_parts.append("")
                text_parts.append(content)
                if truncated:
                    text_parts.append("")
                    text_parts.append("（内容已按 max_chars 截断）")
            elif include_content and not is_text:
                text_parts.append("说明：该文件不是文本文件，未返回正文内容。")

            text = "\n".join(text_parts)
            if content:
                ctx.loaded_docs_parts.append(f"### [Artifact File: {path}]\n{text}")
            summary = f"已读取本地文件：{path}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=text,
                path=path,
                size_bytes=size_bytes,
                include_content=include_content,
            )
            return text

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    if logical_name == "artifacts.write_file":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            file_info = result.get("file", {})
            path = file_info.get("path") or params.get("path", "")
            size_bytes = file_info.get("size_bytes", 0)
            created = result.get("created", False)
            overwritten = result.get("overwritten", False)
            action = "已创建" if created and not overwritten else "已覆盖写入" if overwritten else "已写入"
            summary = f"{action}本地文件：{path}（{size_bytes} bytes）"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=_pretty_json(result),
                path=path,
                size_bytes=size_bytes,
                created=created,
                overwritten=overwritten,
            )
            return summary

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: runtime.invoke(logical_name, **params),
            on_result=on_result,
        )

    async def on_result(result: dict, params: Dict[str, Any]) -> str:
        summary = f"已调用工具：{logical_name}"
        await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
        await _emit_resource_event(
            ctx,
            logical_name,
            summary,
            output_detail=_pretty_json(result) if isinstance(result, dict) else str(result),
            params=params,
        )
        return _pretty_json(result) if isinstance(result, dict) else str(result)

    return _build_tool_wrapper(
        logical_name=logical_name,
        handler=spec.handler,
        invoke=lambda **params: runtime.invoke(logical_name, **params),
        on_result=on_result,
    )


def create_public_mcp_tools(ctx: "ConversationContext", runtime=None) -> Tuple:
    """Create public MCP-backed tools for the main orchestrator."""
    runtime = get_public_runtime(runtime)
    return tuple(
        create_public_mcp_tool(ctx, spec.logical_name, runtime=runtime)
        for spec in list_public_tool_specs(runtime)
    )


def create_internal_skill_mcp_tool(ctx: "ConversationContext", skill: Any, logical_name: str):
    """Create one internal skill.* tool wrapper bound to the current skill."""
    namespace = SkillNamespace(skill)
    tool_specs = {spec.logical_name: spec for spec in list_internal_skill_tool_specs(skill)}
    spec = tool_specs.get(logical_name)
    if spec is None:
        raise ValueError(f"未发现 internal skill 工具：{logical_name}")

    handler_map = {
        "skill.list_resources": namespace.list_resources,
        "skill.read_resource": namespace.read_resource,
        "skill.run_script": namespace.run_script,
    }

    if logical_name == "skill.list_resources":
        async def on_result(result: dict, _params: Dict[str, Any]) -> str:
            resources = result.get("resources", [])
            if not resources:
                return "当前 Skill 无可用资源。"
            lines = ["当前 Skill 可用资源："]
            for item in resources:
                lines.append(f"- [{item['category']}] {item['path']}")
            summary = f"已列出 Skill 资源：{len(resources)} 项"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail="\n".join(lines),
                skill_id=getattr(skill, "id", None),
                count=len(resources),
            )
            return "\n".join(lines)

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: handler_map[logical_name](**params),
            on_result=on_result,
        )

    if logical_name == "skill.read_resource":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            content = result.get("content", "")
            path = result.get("path", params.get("relative_path", ""))
            category = result.get("category", "other")
            ctx.loaded_skill_resource_parts.append(f"### [Skill Resource: {path}]\n{content}")
            summary = f"已读取 Skill 资源：{path}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=f"[{category}] {path}\n\n{content}",
                skill_id=getattr(skill, "id", None),
                relative_path=path,
            )
            return f"[{category}] {path}\n\n{content}"

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: handler_map[logical_name](**params),
            on_result=on_result,
        )

    if logical_name == "skill.run_script":
        async def on_result(result: dict, params: Dict[str, Any]) -> str:
            stderr_summary = result.get("stderr_summary", "")
            summary = f"脚本已执行：{result.get('path')}，exit_code={result.get('exit_code')}"
            if stderr_summary:
                summary += f"\nstderr:\n{stderr_summary}"
            await ctx.ws_sender({"type": "status", "sub": "detail", "tool": logical_name, "content": summary})
            await _emit_resource_event(
                ctx,
                logical_name,
                summary,
                output_detail=_pretty_json(result),
                skill_id=getattr(skill, "id", None),
                relative_path=result.get("path", params.get("relative_path", "")),
            )
            if result.get("stdout"):
                return result["stdout"]
            return _pretty_json(result)

        return _build_tool_wrapper(
            logical_name=logical_name,
            handler=spec.handler,
            invoke=lambda **params: handler_map[logical_name](**params),
            on_result=on_result,
        )

    async def on_result(result: dict, _params: Dict[str, Any]) -> str:
        return _pretty_json(result) if isinstance(result, dict) else str(result)

    return _build_tool_wrapper(
        logical_name=logical_name,
        handler=spec.handler,
        invoke=lambda **params: handler_map[logical_name](**params),
        on_result=on_result,
    )


def create_internal_skill_mcp_tools(ctx: "ConversationContext", skill: Any) -> Tuple:
    """Create internal skill.* tool wrappers bound to the current skill."""
    return tuple(
        create_internal_skill_mcp_tool(ctx, skill, spec.logical_name)
        for spec in list_internal_skill_tool_specs(skill)
    )
