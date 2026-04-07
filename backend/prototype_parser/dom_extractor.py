"""Best-effort DOM extraction without external parser dependencies."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List


def _clean_text(value: str) -> str:
    text = unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _dedupe(items: List[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        text = _clean_text(item)
        if text and text not in result:
            result.append(text)
    return result


class PrototypeHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_stack: List[str] = []
        self._button_depth = 0
        self._button_buffer: List[str] = []
        self._link_stack: List[Dict[str, Any]] = []
        self._table_depth = 0
        self._table_headers: List[str] = []
        self._tables: List[Dict[str, Any]] = []
        self.visible_texts: List[str] = []
        self.buttons: List[str] = []
        self.inputs: List[str] = []
        self.links: List[Dict[str, str]] = []
        self.dialogs: List[str] = []
        self.tabs: List[str] = []
        self.messages: List[str] = []
        self.layout_sections: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        class_text = " ".join([attr_map.get("class", ""), attr_map.get("id", "")]).lower()
        role = attr_map.get("role", "").lower()

        if tag in {"script", "style"}:
            self._skip_stack.append(tag)
            return

        if tag == "title":
            self._in_title = True
            return

        if tag == "button":
            self._button_depth += 1
            self._button_buffer.append("")
        elif tag == "input":
            label = _clean_text(
                attr_map.get("placeholder")
                or attr_map.get("aria-label")
                or attr_map.get("name")
                or attr_map.get("value")
            )
            if label:
                self.inputs.append(label)
        elif tag == "a":
            self._link_stack.append({"href": attr_map.get("href", "").strip(), "text": ""})
        elif tag == "table":
            self._table_depth += 1
            self._table_headers = []
        elif tag == "th" and self._table_depth:
            self._table_headers.append("")

        if tag in {"section", "aside", "header", "main"}:
            section_name = _clean_text(attr_map.get("aria-label") or attr_map.get("title") or attr_map.get("id"))
            if section_name:
                self.layout_sections.append(section_name)

        if "dialog" in class_text or "modal" in class_text or role == "dialog":
            dialog_name = _clean_text(attr_map.get("title") or attr_map.get("aria-label") or attr_map.get("id"))
            if dialog_name:
                self.dialogs.append(dialog_name)

        if role == "tab" or "tab" in class_text:
            tab_name = _clean_text(attr_map.get("title") or attr_map.get("aria-label") or attr_map.get("id"))
            if tab_name:
                self.tabs.append(tab_name)

        if role in {"alert", "status"} or any(keyword in class_text for keyword in ("alert", "message", "error", "success", "warning", "tip")):
            name = _clean_text(attr_map.get("title") or attr_map.get("aria-label") or attr_map.get("id"))
            if name:
                self.messages.append(name)

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()
            return

        if tag == "title":
            self._in_title = False
            return

        if tag == "button" and self._button_depth:
            text = _clean_text(self._button_buffer.pop())
            self._button_depth -= 1
            if text:
                self.buttons.append(text)
        elif tag == "a" and self._link_stack:
            link = self._link_stack.pop()
            text = _clean_text(link["text"])
            if text or link["href"]:
                self.links.append({"label": text, "href": link["href"]})
        elif tag == "table" and self._table_depth:
            headers = _dedupe(self._table_headers)
            if headers:
                self._tables.append({"name": "表格", "columns": headers})
            self._table_depth -= 1
            self._table_headers = []

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = _clean_text(data)
        if not text:
            return

        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return

        self.visible_texts.append(text)

        if self._button_depth:
            self._button_buffer[-1] = f"{self._button_buffer[-1]} {text}".strip()
        if self._link_stack:
            self._link_stack[-1]["text"] = f"{self._link_stack[-1]['text']} {text}".strip()
        if self._table_depth and self._table_headers:
            self._table_headers[-1] = f"{self._table_headers[-1]} {text}".strip()

        if any(keyword in text for keyword in ("成功", "失败", "错误", "提示", "为空", "未查询到", "确认")):
            self.messages.append(text)

        if any(keyword in text for keyword in ("列表", "详情", "查询", "筛选", "表单", "弹窗", "分页")):
            self.layout_sections.append(text)

    def result(self) -> Dict[str, Any]:
        return {
            "title": _clean_text(self.title),
            "visible_texts": _dedupe(self.visible_texts),
            "buttons": _dedupe(self.buttons),
            "inputs": _dedupe(self.inputs),
            "tables": self._tables,
            "tabs": _dedupe(self.tabs),
            "dialogs": _dedupe(self.dialogs),
            "links": [
                {"label": _clean_text(item["label"]), "href": item["href"]}
                for item in self.links
                if _clean_text(item["label"]) or item["href"]
            ],
            "messages": _dedupe(self.messages),
            "layout_sections": _dedupe(self.layout_sections),
        }


def extract_dom_facts(html_text: str) -> Dict[str, Any]:
    parser = PrototypeHTMLParser()
    parser.feed(html_text)
    return parser.result()
