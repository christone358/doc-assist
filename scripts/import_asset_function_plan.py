#!/usr/bin/env python3
"""Import the asset planning workbook into the project facts database.

The workbook is parsed without third-party dependencies so the import can run
in the current repository environment.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.project_fact_modules import (  # noqa: E402
    ModuleArchive,
    ensure_generated_views,
    render_module_archive_markdown,
    safe_filename,
)


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SOURCE_AUTHOR = "Codex"


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u200b", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    return text.strip()


def first_non_empty(record: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = normalize_text(record.get(key, ""))
        if value:
            return value
    return ""


def load_sheet_rows(workbook_path: Path) -> List[List[str]]:
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", NS):
                parts = [node.text or "" for node in item.iterfind(".//a:t", NS)]
                shared_strings.append("".join(parts))

        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.find("a:sheetData", NS):
            row_values: Dict[int, str] = defaultdict(str)
            for cell in row.findall("a:c", NS):
                ref = cell.attrib["r"]
                col_letters = re.match(r"([A-Z]+)", ref).group(1)
                col_num = 0
                for char in col_letters:
                    col_num = col_num * 26 + ord(char) - 64

                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", NS)
                value = ""
                if cell_type == "s" and value_node is not None:
                    value = shared_strings[int(value_node.text)]
                elif cell_type == "inlineStr":
                    inline = cell.find("a:is", NS)
                    if inline is not None:
                        value = "".join(
                            node.text or "" for node in inline.iterfind(".//a:t", NS)
                        )
                elif value_node is not None:
                    value = value_node.text or ""

                row_values[col_num] = normalize_text(value)

            max_col = max(row_values) if row_values else 0
            rows.append([row_values[i] for i in range(1, max_col + 1)])

    return rows


def rows_to_records(rows: List[List[str]]) -> List[Dict[str, str]]:
    if not rows:
        return []

    headers = list(rows[0])
    while headers and not headers[-1]:
        headers.pop()

    records = []
    for row in rows[1:]:
        if not any(normalize_text(cell) for cell in row):
            continue

        padded = list(row)
        if len(padded) < len(headers):
            padded.extend([""] * (len(headers) - len(padded)))

        record: Dict[str, str] = {}
        for index, cell in enumerate(padded):
            if index < len(headers):
                key = headers[index] or f"扩展列{index + 1}"
            else:
                key = f"备注{index - len(headers) + 1}"
            record[key] = normalize_text(cell)

        records.append(record)

    return records


def fill_hierarchy(records: List[Dict[str, str]]) -> List[Dict[str, str]]:
    filled = []
    current = {
        "系统名称": "",
        "子系统": "",
        "模块": "",
        "模块描述": "",
        "子模块": "",
    }

    for record in records:
        raw = {key: normalize_text(value) for key, value in record.items()}

        system_name = first_non_empty(raw, "系统名称")
        subsystem_name = first_non_empty(raw, "子系统", "一级功能")
        module_name = first_non_empty(raw, "模块", "二级功能")
        module_desc = first_non_empty(raw, "模块描述", "二级功能描述")
        submodule_name = first_non_empty(raw, "子模块", "三级功能")

        if system_name:
            current["系统名称"] = system_name
            current["子系统"] = ""
            current["模块"] = ""
            current["模块描述"] = ""
            current["子模块"] = ""

        if subsystem_name:
            current["子系统"] = subsystem_name
            current["模块"] = ""
            current["模块描述"] = ""
            current["子模块"] = ""

        if module_name:
            current["模块"] = module_name
            current["模块描述"] = module_desc
            current["子模块"] = ""
        elif module_desc:
            current["模块描述"] = module_desc

        if submodule_name:
            current["子模块"] = submodule_name

        merged = dict(raw)
        for key in current:
            merged[key] = merged.get(key) or current[key]

        filled.append(merged)

    return filled


def split_function_description(text: str) -> tuple[str, str]:
    normalized = normalize_text(text)
    if not normalized:
        return "", ""

    if "\n" in normalized:
        first_line, *rest = normalized.split("\n")
        return first_line.strip(), "\n".join(line.strip() for line in rest if line.strip())

    return normalized, ""


def build_module_archives(records: List[Dict[str, str]]) -> List[Dict[str, object]]:
    modules: List[Dict[str, object]] = []
    module_map: Dict[tuple[str, str, str], Dict[str, object]] = {}

    for row_index, record in enumerate(records, start=2):
        system_name = first_non_empty(record, "系统名称")
        subsystem_name = first_non_empty(record, "子系统", "一级功能")
        module_name = first_non_empty(record, "模块", "二级功能")
        module_desc = first_non_empty(record, "模块描述", "二级功能描述")
        submodule_name = first_non_empty(record, "子模块", "三级功能")
        function_raw = first_non_empty(record, "功能描述", "功能点")
        function_name, function_desc = split_function_description(function_raw)
        status = first_non_empty(record, "状态", "完成状态")
        notes = [value for key, value in record.items() if key.startswith("备注") and value]

        if not system_name or not module_name:
            continue

        key = (system_name, subsystem_name, module_name)
        module = module_map.get(key)
        if module is None:
            module = {
                "system_name": system_name,
                "subsystem_name": subsystem_name,
                "module_name": module_name,
                "description": module_desc,
                "function_points": [],
                "point_keys": set(),
                "notes": [],
                "source_rows": [],
            }
            module_map[key] = module
            modules.append(module)

        if module_desc and not module["description"]:
            module["description"] = module_desc
        for note in notes:
            if note not in module["notes"]:
                module["notes"].append(note)
        module["source_rows"].append(row_index)

        point_name = function_name
        if not point_name:
            continue

        point_key = (submodule_name, point_name, function_desc, status)
        if point_key in module["point_keys"]:
            continue
        module["point_keys"].add(point_key)
        module["function_points"].append(
            {
                "子模块": submodule_name,
                "功能点": point_name,
                "描述": function_desc,
                "状态": status,
            }
        )

    for module in modules:
        module.pop("point_keys", None)

    return modules


def write_summary(summary_path: Path, source_file: Path, modules: List[Dict[str, object]]) -> None:
    lines = [
        "# 资产功能规划模块总结",
        "",
        f"- 来源文件: `{source_file}`",
        f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 系统数: {len({module['system_name'] for module in modules})}",
        f"- 模块数: {len(modules)}",
        "",
    ]

    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for module in modules:
        grouped[module["system_name"]].append(module)

    for system_name, system_modules in grouped.items():
        lines.append(f"## {system_name}")
        lines.append("")
        for module in system_modules:
            lines.append(f"### {module['module_name']}")
            lines.append(f"- 模块描述: {module['description'] or '未提供描述'}")
            if module["subsystem_name"]:
                lines.append(f"- 所属子系统: {module['subsystem_name']}")
            lines.append(f"- 功能点数: {len(module['function_points'])}")
            if module["function_points"]:
                lines.append("- 功能点:")
                for point in module["function_points"]:
                    prefix = f"[{point['子模块']}] " if point["子模块"] else ""
                    detail = f": {point['描述']}" if point["描述"] else ""
                    status = f" ({point['状态']})" if point["状态"] else ""
                    lines.append(f"  - {prefix}{point['功能点']}{detail}{status}")
            lines.append("")

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_aggregate(output_path: Path, source_file: Path, modules: List[Dict[str, object]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": str(source_file),
        "modules": modules,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def module_file_path(
    facts_root: Path,
    system_name: str,
    module_name: str,
    subsystem_name: str = "",
) -> Path:
    name_parts = [system_name]
    if subsystem_name:
        name_parts.append(subsystem_name)
    name_parts.append(module_name)
    filename = safe_filename("-".join(part for part in name_parts if part))
    return facts_root / "modules" / f"{filename}.md"


def clean_existing_business_modules(facts_root: Path, system_names: List[str]) -> None:
    modules_dir = facts_root / "modules"
    if not modules_dir.exists():
        return

    for path in modules_dir.glob("*.md"):
        if "模板" in path.stem:
            continue
        text = path.read_text(encoding="utf-8")
        system_match = re.search(r"^- 所属系统:\s*(.+?)\s*$", text, re.MULTILINE)
        if system_match and system_match.group(1).strip() in system_names:
            path.unlink()


def write_module_archives(facts_root: Path, source_file: Path, modules: List[Dict[str, object]]) -> None:
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)

    for module in modules:
        remarks = [f"由资产功能规划导入，来源文件：{source_file.name}"]
        if module["subsystem_name"]:
            remarks.append(f"所属子系统：{module['subsystem_name']}")
        if module["notes"]:
            remarks.extend(module["notes"])
        archive = ModuleArchive(
            module_id="",
            name=module["module_name"],
            system=module["system_name"],
            subsystem=module["subsystem_name"],
            status="",
            aliases=[],
            description=module["description"],
            usecases=[],
            function_points=module["function_points"],
            apis=[],
            prototype_pages=[],
            packages_or_classes=[],
            dependencies=[],
            remarks="\n".join(remarks),
            path=module_file_path(
                facts_root,
                module["system_name"],
                module["module_name"],
                module["subsystem_name"],
            ),
        )
        archive.path.write_text(render_module_archive_markdown(archive), encoding="utf-8")


def generate_database(source_file: Path, facts_root: Path) -> Dict[str, int]:
    rows = load_sheet_rows(source_file)
    records = rows_to_records(rows)
    filled_records = fill_hierarchy(records)
    modules = build_module_archives(filled_records)
    generated_dir = facts_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    clean_existing_business_modules(
        facts_root,
        sorted({module["system_name"] for module in modules}),
    )
    write_module_archives(facts_root, source_file, modules)
    write_summary(generated_dir / "asset-function-module-summary.md", source_file, modules)
    write_aggregate(generated_dir / "asset-function-database.json", source_file, modules)
    ensure_generated_views(facts_root)

    return {
        "systems": len({module["system_name"] for module in modules}),
        "modules": len(modules),
        "function_points": sum(len(module["function_points"]) for module in modules),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import asset planning workbook into project facts")
    parser.add_argument("source", help="Path to the Excel workbook")
    parser.add_argument(
        "--facts-root",
        default="project-facts",
        help="Base directory of the fact database output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_file = Path(args.source).expanduser().resolve()
    facts_root = Path(args.facts_root).resolve()

    if not source_file.exists():
        raise SystemExit(f"Source file not found: {source_file}")

    stats = generate_database(source_file=source_file, facts_root=facts_root)
    print(
        "Imported workbook successfully:",
        json.dumps(stats, ensure_ascii=False),
    )


if __name__ == "__main__":
    main()
