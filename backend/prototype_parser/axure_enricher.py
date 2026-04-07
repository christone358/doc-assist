"""Axure-specific enrichment extracted from HTML links and class patterns."""

from __future__ import annotations

from typing import Any, Dict, List


def enrich_axure_interactions(dom_data: Dict[str, Any]) -> Dict[str, List[Dict[str, str]] | List[str]]:
    interactions: List[str] = []
    outgoing_links: List[Dict[str, str]] = []

    for link in dom_data.get("links", []):
        href = (link.get("href") or "").strip()
        label = (link.get("label") or "").strip()
        if not href:
            continue
        if href.lower().endswith(".html"):
            interactions.append(
                f"点击{f'【{label}】' if label else '页面链接'}跳转到 {href}"
            )
            outgoing_links.append({"label": label, "target": href})

    for button in dom_data.get("buttons", []):
        if any(keyword in button for keyword in ("新增", "编辑", "删除", "导出", "查询", "保存", "提交")):
            interactions.append(f"点击【{button}】触发对应操作")

    return {
        "interactions": interactions,
        "outgoing_links": outgoing_links,
    }
