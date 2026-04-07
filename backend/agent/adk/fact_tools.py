"""
项目事实加载 Tools - 直接供 DocumentAgent ReAct 循环调用。

提供四个工具：
- resolve_target_module: 解析用户给出的模块引用，定位唯一模块
- load_module_fact_sheet: 按模块聚合根加载模块事实主档
- get_fact_overview: 加载系统 / 子系统 / 模块等概览信息
- get_fact_detail:   按模块加载描述、用例、功能点、API、页面、包类等详细内容

create_fact_tools(ctx) 返回带 WebSocket 侧信道和上下文累积的异步版本，
每次调用结果自动追加到 ctx.collected_facts_parts，供 write_document 注入。
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

from agent.context_loader import load_context
from project_fact_modules import ModuleArchiveRepository

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)

_FACTS_ROOT = Path(__file__).parent.parent.parent.parent / "project-facts"

_OVERVIEW_VOCAB = {
    "systems",
    "subsystems",
    "modules",
    "usecases",
    "function_points",
    "apis",
    "classes",
    "prototypes",
    # legacy aliases
    "usecases",
    "interfaces",
}
_DETAIL_VOCAB = {
    "module",
    "description",
    "usecases",
    "function_points",
    "apis",
    "classes",
    "prototypes",
    "dependencies",
    "remarks",
    # legacy aliases
    "usecases",
    "interfaces",
}
_FACT_TYPE_ALIASES = {"interfaces": "apis"}


# ── 纯函数（同步，无副作用）────────────────────────────────────────────────

def get_fact_overview(category: Optional[str] = None) -> str:
    """加载项目概览信息，帮助 Agent 定位写作目标。

    Args:
        category: 概览类型，可选值：
            systems、subsystems、modules、usecases、
            function_points、apis、classes、prototypes。
            兼容别名：interfaces。
            为空时默认加载 modules 清单。

    Returns:
        概览内容字符串；若无数据则返回说明性文字。
    """
    vocab = category if category in _OVERVIEW_VOCAB else "modules"

    if not _FACTS_ROOT.exists():
        logger.warning(f"project-facts 目录不存在: {_FACTS_ROOT}")
        return f"project-facts 目录不存在，无法加载 {vocab} 概览。"

    contents = load_context(vocab, None, _FACTS_ROOT)
    if not contents:
        return f"未找到 {vocab} 概览信息。"

    result = "\n\n".join(contents)
    logger.info(f"get_fact_overview: vocab={vocab}, chars={len(result)}")
    return result


def get_fact_detail(target_id: str, fact_type: str) -> str:
    """按写作目标和事实类型加载详细内容。

    Args:
        target_id: 写作目标的标识符。对于模块型事实，支持模块 ID（mod-agent）、
            模块名称、模块别名；工具内部会优先解析为稳定 module_id。
        fact_type: 事实类型，可选值：
            module（模块档案全文）、description（模块描述）、usecases（用例信息）、function_points（功能点）、
            apis（接口定义）、classes（类包设计）、prototypes（原型界面）、
            dependencies（依赖模块）、remarks（备注）。
            兼容别名：interfaces。

    Returns:
        与写作目标相关的详细内容字符串；若无数据则返回说明性文字。
    """
    if fact_type not in _DETAIL_VOCAB:
        return (
            f"不支持的事实类型 '{fact_type}'，可选："
            "module、description、usecases、function_points、apis、classes、prototypes、dependencies、remarks。"
        )

    if not _FACTS_ROOT.exists():
        logger.warning(f"project-facts 目录不存在: {_FACTS_ROOT}")
        return f"project-facts 目录不存在，无法加载 {fact_type} 详情。"

    resolved_target_id = target_id
    if fact_type in {"module", "description", "usecases", "function_points", "apis", "classes", "prototypes", "dependencies", "remarks", "interfaces"}:
        repo = ModuleArchiveRepository(_FACTS_ROOT)
        module_id, candidates = repo.resolve_module_reference(target_id)
        if candidates:
            candidate_text = "；".join(
                f"{item['system'] or '待补充系统'} / {item['subsystem'] or '未设置子系统'} / {item['name']} ({item['id']})"
                for item in candidates[:5]
            )
            suffix = "；请改用模块 ID 或补充所属系统/子系统。" if candidates else ""
            return f"存在多个模块匹配 target_id='{target_id}'：{candidate_text}{suffix}"
        if module_id:
            resolved_target_id = module_id

    contents = load_context(fact_type, resolved_target_id, _FACTS_ROOT)
    if not contents:
        return (
            f"未找到 target_id='{target_id}' 的 {fact_type} 信息，"
            "该信息可能尚未录入或标识符有误。"
        )

    result = "\n\n".join(contents)
    logger.info(f"get_fact_detail: target_id={target_id}, fact_type={fact_type}, chars={len(result)}")
    return result


def load_module_fact_sheet(target_ref: str) -> str:
    """按模块聚合根加载模块事实主档。

    Args:
        target_ref: 用户提供的模块引用，可为模块 ID、模块名或别名。

    Returns:
        模块事实主档全文；若模块存在歧义或不存在，则返回说明性文字。
    """
    if not _FACTS_ROOT.exists():
        logger.warning(f"project-facts 目录不存在: {_FACTS_ROOT}")
        return "project-facts 目录不存在，无法加载模块事实主档。"

    repo = ModuleArchiveRepository(_FACTS_ROOT)
    module_id, candidates = repo.resolve_module_reference(target_ref)
    if candidates:
        candidate_text = "；".join(
            f"{item['system'] or '待补充系统'} / {item['subsystem'] or '未设置子系统'} / {item['name']} ({item['id']})"
            for item in candidates[:5]
        )
        return f"存在多个模块匹配 target_ref='{target_ref}'：{candidate_text}；请改用模块 ID 或补充所属系统/子系统。"

    if not module_id:
        return f"未找到与 '{target_ref}' 对应的模块，无法加载模块事实主档。"

    contents = load_context("module", module_id, _FACTS_ROOT)
    if not contents:
        return f"未找到模块 '{target_ref}' 的事实主档。"

    result = "\n\n".join(contents)
    logger.info(f"load_module_fact_sheet: target_ref={target_ref}, module_id={module_id}, chars={len(result)}")
    return result


def resolve_target_module(target_ref: str) -> str:
    """Resolve a user-provided module reference to a unique module.

    Args:
        target_ref: 用户提供的模块引用，可为模块名、别名、模块 ID，
            也支持带系统 / 子系统范围的自然语言短语。

    Returns:
        标准化定位结果字符串。
    """
    if not _FACTS_ROOT.exists():
        logger.warning(f"project-facts 目录不存在: {_FACTS_ROOT}")
        return "project-facts 目录不存在，无法定位目标模块。"

    repo = ModuleArchiveRepository(_FACTS_ROOT)
    module_id, candidates = repo.resolve_module_reference(target_ref)
    if candidates:
        candidate_lines = [
            f"- {item['system'] or '待补充系统'} / {item['subsystem'] or '未设置子系统'} / {item['name']} ({item['id']})"
            for item in candidates[:8]
        ]
        return "\n".join(
            [
                "模块定位结果：AMBIGUOUS",
                f"- 输入: {target_ref}",
                *candidate_lines,
            ]
        )

    if not module_id:
        return "\n".join(
            [
                "模块定位结果：NOT_FOUND",
                f"- 输入: {target_ref}",
            ]
        )

    module = repo.get_module(module_id)
    if not module:
        return "\n".join(
            [
                "模块定位结果：NOT_FOUND",
                f"- 输入: {target_ref}",
            ]
        )

    return "\n".join(
        [
            "模块定位结果：FOUND",
            f"- 模块: {module['name']}",
            f"- 所属系统: {module['system'] or '待补充系统'}",
            f"- 所属子系统: {module['subsystem'] or '未设置子系统'}",
            f"- 模块ID: {module['id']}",
        ]
    )


# ── 摘要生成（用于 WebSocket 侧信道展示）──────────────────────────────────

def _fact_type_label(fact_type: str) -> str:
    normalized = _FACT_TYPE_ALIASES.get(fact_type, fact_type)
    return {
        "module": "模块档案",
        "description": "模块描述",
        "usecases": "用例信息",
        "function_points": "功能点",
        "apis": "接口定义",
        "classes":    "类包设计",
        "prototypes": "原型界面",
        "dependencies": "依赖模块",
        "remarks": "备注",
    }.get(normalized, normalized)


def _classify_fact_result(result: str) -> str:
    """将事实工具原始返回归类为 success / empty / error。"""
    text = (result or "").strip()

    if not text:
        return "empty"

    if text.startswith("未找到 "):
        return "empty"

    if (
        text.startswith("project-facts 目录不存在")
        or text.startswith("不支持的事实类型")
        or text.startswith("处理失败")
        or text.startswith("存在多个模块匹配")
    ):
        return "error"

    return "success"


def _classify_module_resolution_result(result: str) -> str:
    text = (result or "").strip()
    if not text:
        return "empty"
    if text.startswith("模块定位结果：FOUND"):
        return "success"
    if text.startswith("模块定位结果：NOT_FOUND"):
        return "empty"
    if text.startswith("模块定位结果：AMBIGUOUS"):
        return "error"
    if text.startswith("project-facts 目录不存在"):
        return "error"
    return "success"


def _summarize_module_resolution(target_ref: str, result: str) -> str:
    outcome = _classify_module_resolution_result(result)
    if outcome == "empty":
        return f"未识别到目标模块：{target_ref}"
    if outcome == "error":
        if result.startswith("模块定位结果：AMBIGUOUS"):
            lines = [line.strip() for line in result.splitlines() if line.strip()]
            candidates = "；".join(line[2:] for line in lines[2:6] if line.startswith("- "))
            return f"模块定位存在歧义：{candidates}；需要用户补充所属系统或子系统。"
        return f"定位失败：{result}"

    module_name = re.search(r"^- 模块:\s*(.+)$", result, re.MULTILINE)
    system_name = re.search(r"^- 所属系统:\s*(.+)$", result, re.MULTILINE)
    subsystem_name = re.search(r"^- 所属子系统:\s*(.+)$", result, re.MULTILINE)
    module_id = re.search(r"^- 模块ID:\s*(.+)$", result, re.MULTILINE)
    if module_name and module_id:
        system = system_name.group(1).strip() if system_name else "待补充系统"
        subsystem = subsystem_name.group(1).strip() if subsystem_name else "未设置子系统"
        return (
            f"已定位目标模块：{system} / {subsystem} / "
            f"{module_name.group(1).strip()} ({module_id.group(1).strip()})"
        )
    return f"已完成模块定位：{target_ref}"


def _summarize_overview(category: str, result: str) -> str:
    normalized = _FACT_TYPE_ALIASES.get(category, category)
    outcome = _classify_fact_result(result)
    if outcome == "empty":
        return f"未加载到数据：{result}"
    if outcome == "error":
        return f"加载失败：{result}"

    if normalized == "systems":
        systems = re.findall(r"^##\s+(.+?)$", result, re.MULTILINE)
        if systems:
            preview = "、".join(name.strip() for name in systems[:5])
            suffix = f" 等 {len(systems)} 个系统" if len(systems) > 5 else ""
            return f"已加载系统概览：{preview}{suffix}"
    elif normalized == "subsystems":
        subsystems = re.findall(r"^###\s+(.+?)$", result, re.MULTILINE)
        if subsystems:
            preview = "、".join(name.strip() for name in subsystems[:5])
            suffix = f" 等 {len(subsystems)} 个子系统" if len(subsystems) > 5 else ""
            return f"已加载子系统概览：{preview}{suffix}"
    elif normalized == "modules":
        modules = re.findall(r"^##\s+(.+?)\s+\{#([^}]+)\}", result, re.MULTILINE)
        if not modules:
            modules = re.findall(r"^###\s+\d+\.\s+(.+?)\s+\(([^)]+)\)", result, re.MULTILINE)
        if modules:
            preview = "、".join(name.strip() for name, _module_id in modules[:5])
            suffix = f" 等 {len(modules)} 个模块" if len(modules) > 5 else ""
            return f"已加载模块档案概览：{preview}{suffix}"
    elif normalized in ("usecases", "function_points", "apis", "classes", "prototypes"):
        names = []
        for raw_name in re.findall(r"^##\s+(.+?)(?:\n|$)", result, re.MULTILINE):
            cleaned = re.sub(r"\s+\{#[^}]+\}\s*$", "", raw_name).strip()
            if cleaned:
                names.append(cleaned)
        if names:
            return f"已加载{_fact_type_label(normalized)}概览：{'、'.join(n.strip() for n in names[:4])}"
    return f"已加载 {normalized} 概览（{len(result)} 字符）"


def _summarize_detail(target_id: str, fact_type: str, result: str) -> str:
    normalized = _FACT_TYPE_ALIASES.get(fact_type, fact_type)
    outcome = _classify_fact_result(result)
    if outcome == "empty":
        return f"未加载到数据：{result}"
    if outcome == "error":
        return f"加载失败：{result}"

    title_m = re.search(r"^#\s+(.+?)$", result, re.MULTILINE)
    if title_m:
        return f"已加载模块档案「{title_m.group(1).strip()}」"

    section_m = re.search(r"^##\s+(.+?)$", result, re.MULTILINE)
    if section_m:
        return f"已加载模块档案中的「{section_m.group(1).strip()}」"

    return f"已加载 {_fact_type_label(normalized)}（{len(result)} 字符）"


def _extract_module_section(result: str, section_title: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(section_title)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        result,
        re.MULTILINE,
    )
    if not match:
        return ""
    return match.group(1).strip()


def _section_has_placeholder(section_body: str) -> bool:
    return "_待补充_" in (section_body or "")


def _parse_markdown_table_rows(section_body: str) -> list[list[str]]:
    lines = [line.strip() for line in (section_body or "").splitlines() if line.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        return []

    rows: list[list[str]] = []
    for line in lines[2:]:
        if "|" not in line:
            continue
        values = [col.strip() for col in line.strip("|").split("|")]
        if not values:
            continue
        if any(value and value != "_待补充_" for value in values):
            rows.append(values)
    return rows


def _parse_bullet_items(section_body: str) -> list[str]:
    items: list[str] = []
    for line in (section_body or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        value = stripped[1:].strip()
        if value:
            items.append(value)
    return items


def _shorten_list(items: list[str], limit: int = 5) -> str:
    cleaned = [item.strip() for item in items if item and item.strip()]
    if not cleaned:
        return ""
    preview = "、".join(cleaned[:limit])
    if len(cleaned) > limit:
        return f"{preview} 等 {len(cleaned)} 项"
    return preview


def _summarize_module_fact_sheet(target_ref: str, result: str) -> str:
    outcome = _classify_fact_result(result)
    if outcome == "empty":
        return f"未加载到模块事实主档：{result}"
    if outcome == "error":
        return f"加载失败：{result}"

    title_m = re.search(r"^#\s+(.+?)$", result, re.MULTILINE)
    system_m = re.search(r"^- 所属系统:\s*(.+)$", result, re.MULTILINE)
    subsystem_m = re.search(r"^- 所属子系统:\s*(.+)$", result, re.MULTILINE)

    description = _extract_module_section(result, "功能描述")
    usecases_body = _extract_module_section(result, "用例信息")
    function_points_body = _extract_module_section(result, "功能点")
    apis_body = _extract_module_section(result, "API 清单")
    prototypes_body = _extract_module_section(result, "页面 / 原型")
    classes_body = _extract_module_section(result, "包 / 类")
    dependencies_body = _extract_module_section(result, "依赖模块")
    remarks = _extract_module_section(result, "备注")

    usecase_rows = _parse_markdown_table_rows(usecases_body)
    function_point_rows = _parse_markdown_table_rows(function_points_body)
    api_rows = _parse_markdown_table_rows(apis_body)
    prototype_items = _parse_bullet_items(prototypes_body)
    class_items = _parse_bullet_items(classes_body)
    dependency_items = _parse_bullet_items(dependencies_body)

    lines = ["已加载模块事实主档："]
    if title_m:
        lines.append(f"- 模块: {title_m.group(1).strip()}")
    if system_m:
        lines.append(f"- 所属系统: {system_m.group(1).strip()}")
    if subsystem_m:
        lines.append(f"- 所属子系统: {subsystem_m.group(1).strip()}")

    if description:
        description_preview = " ".join(description.split())
        lines.append(f"- 功能描述: {description_preview}")

    if usecase_rows:
        usecase_names = _shorten_list([row[0] for row in usecase_rows if row])
        lines.append(f"- 用例信息: 共 {len(usecase_rows)} 条；{usecase_names}")
    elif _section_has_placeholder(usecases_body):
        lines.append("- 用例信息: 待补充")

    if function_point_rows:
        point_names = _shorten_list([row[1] for row in function_point_rows if len(row) > 1])
        lines.append(f"- 功能点: 共 {len(function_point_rows)} 项；{point_names}")
    elif _section_has_placeholder(function_points_body):
        lines.append("- 功能点: 待补充")

    if api_rows:
        api_names = _shorten_list([row[0] for row in api_rows if row])
        lines.append(f"- API 清单: 共 {len(api_rows)} 条；{api_names}")
    elif _section_has_placeholder(apis_body):
        lines.append("- API 清单: 待补充")

    if prototype_items:
        lines.append(f"- 页面 / 原型: {_shorten_list(prototype_items)}")
    elif _section_has_placeholder(prototypes_body):
        lines.append("- 页面 / 原型: 待补充")

    if class_items:
        lines.append(f"- 包 / 类: {_shorten_list(class_items)}")
    elif _section_has_placeholder(classes_body):
        lines.append("- 包 / 类: 待补充")

    if dependency_items:
        lines.append(f"- 依赖模块: {_shorten_list(dependency_items)}")
    elif dependencies_body:
        dependency_preview = " ".join(dependencies_body.split())
        lines.append(f"- 依赖模块: {dependency_preview}")

    if remarks:
        lines.append(f"- 备注: {' '.join(remarks.split())}")

    lines.append("- 主档已覆盖以上章节；仅在用户明确追问专项细节时再补充 get_fact_detail。")
    return "\n".join(lines)


def _remember_resolved_module(ctx: "ConversationContext", module_id: Optional[str]) -> None:
    """将成功定位到的模块身份写入当前对话上下文。"""
    if not module_id:
        return

    try:
        repo = ModuleArchiveRepository(_FACTS_ROOT)
        module = repo.get_module(module_id)
    except Exception as exc:  # pragma: no cover - 仅容错
        logger.warning(f"_remember_resolved_module: 读取模块信息失败 module_id={module_id}: {exc}")
        return

    if not module:
        return

    ctx.current_module_id = module_id
    ctx.current_module_name = module.get("name") or ctx.current_module_name
    ctx.current_system_name = module.get("system") or ctx.current_system_name
    ctx.current_subsystem_name = module.get("subsystem") or ctx.current_subsystem_name


def _extract_module_id_from_resolution_result(result: str) -> Optional[str]:
    match = re.search(r"^- 模块ID:\s*(.+)$", result or "", re.MULTILINE)
    return match.group(1).strip() if match else None


# ── 工厂：带 WS 侧信道 + 上下文累积的异步包装 ──────────────────────────────

def create_fact_tools(ctx: "ConversationContext") -> Tuple:
    """创建带 WebSocket 侧信道和上下文累积的事实工具集。

    返回的工具函数每次调用后：
    1. 对 facts 类工具，将结果追加到 ctx.collected_facts_parts（供 write_document 自动注入）
    2. 向 WebSocket 发送 detail 子事件（供前端可观测面板展示）

    Returns:
        (resolve_target_module_fn, load_module_fact_sheet_fn, get_fact_overview_fn, get_fact_detail_fn) 元组
    """
    from agent.adk.runner_adapter import complete_tool_node
    from agent.models import ExecutionNodeStatus

    execution_id = ctx.current_execution_id or ctx.orchestrator_execution_id
    parent_node_id = ctx.current_skill_node_id if ctx.current_execution_id else None

    async def resolve_target_module_fn(target_ref: str) -> str:
        """定位目标模块。

        Args:
            target_ref: 用户提供的模块引用，可包含系统 / 子系统范围。

        Returns:
            模块定位结果摘要；完整定位结果写入 ADK session 历史，供后续工具调用使用。
        """
        result = resolve_target_module(target_ref)
        _remember_resolved_module(ctx, _extract_module_id_from_resolution_result(result))
        summary = _summarize_module_resolution(target_ref, result)
        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "resolve_target_module",
            "outcome": _classify_module_resolution_result(result),
            "content": summary,
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="resolve_target_module",
            parent_node_id=parent_node_id,
            status=(
                ExecutionNodeStatus.FAILED
                if _classify_module_resolution_result(result) == "error"
                else ExecutionNodeStatus.COMPLETED
            ),
            output_preview=summary,
            output_detail=result,
        )
        return result

    async def get_fact_overview_fn(category: Optional[str] = None) -> str:
        """加载项目概览信息，帮助定位写作目标。

        Args:
            category: 概览类型，可选值：systems、subsystems、modules、
                      usecases、function_points、apis、classes、prototypes。
                      兼容别名：interfaces。
                      为空时默认加载 modules 清单。

        Returns:
            概览摘要字符串（如"已加载模块清单：A、B、C 等5个模块"）；
            原始全文通过内部上下文累积供 write_document 使用，不写入此返回值。
        """
        vocab = category if category in _OVERVIEW_VOCAB else "modules"
        result = get_fact_overview(vocab)

        # 第一层即时截断：原始全文追加到 collected_facts_parts 供当轮 write_document 使用
        ctx.collected_facts_parts.append(f"### [概览: {vocab}]\n{result}")

        # WS 侧信道：detail 子事件
        summary = _summarize_overview(vocab, result)
        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "get_fact_overview",
            "outcome": _classify_fact_result(result),
            "content": summary,
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="get_fact_overview",
            parent_node_id=parent_node_id,
            status=(
                ExecutionNodeStatus.FAILED
                if _classify_fact_result(result) == "error"
                else ExecutionNodeStatus.COMPLETED
            ),
            output_preview=summary,
            output_detail=result,
        )

        # 向 ADK session 历史只返回摘要，不含原始全文，避免历史膨胀
        return summary

    async def load_module_fact_sheet_fn(target_ref: str) -> str:
        """按模块聚合根加载模块事实主档。

        Args:
            target_ref: 模块 ID、模块名称或别名。

        Returns:
            模块事实主档完整正文；同时发送摘要到可观测面板。
        """
        result = load_module_fact_sheet(target_ref)
        if _FACTS_ROOT.exists():
            repo = ModuleArchiveRepository(_FACTS_ROOT)
            module_id, candidates = repo.resolve_module_reference(target_ref)
            if module_id and not candidates:
                _remember_resolved_module(ctx, module_id)

        ctx.collected_facts_parts.append(
            f"### [模块事实主档: {target_ref}]\n{result}"
        )

        summary = _summarize_module_fact_sheet(target_ref, result)
        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "load_module_fact_sheet",
            "outcome": _classify_fact_result(result),
            "content": summary,
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="load_module_fact_sheet",
            parent_node_id=parent_node_id,
            status=(
                ExecutionNodeStatus.FAILED
                if _classify_fact_result(result) == "error"
                else ExecutionNodeStatus.COMPLETED
            ),
            output_preview=summary,
            output_detail=result,
        )

        return result

    async def get_fact_detail_fn(target_id: str, fact_type: str) -> str:
        """按写作目标和事实类型加载详细内容。

        Args:
            target_id: 写作目标的标识符，例如模块 ID（mod-agent）、类名等。
            fact_type: 事实类型，可选值：module、description、usecases、
                       function_points、apis、classes、prototypes、dependencies、remarks。
                       兼容别名：interfaces。

        Returns:
            详情摘要字符串（如"已加载「XXX」用例描述"）；
            原始全文通过内部上下文累积供 write_document 使用，不写入此返回值。
        """
        result = get_fact_detail(target_id, fact_type)

        # 第一层即时截断：原始全文追加到 collected_facts_parts
        ctx.collected_facts_parts.append(
            f"### [详情: {target_id} / {fact_type}]\n{result}"
        )

        # WS 侧信道：detail 子事件
        summary = _summarize_detail(target_id, fact_type, result)
        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "get_fact_detail",
            "outcome": _classify_fact_result(result),
            "content": summary,
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="get_fact_detail",
            parent_node_id=parent_node_id,
            status=(
                ExecutionNodeStatus.FAILED
                if _classify_fact_result(result) == "error"
                else ExecutionNodeStatus.COMPLETED
            ),
            output_preview=summary,
            output_detail=result,
        )

        # 向 ADK session 历史只返回摘要，不含原始全文
        return summary

    return resolve_target_module_fn, load_module_fact_sheet_fn, get_fact_overview_fn, get_fact_detail_fn
