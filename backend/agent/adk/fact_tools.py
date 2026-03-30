"""
项目事实加载 Tools - 直接供 DocumentAgent ReAct 循环调用。

提供两个工具：
- get_fact_overview: 加载项目概览信息（模块清单、用例清单等）
- get_fact_detail:   按写作目标和事实类型加载详细内容

create_fact_tools(ctx) 返回带 WebSocket 侧信道和上下文累积的异步版本，
每次调用结果自动追加到 ctx.collected_facts_parts，供 write_document 注入。
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

from agent.context_loader import load_context

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)

_FACTS_ROOT = Path(__file__).parent.parent.parent.parent / "project-facts"

_OVERVIEW_VOCAB = {"modules", "usecases", "classes", "interfaces"}
_DETAIL_VOCAB   = {"usecases", "classes", "interfaces", "prototypes"}


# ── 纯函数（同步，无副作用）────────────────────────────────────────────────

def get_fact_overview(category: Optional[str] = None) -> str:
    """加载项目概览信息，帮助 Agent 定位写作目标。

    Args:
        category: 概览类型，可选值：modules（模块清单）、usecases（用例清单）、
                  classes（类包清单）、interfaces（接口清单）。
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
        target_id: 写作目标的标识符，例如模块 ID（mod-agent）、类名、包名等。
        fact_type: 事实类型，可选值：usecases（用例描述）、classes（类包设计）、
                   interfaces（接口定义）、prototypes（原型界面）。

    Returns:
        与写作目标相关的详细内容字符串；若无数据则返回说明性文字。
    """
    if fact_type not in _DETAIL_VOCAB:
        return f"不支持的事实类型 '{fact_type}'，可选：usecases、classes、interfaces、prototypes。"

    if not _FACTS_ROOT.exists():
        logger.warning(f"project-facts 目录不存在: {_FACTS_ROOT}")
        return f"project-facts 目录不存在，无法加载 {fact_type} 详情。"

    contents = load_context(fact_type, target_id, _FACTS_ROOT)
    if not contents:
        return (
            f"未找到 target_id='{target_id}' 的 {fact_type} 信息，"
            "该信息可能尚未录入或标识符有误。"
        )

    result = "\n\n".join(contents)
    logger.info(f"get_fact_detail: target_id={target_id}, fact_type={fact_type}, chars={len(result)}")
    return result


# ── 摘要生成（用于 WebSocket 侧信道展示）──────────────────────────────────

def _fact_type_label(fact_type: str) -> str:
    return {
        "usecases":   "用例描述",
        "classes":    "类包设计",
        "interfaces": "接口定义",
        "prototypes": "原型界面",
    }.get(fact_type, fact_type)


def _summarize_overview(category: str, result: str) -> str:
    if category == "modules":
        modules = re.findall(r"^##\s+(.+?)\s+\{#([^}]+)\}", result, re.MULTILINE)
        if not modules:
            modules = re.findall(r"^###\s+\d+\.\s+(.+?)\s+\(([^)]+)\)", result, re.MULTILINE)
        if modules:
            preview = "、".join(
                f"{name.strip()}({module_id.strip().lower()})"
                for name, module_id in modules[:5]
            )
            suffix = f" 等 {len(modules)} 个模块" if len(modules) > 5 else ""
            return f"已加载模块清单：{preview}{suffix}"
    elif category == "usecases":
        usecases = re.findall(
            r"###\s+(UC-\d+):\s+(.+?)\n- \*\*模块\*\*:\s*(mod-[a-z0-9-]+)",
            result,
            re.MULTILINE,
        )
        if usecases:
            preview = "、".join(
                f"{uc_id} {name.strip()}({module_id.strip()})"
                for uc_id, name, module_id in usecases[:5]
            )
            suffix = f" 等 {len(usecases)} 个用例" if len(usecases) > 5 else ""
            return f"已加载用例清单：{preview}{suffix}"
    elif category in ("classes", "interfaces"):
        names = re.findall(r"^(?:##|###)\s+(.+?)(?:\n|$)", result, re.MULTILINE)
        if names:
            return f"已加载{_fact_type_label(category)}清单：{'、'.join(n.strip() for n in names[:4])}"
    return f"已加载 {category} 概览（{len(result)} 字符）"


def _summarize_detail(target_id: str, fact_type: str, result: str) -> str:
    title_m = re.search(r"^#\s+(.+?)$", result, re.MULTILINE)
    if title_m:
        return f"已加载「{title_m.group(1).strip()}」{_fact_type_label(fact_type)}"
    return f"已加载 {target_id} {_fact_type_label(fact_type)}（{len(result)} 字符）"


# ── 工厂：带 WS 侧信道 + 上下文累积的异步包装 ──────────────────────────────

def create_fact_tools(ctx: "ConversationContext") -> Tuple:
    """创建带 WebSocket 侧信道和上下文累积的事实工具对。

    返回的工具函数每次调用后：
    1. 将结果追加到 ctx.collected_facts_parts（供 write_document 自动注入）
    2. 向 WebSocket 发送 detail 子事件（供前端可观测面板展示）

    Returns:
        (get_fact_overview_fn, get_fact_detail_fn) 元组
    """

    async def get_fact_overview_fn(category: Optional[str] = None) -> str:
        """加载项目概览信息，帮助定位写作目标。

        Args:
            category: 概览类型，可选值：modules（模块清单）、usecases（用例清单）、
                      classes（类包清单）、interfaces（接口清单）。
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
            "content": summary,
        })

        # 向 ADK session 历史只返回摘要，不含原始全文，避免历史膨胀
        return summary

    async def get_fact_detail_fn(target_id: str, fact_type: str) -> str:
        """按写作目标和事实类型加载详细内容。

        Args:
            target_id: 写作目标的标识符，例如模块 ID（mod-agent）、类名等。
            fact_type: 事实类型，可选值：usecases（用例描述）、classes（类包设计）、
                       interfaces（接口定义）、prototypes（原型界面）。

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
            "content": summary,
        })

        # 向 ADK session 历史只返回摘要，不含原始全文
        return summary

    return get_fact_overview_fn, get_fact_detail_fn
