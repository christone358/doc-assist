"""Structured models for parsed prototype packages and pages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class PrototypePackageManifest:
    package_id: str
    package_name: str
    root_path: str
    entry_page: str
    fingerprint: str
    page_count: int
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PrototypePageIndexItem:
    page_id: str
    page_name: str
    title: str
    package_id: str
    source_path: str
    relative_path: str
    outgoing_page_ids: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PrototypePageFact:
    page_id: str
    page_name: str
    title: str
    source_path: str
    relative_path: str
    package_id: str
    layout_sections: List[str] = field(default_factory=list)
    elements: Dict[str, Any] = field(default_factory=dict)
    visible_texts: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    interactions: List[str] = field(default_factory=list)
    outgoing_links: List[Dict[str, str]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    parser_warnings: List[str] = field(default_factory=list)
    llm_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
