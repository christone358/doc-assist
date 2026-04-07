"""Build LLM-friendly summaries from structured page facts."""

from __future__ import annotations

from typing import Any, Dict, List


def _join_preview(values: List[str], limit: int = 4) -> str:
    if not values:
        return ""
    preview = "、".join(values[:limit])
    if len(values) > limit:
        preview += f" 等 {len(values)} 项"
    return preview


def build_llm_summary(page_name: str, title: str, relative_path: str, fact: Dict[str, Any]) -> str:
    sections: List[str] = []
    header = f"页面“{page_name or title or relative_path}”"
    if title and title != page_name:
        header += f"（标题：{title}）"
    header += f"，来源：{relative_path}。"
    sections.append(header)

    layout_sections = fact.get("layout_sections", [])
    if layout_sections:
        sections.append(f"关键区域：{_join_preview(layout_sections)}。")

    elements = fact.get("elements", {})
    buttons = elements.get("buttons", [])
    inputs = elements.get("inputs", [])
    dialogs = elements.get("dialogs", [])
    tabs = elements.get("tabs", [])
    tables = elements.get("tables", [])

    element_chunks: List[str] = []
    if buttons:
        element_chunks.append(f"按钮：{_join_preview(buttons)}")
    if inputs:
        element_chunks.append(f"输入项：{_join_preview(inputs)}")
    if dialogs:
        element_chunks.append(f"对话框：{_join_preview(dialogs)}")
    if tabs:
        element_chunks.append(f"选项卡：{_join_preview(tabs)}")
    if tables:
        columns = tables[0].get("columns", []) if isinstance(tables[0], dict) else []
        if columns:
            element_chunks.append(f"表格列：{_join_preview(columns)}")
        else:
            element_chunks.append("包含表格")
    if element_chunks:
        sections.append("关键控件：" + "；".join(element_chunks) + "。")

    messages = fact.get("messages", [])
    if messages:
        sections.append(f"用户可见反馈：{_join_preview(messages)}。")

    interactions = fact.get("interactions", [])
    if interactions:
        sections.append(f"主要交互：{_join_preview(interactions, limit=3)}。")

    return "\n".join(sections).strip()
