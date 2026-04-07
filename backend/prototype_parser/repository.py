"""Generated prototype repository and refresh logic."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import PrototypePageFact, PrototypePageIndexItem
from .package_scanner import iter_package_html_files, scan_prototype_packages
from .page_parser import parse_page

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FACTS_ROOT = REPO_ROOT / "project-facts"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).casefold()


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _package_signature(packages: List[Dict[str, Any]]) -> List[Tuple[str, str, str, str, int]]:
    return sorted(
        (
            item.get("package_id", ""),
            item.get("root_path", ""),
            item.get("entry_page", ""),
            item.get("fingerprint", ""),
            int(item.get("page_count", 0)),
        )
        for item in packages
    )


def _load_existing_generated(facts_root: Path) -> Optional[Dict[str, Any]]:
    generated_root = facts_root / "generated" / "prototypes"
    pages_dir = generated_root / "pages"
    packages_payload = _load_json(generated_root / "prototype-packages.json")
    page_index_payload = _load_json(generated_root / "page-index.json")
    if packages_payload is None or page_index_payload is None:
        return None

    page_facts: Dict[str, Any] = {}
    for item in page_index_payload.get("pages", []):
        page_id = item.get("id", "").strip()
        if not page_id:
            return None
        fact_path = pages_dir / f"{page_id}.json"
        fact = _load_json(fact_path)
        if fact is None:
            return None
        page_facts[page_id] = fact

    return {
        "packages": packages_payload,
        "page_index": page_index_payload,
        "page_facts": page_facts,
    }


def _generated_is_current(
    facts_root: Path,
    manifests: List[Dict[str, Any]],
) -> bool:
    existing = _load_existing_generated(facts_root)
    if existing is None:
        return False

    existing_packages = existing["packages"].get("packages", [])
    if _package_signature(existing_packages) != _package_signature(manifests):
        return False

    page_index = existing["page_index"].get("pages", [])
    expected_page_count = sum(int(item.get("page_count", 0)) for item in manifests)
    if len(page_index) != expected_page_count:
        return False

    page_ids = {item.get("id", "") for item in page_index if item.get("id")}
    if page_ids != set(existing["page_facts"].keys()):
        return False
    return True


def _rebuild_generated_prototypes(facts_root: Path, manifests: List[Dict[str, Any]]) -> Dict[str, Any]:
    facts_root = Path(facts_root).resolve()
    prototypes_root = facts_root / "prototypes"
    generated_root = facts_root / "generated" / "prototypes"
    pages_dir = generated_root / "pages"
    prototypes_root.mkdir(parents=True, exist_ok=True)
    generated_root.mkdir(parents=True, exist_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)

    page_items: List[PrototypePageIndexItem] = []
    page_facts: Dict[str, PrototypePageFact] = {}

    for manifest in manifests:
        package_root = facts_root / manifest["root_path"]
        for html_file in iter_package_html_files(package_root, prototypes_root):
            if html_file.name.lower() == "index.html":
                continue
            index_item, fact = parse_page(
                html_file,
                package_id=manifest["package_id"],
                prototypes_root=prototypes_root,
            )
            page_items.append(index_item)
            page_facts[index_item.page_id] = fact
            (pages_dir / f"{index_item.page_id}.json").write_text(
                json.dumps(fact.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    packages_payload = {"packages": manifests}
    page_index_payload = {
        "pages": [
            {
                "id": item.page_id,
                "name": item.page_name,
                "title": item.title,
                "package_id": item.package_id,
                "path": item.relative_path,
                "source_path": item.source_path,
                "outgoing_page_ids": item.outgoing_page_ids,
                "aliases": item.aliases,
            }
            for item in page_items
        ]
    }

    (generated_root / "prototype-packages.json").write_text(
        json.dumps(packages_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (generated_root / "page-index.json").write_text(
        json.dumps(page_index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    # Compatibility with existing views/tests.
    (prototypes_root / "page-index.json").write_text(
        json.dumps(page_index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "packages": packages_payload,
        "page_index": page_index_payload,
        "page_facts": {page_id: fact.to_dict() for page_id, fact in page_facts.items()},
    }


def build_generated_prototypes(facts_root: Path) -> Dict[str, Any]:
    facts_root = Path(facts_root).resolve()
    prototypes_root = facts_root / "prototypes"
    manifests = [item.to_dict() for item in scan_prototype_packages(prototypes_root)]
    if _generated_is_current(facts_root, manifests):
        cached = _load_existing_generated(facts_root)
        if cached is not None:
            return cached
    return _rebuild_generated_prototypes(facts_root, manifests)


class PrototypeRepository:
    def __init__(self, facts_root: str | Path = DEFAULT_FACTS_ROOT):
        self.facts_root = Path(facts_root).resolve()
        self.generated = build_generated_prototypes(self.facts_root)

    @property
    def pages(self) -> List[Dict[str, Any]]:
        return self.generated["page_index"]["pages"]

    @property
    def packages(self) -> List[Dict[str, Any]]:
        return self.generated["packages"]["packages"]

    def resolve_page_reference(self, page_ref: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        raw = (page_ref or "").strip()
        if not raw:
            return None, []

        normalized = _normalize(raw)
        exact_matches: List[Dict[str, Any]] = []
        fuzzy_matches: List[Dict[str, Any]] = []
        for page in self.pages:
            candidates = [
                page.get("id", ""),
                page.get("name", ""),
                page.get("title", ""),
                page.get("path", ""),
                *(page.get("aliases", []) or []),
            ]
            normalized_candidates = {_normalize(value) for value in candidates if _normalize(value)}
            if normalized in normalized_candidates:
                exact_matches.append(page)
                continue
            if any(candidate and candidate in normalized for candidate in normalized_candidates):
                fuzzy_matches.append(page)

        if len(exact_matches) == 1:
            return exact_matches[0]["id"], []
        if len(exact_matches) > 1:
            return None, exact_matches
        if len(fuzzy_matches) == 1:
            return fuzzy_matches[0]["id"], []
        if len(fuzzy_matches) > 1:
            return None, fuzzy_matches
        return None, []

    def get_page(self, page_ref: str) -> Optional[Dict[str, Any]]:
        page_id, candidates = self.resolve_page_reference(page_ref)
        if candidates or not page_id:
            return None
        fact_path = self.facts_root / "generated" / "prototypes" / "pages" / f"{page_id}.json"
        if not fact_path.exists():
            return None
        return json.loads(fact_path.read_text(encoding="utf-8"))
