#!/usr/bin/env python3
"""Migrate existing project facts into module archive markdown files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.project_fact_modules import (
    ModuleArchive,
    ensure_generated_views,
    render_module_archive_markdown,
    safe_filename,
)


def build_archive_path(root: Path, system: str, subsystem: str, name: str) -> Path:
    parts = [system]
    if subsystem:
        parts.append(subsystem)
    parts.append(name)
    return root / "modules" / f"{safe_filename('-'.join(part for part in parts if part))}.md"


def parse_legacy_modules(root: Path) -> List[ModuleArchive]:
    modules_md = root / "modules.md"
    usecases_md = root / "usecases.md"
    if not modules_md.exists():
        return []

    modules_text = modules_md.read_text(encoding="utf-8")
    usecases_text = usecases_md.read_text(encoding="utf-8") if usecases_md.exists() else ""
    entries = re.split(r"(?=^## )", modules_text, flags=re.MULTILINE)
    migrated: List[ModuleArchive] = []

    for entry in entries:
        heading = re.search(r"^##\s+(.+?)\s+\{#([^}]+)\}", entry, re.MULTILINE)
        if not heading:
            continue
        name = heading.group(1).strip()
        module_tag = heading.group(2).strip()
        description_match = re.search(r"\*\*描述\*\*:\s*(.+)", entry)
        description = description_match.group(1).strip() if description_match else ""

        features: List[Dict[str, str]] = []
        feature_block = re.search(r"\*\*关键特性\*\*:\s*(.+?)(?:\n\n|\Z)", entry, re.S)
        if feature_block:
            for line in feature_block.group(1).splitlines():
                stripped = line.strip()
                if stripped.startswith("-"):
                    features.append(
                        {
                            "功能点": stripped[1:].strip(),
                            "描述": "",
                            "状态": "",
                        }
                    )

        dependencies = []
        api_rows: List[Dict[str, str]] = []
        for match in re.finditer(
            r"###\s+(.+?)\n- \*\*模块\*\*:\s*" + re.escape(module_tag) + r"\n- \*\*方法\*\*:\s*(.+?)\n- \*\*路径\*\*:\s*(.+?)\n- \*\*描述\*\*:\s*(.+)",
            (root / "interfaces.md").read_text(encoding="utf-8") if (root / "interfaces.md").exists() else "",
            re.MULTILINE,
        ):
            api_rows.append(
                {
                    "API 名称": match.group(1).strip(),
                    "说明": match.group(4).strip(),
                    "路径": match.group(3).strip(),
                    "方法": match.group(2).strip(),
                }
            )

        for _uc in re.finditer(
            r"###\s+(UC-\d+):\s+(.+?)\n- \*\*模块\*\*:\s*" + re.escape(module_tag),
            usecases_text,
            re.MULTILINE,
        ):
            pass

        migrated.append(
            ModuleArchive(
                module_id=f"legacy-{module_tag}",
                name=name,
                system="NextAgent Doc Assistant",
                subsystem="",
                status="active",
                aliases=[],
                description=description,
                usecases=[],
                function_points=features,
                apis=api_rows,
                prototype_pages=[],
                packages_or_classes=[],
                dependencies=dependencies,
                remarks=f"由旧版 modules.md 迁移（来源标签: {module_tag}）",
                path=build_archive_path(root, "NextAgent Doc Assistant", "", name),
            )
        )

    return migrated


def parse_generated_json_modules(root: Path) -> List[ModuleArchive]:
    manifest_dir = root / "manifest" / "modules"
    feature_dir = root / "core" / "feature_descriptions"
    if not manifest_dir.exists():
        return []

    feature_lookup: Dict[str, Dict[str, object]] = {}
    for feature_file in feature_dir.glob("*.json"):
        data = json.loads(feature_file.read_text(encoding="utf-8"))
        feature_lookup[data["metadata"]["id"]] = data

    migrated: List[ModuleArchive] = []
    for module_file in sorted(manifest_dir.glob("*.json")):
        data = json.loads(module_file.read_text(encoding="utf-8"))
        raw = data.get("raw_data", {})
        feature_rows: List[Dict[str, str]] = []
        api_rows: List[Dict[str, str]] = []
        prototype_pages: List[Dict[str, str]] = []
        packages: List[str] = []
        remarks: List[str] = []

        for feature_id in raw.get("feature_ids", []):
            feature_data = feature_lookup.get(feature_id, {})
            feature_raw = feature_data.get("raw_data", {})
            feature_rows.append(
                {
                    "功能点": feature_raw.get("feature_name", ""),
                    "描述": feature_raw.get("description", ""),
                    "状态": "、".join(feature_raw.get("statuses", [])),
                }
            )
            for note in feature_raw.get("notes", []):
                if note:
                    remarks.append(note)

        name = raw.get("module_name") or data["metadata"]["name"].split("/")[-1].strip()
        system = raw.get("system_name", "")
        path = build_archive_path(root, system, "", name)

        migrated.append(
            ModuleArchive(
                module_id=data["metadata"]["id"],
                name=name,
                system=system,
                subsystem="",
                status="active",
                aliases=[],
                description=data["metadata"].get("description", ""),
                usecases=[],
                function_points=feature_rows,
                apis=api_rows,
                prototype_pages=prototype_pages,
                packages_or_classes=packages,
                dependencies=[],
                remarks="；".join(dict.fromkeys(remarks)) if remarks else "由结构化事实信息迁移",
                path=path,
            )
        )

    return migrated


def dedupe_modules(modules: List[ModuleArchive]) -> List[ModuleArchive]:
    seen = {}
    for module in modules:
        key = (module.system, module.name)
        seen[key] = module
    return list(seen.values())


def write_archives(root: Path, modules: List[ModuleArchive]) -> None:
    modules_dir = root / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    for module in modules:
        module.path.write_text(render_module_archive_markdown(module), encoding="utf-8")


def main() -> None:
    root = Path("project-facts").resolve()
    migrated = dedupe_modules(parse_generated_json_modules(root) + parse_legacy_modules(root))
    write_archives(root, migrated)
    ensure_generated_views(root)
    print(json.dumps({"migrated_modules": len(migrated)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
