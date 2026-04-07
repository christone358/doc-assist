"""Single page parser for prototype HTML pages."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

from .axure_enricher import enrich_axure_interactions
from .dom_extractor import extract_dom_facts
from .models import PrototypePageFact, PrototypePageIndexItem
from .summary_builder import build_llm_summary


def _page_id(relative_path: str) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:12]
    return f"page-{digest}"


def _aliases(page_name: str, title: str) -> List[str]:
    aliases: List[str] = []
    for candidate in [page_name, title]:
        text = (candidate or "").strip()
        if text and text not in aliases:
            aliases.append(text)
        if text.endswith("页") and text[:-1] and text[:-1] not in aliases:
            aliases.append(text[:-1])
    return aliases


def parse_page(
    html_file: Path,
    *,
    package_id: str,
    prototypes_root: Path,
) -> tuple[PrototypePageIndexItem, PrototypePageFact]:
    html_text = html_file.read_text(encoding="utf-8", errors="ignore")
    relative_path = str(html_file.relative_to(prototypes_root))
    dom_data = extract_dom_facts(html_text)
    axure_data = enrich_axure_interactions(dom_data)

    page_name = html_file.stem.strip()
    title = (dom_data.get("title") or page_name).strip()

    tables = dom_data.get("tables", [])
    elements = {
        "buttons": dom_data.get("buttons", []),
        "inputs": dom_data.get("inputs", []),
        "tables": tables,
        "tabs": dom_data.get("tabs", []),
        "dialogs": dom_data.get("dialogs", []),
        "links": [item.get("label", "") for item in dom_data.get("links", []) if item.get("label")],
    }

    outgoing_links = [
        {
            "label": item.get("label", ""),
            "target_page_id": _page_id(item.get("target", "")),
            "target": item.get("target", ""),
        }
        for item in axure_data.get("outgoing_links", [])
        if item.get("target")
    ]

    interactions = axure_data.get("interactions", [])
    evidence = []
    if elements["buttons"]:
        evidence.append(f"按钮: {' / '.join(elements['buttons'][:4])}")
    if elements["inputs"]:
        evidence.append(f"输入项: {' / '.join(elements['inputs'][:4])}")
    if tables and isinstance(tables[0], dict) and tables[0].get("columns"):
        evidence.append(f"表格列: {' / '.join(tables[0]['columns'][:5])}")

    fact_dict = {
        "layout_sections": dom_data.get("layout_sections", []),
        "elements": elements,
        "visible_texts": dom_data.get("visible_texts", []),
        "messages": dom_data.get("messages", []),
        "interactions": interactions,
    }
    llm_summary = build_llm_summary(page_name, title, relative_path, fact_dict)

    page_id = _page_id(relative_path)
    fact = PrototypePageFact(
        page_id=page_id,
        page_name=page_name,
        title=title,
        source_path=str(html_file.relative_to(prototypes_root.parent)),
        relative_path=relative_path,
        package_id=package_id,
        layout_sections=dom_data.get("layout_sections", []),
        elements=elements,
        visible_texts=dom_data.get("visible_texts", []),
        messages=dom_data.get("messages", []),
        interactions=interactions,
        outgoing_links=outgoing_links,
        evidence=evidence,
        parser_warnings=[],
        llm_summary=llm_summary,
    )
    index_item = PrototypePageIndexItem(
        page_id=page_id,
        page_name=page_name,
        title=title,
        package_id=package_id,
        source_path=str(html_file.relative_to(prototypes_root.parent)),
        relative_path=relative_path,
        outgoing_page_ids=[item["target_page_id"] for item in outgoing_links],
        aliases=_aliases(page_name, title),
    )
    return index_item, fact
