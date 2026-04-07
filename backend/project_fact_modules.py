"""
Module archive utilities for project facts.

This module implements the module-archive style fact store introduced by
the simplify-project-facts-maintenance change. Human maintainers edit the
module archive markdown files, while the system derives indexes and views
for browsing and agent loading.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prototype_parser import build_generated_prototypes

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS_ROOT = REPO_ROOT / "project-facts"


SECTION_TITLES = [
    "基本信息",
    "功能描述",
    "用例信息",
    "功能点",
    "API 清单",
    "页面 / 原型",
    "包 / 类",
    "依赖模块",
    "备注",
]


@dataclass
class ModuleArchive:
    module_id: str
    name: str
    system: str
    subsystem: str
    status: str
    aliases: List[str]
    description: str
    usecases: List[Dict[str, str]]
    function_points: List[Dict[str, str]]
    apis: List[Dict[str, str]]
    prototype_pages: List[Dict[str, str]]
    packages_or_classes: List[str]
    dependencies: List[str]
    remarks: str
    path: Path


def _normalize_function_points(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        normalized_rows.append(
            {
                "子模块": row.get("子模块", "").strip(),
                "功能点": row.get("功能点", "").strip(),
                "描述": row.get("描述", "").strip(),
                "状态": row.get("状态", "").strip(),
            }
        )
    return normalized_rows


def _normalize_usecases(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized_rows: List[Dict[str, str]] = []
    for row in rows:
        normalized_rows.append(
            {
                "用例": row.get("用例", row.get("用例名称", "")).strip(),
                "描述": row.get("描述", row.get("说明", "")).strip(),
                "参与角色": row.get("参与角色", row.get("角色", "")).strip(),
            }
        )
    return normalized_rows


def _extract_submodules(function_points: List[Dict[str, str]]) -> List[str]:
    seen: List[str] = []
    for row in function_points:
        submodule = row.get("子模块", "").strip()
        if submodule and submodule not in seen:
            seen.append(submodule)
    return seen


def safe_filename(name: str) -> str:
    text = name.strip().replace("/", "-").replace("\\", "-").replace(":", "：")
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\n", " ")
    return text[:120] or "未命名模块"


def _split_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _extract_title(text: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else "未命名模块"


def _parse_kv_bullets(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        item = stripped[1:].strip()
        if ":" not in item and "：" not in item:
            continue
        parts = re.split(r"[：:]", item, maxsplit=1)
        key = parts[0].strip()
        value = parts[1].strip()
        result[key] = value
    return result


def _split_aliases(value: str) -> List[str]:
    aliases = []
    for part in re.split(r"[，,、；;\n]+", value):
        alias = part.strip()
        if alias:
            aliases.append(alias)
    return aliases


def _normalize_identity(value: str) -> str:
    return re.sub(r"\s+", "", value.strip()).casefold()


def _normalize_subsystem(value: str) -> str:
    normalized = value.strip()
    if normalized in {"无", "无子系统", "未设置", "N/A", "n/a"}:
        return ""
    return normalized


def _parse_markdown_table(text: str) -> List[Dict[str, str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or "|" not in lines[0]:
        return []

    headers = [col.strip() for col in lines[0].strip("|").split("|")]
    data_rows: List[Dict[str, str]] = []
    for line in lines[2:]:
        if "|" not in line:
            continue
        values = [col.strip() for col in line.strip("|").split("|")]
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        row = {headers[i]: values[i] for i in range(len(headers))}
        normalized_values = [value for value in row.values() if value]
        if normalized_values and not all(value == "待补充" for value in normalized_values):
            data_rows.append(row)
    return data_rows


def _parse_bullets(text: str) -> List[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            value = stripped[1:].strip()
            if value:
                items.append(value)
    return items


def _generate_module_id(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"mod-{digest}"


def scan_prototype_pages(prototypes_root: Path) -> List[Dict[str, str]]:
    facts_root = prototypes_root.parent
    generated = build_generated_prototypes(facts_root)
    pages: List[Dict[str, str]] = []
    for item in generated["page_index"]["pages"]:
        pages.append(
            {
                "name": item.get("name", ""),
                "path": item.get("path", ""),
                "title": item.get("title", ""),
                "id": item.get("id", ""),
                "package_id": item.get("package_id", ""),
            }
        )
    return pages


def parse_module_archive(
    path: Path,
    module_id: Optional[str] = None,
    prototype_index: Optional[Dict[str, str]] = None,
) -> ModuleArchive:
    text = path.read_text(encoding="utf-8")
    title = _extract_title(text)
    sections = _split_sections(text)
    basics = _parse_kv_bullets(sections.get("基本信息", ""))

    aliases = _split_aliases(basics.get("别名", ""))
    system = basics.get("所属系统", "")
    subsystem = _normalize_subsystem(basics.get("所属子系统", basics.get("子系统", "")))
    status = basics.get("模块状态", basics.get("状态", ""))
    description = sections.get("功能描述", "").strip()
    usecases = _normalize_usecases(_parse_markdown_table(sections.get("用例信息", "")))
    function_points = _normalize_function_points(_parse_markdown_table(sections.get("功能点", "")))
    apis = _parse_markdown_table(sections.get("API 清单", ""))
    pages = [{"name": item, "path": ""} for item in _parse_bullets(sections.get("页面 / 原型", ""))]

    if prototype_index:
        pages = [{"name": page["name"], "path": prototype_index.get(page["name"], "")} for page in pages]

    return ModuleArchive(
        module_id=module_id or _generate_module_id(title or path.as_posix()),
        name=title,
        system=system,
        subsystem=subsystem,
        status=status,
        aliases=aliases,
        description=description,
        usecases=usecases,
        function_points=function_points,
        apis=apis,
        prototype_pages=pages,
        packages_or_classes=_parse_bullets(sections.get("包 / 类", "")),
        dependencies=_parse_bullets(sections.get("依赖模块", "")),
        remarks=sections.get("备注", "").strip(),
        path=path,
    )


def _load_module_identity_registry(generated_dir: Path) -> List[Dict[str, Any]]:
    registry_path = generated_dir / "module-id-map.json"
    if not registry_path.exists():
        return []
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    modules = data.get("modules", [])
    return modules if isinstance(modules, list) else []


def _resolve_module_identity(
    facts_root: Path,
    generated_dir: Path,
    archive_paths: List[Path],
) -> Tuple[Dict[Path, str], List[Dict[str, Any]]]:
    existing_entries = _load_module_identity_registry(generated_dir)
    existing_by_path: Dict[str, Dict[str, Any]] = {}
    existing_by_key: Dict[str, Dict[str, Any]] = {}

    for entry in existing_entries:
        relative_path = str(entry.get("path", "")).strip()
        if relative_path:
            existing_by_path[relative_path] = entry

        keys = [entry.get("name", "")]
        keys.extend(entry.get("aliases", []) or [])
        for value in keys:
            normalized = _normalize_identity(str(value))
            if normalized and normalized not in existing_by_key:
                existing_by_key[normalized] = entry

    assigned: Dict[Path, str] = {}
    registry_entries: List[Dict[str, Any]] = []
    known_ids = {
        str(entry.get("id", "")).strip()
        for entry in existing_entries
        if str(entry.get("id", "")).strip()
    }
    assigned_ids: set[str] = set()

    for path in archive_paths:
        text = path.read_text(encoding="utf-8")
        title = _extract_title(text)
        sections = _split_sections(text)
        basics = _parse_kv_bullets(sections.get("基本信息", ""))
        aliases = _split_aliases(basics.get("别名", ""))
        relative_path = str(path.relative_to(facts_root))

        matched_entry = existing_by_path.get(relative_path)
        if matched_entry is None:
            identity_candidates = [title, *aliases]
            for candidate in identity_candidates:
                normalized = _normalize_identity(candidate)
                if normalized and normalized in existing_by_key:
                    matched_entry = existing_by_key[normalized]
                    break

        module_id = str(matched_entry.get("id", "")).strip() if matched_entry else ""
        if module_id and module_id in assigned_ids:
            module_id = ""
        if not module_id:
            seed = f"{title}\n{relative_path}"
            module_id = _generate_module_id(seed)
            suffix = 1
            while module_id in known_ids or module_id in assigned_ids:
                suffix += 1
                module_id = _generate_module_id(f"{seed}\n{suffix}")

        assigned_ids.add(module_id)
        assigned[path] = module_id
        registry_entries.append(
            {
                "id": module_id,
                "path": relative_path,
                "name": title,
                "aliases": aliases,
            }
        )

    registry_entries.sort(key=lambda item: item["path"])
    return assigned, registry_entries


def render_module_archive_markdown(module: ModuleArchive) -> str:
    lines = [
        f"# {module.name}",
        "",
        "## 基本信息",
        f"- 所属系统: {module.system or '待补充'}",
        f"- 所属子系统: {module.subsystem or '无'}",
    ]
    if module.aliases:
        lines.append(f"- 别名: {'、'.join(module.aliases)}")

    lines.extend([
        "",
        "## 功能描述",
        module.description or "待补充",
        "",
        "## 用例信息",
        "| 用例 | 描述 | 参与角色 |",
        "|---|---|---|",
    ])
    if module.usecases:
        for row in module.usecases:
            lines.append(
                f"| {row.get('用例', '')} | {row.get('描述', '')} | {row.get('参与角色', '')} |"
            )
    else:
        lines.append("_待补充_")

    lines.extend([
        "",
        "## 功能点",
        "| 子模块 | 功能点 | 描述 | 状态 |",
        "|---|---|---|---|",
    ])
    if module.function_points:
        for row in module.function_points:
            lines.append(
                f"| {row.get('子模块', '')} | {row.get('功能点', '')} | {row.get('描述', '')} | {row.get('状态', '')} |"
            )
    else:
        lines.append("_待补充_")

    lines.extend([
        "",
        "## API 清单",
        "| API 名称 | 说明 | 路径 | 方法 |",
        "|---|---|---|---|",
    ])
    if module.apis:
        for row in module.apis:
            lines.append(
                f"| {row.get('API 名称', '')} | {row.get('说明', '')} | {row.get('路径', '')} | {row.get('方法', '')} |"
            )
    else:
        lines.append("_待补充_")

    lines.extend(["", "## 页面 / 原型"])
    if module.prototype_pages:
        for page in module.prototype_pages:
            path = page.get("path", "").strip()
            suffix = f" ({path})" if path else "（待匹配原型）"
            lines.append(f"- {page['name']}{suffix}")
    else:
        lines.append("_待补充_")

    lines.extend(["", "## 包 / 类"])
    if module.packages_or_classes:
        for item in module.packages_or_classes:
            lines.append(f"- {item}")
    else:
        lines.append("_待补充_")

    lines.extend(["", "## 依赖模块"])
    if module.dependencies:
        for item in module.dependencies:
            lines.append(f"- {item}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 备注", module.remarks or "待补充", ""])
    return "\n".join(lines)


def render_module_view(module: ModuleArchive) -> str:
    lines = [
        f"## {module.name} {{#{module.module_id}}}",
        "",
        f"**描述**: {module.description or '待补充'}",
        "",
        f"**所属系统**: {module.system or '待补充'}",
        f"**所属子系统**: {module.subsystem or '无'}",
    ]
    if module.aliases:
        lines.append(f"**别名**: {'、'.join(module.aliases)}")

    lines.extend(["", "**关键功能点**:"])
    if module.function_points:
        for row in module.function_points[:6]:
            submodule = row.get("子模块", "").strip()
            name = row.get("功能点", "").strip() or "未命名功能点"
            desc = row.get("描述", "").strip()
            prefix = f"[{submodule}] " if submodule else ""
            suffix = f" - {desc}" if desc else ""
            lines.append(f"- {prefix}{name}{suffix}")
    else:
        lines.append("- 待补充")

    lines.extend(["", "**关联信息**:"])
    lines.append(f"- 用例数量: {len(module.usecases)}")
    lines.append(f"- 子模块数量: {len(_extract_submodules(module.function_points))}")
    lines.append(f"- API 数量: {len(module.apis)}")
    lines.append(f"- 页面数量: {len(module.prototype_pages)}")
    lines.append(f"- 包/类数量: {len(module.packages_or_classes)}")
    if module.dependencies:
        lines.append(f"- 依赖模块: {'、'.join(module.dependencies)}")
    return "\n".join(lines).rstrip()


def render_module_detail_view(module: ModuleArchive) -> str:
    return render_module_archive_markdown(module)


def build_module_relationships(module: ModuleArchive) -> Dict[str, List[str]]:
    return {
        "usecases": [row.get("用例", "") for row in module.usecases if row.get("用例")],
        "submodules": _extract_submodules(module.function_points),
        "function_points": [row.get("功能点", "") for row in module.function_points if row.get("功能点")],
        "apis": [row.get("API 名称", "") for row in module.apis if row.get("API 名称")],
        "prototype_pages": [page["name"] for page in module.prototype_pages if page["name"]],
        "packages_or_classes": [item for item in module.packages_or_classes if item],
        "dependencies": [item for item in module.dependencies if item],
    }


def ensure_generated_views(facts_root: Path) -> Dict[str, Any]:
    modules_dir = facts_root / "modules"
    generated_dir = facts_root / "generated"
    views_dir = generated_dir / "views"
    detail_dir = views_dir / "module-details"
    prototypes_root = facts_root / "prototypes"

    modules_dir.mkdir(parents=True, exist_ok=True)
    views_dir.mkdir(parents=True, exist_ok=True)
    detail_dir.mkdir(parents=True, exist_ok=True)
    prototypes_root.mkdir(parents=True, exist_ok=True)

    archive_paths = [
        path for path in sorted(modules_dir.glob("*.md"))
        if "模板" not in path.stem
    ]
    generated_prototypes = build_generated_prototypes(facts_root)
    prototype_pages = [
        {
            "name": item.get("name", ""),
            "path": item.get("path", ""),
            "title": item.get("title", ""),
            "id": item.get("id", ""),
            "package_id": item.get("package_id", ""),
        }
        for item in generated_prototypes["page_index"]["pages"]
    ]
    prototype_index = {page["name"]: page["path"] for page in prototype_pages}
    module_ids, identity_registry = _resolve_module_identity(facts_root, generated_dir, archive_paths)
    archives = [
        parse_module_archive(path, module_ids.get(path), prototype_index)
        for path in archive_paths
    ]

    module_index = {
        "modules": [
            {
                "id": module.module_id,
                "name": module.name,
                "system": module.system,
                "subsystem": module.subsystem,
                "status": module.status,
                "aliases": module.aliases,
                "description": module.description,
                "usecases": [row.get("用例", "") for row in module.usecases if row.get("用例")],
                "path": str(module.path.relative_to(facts_root)),
            }
            for module in archives
        ]
    }
    relation_index = {
        "modules": {
            module.module_id: build_module_relationships(module)
            for module in archives
        }
    }
    page_index = {"pages": prototype_pages}

    (generated_dir / "module-index.json").write_text(
        json.dumps(module_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (generated_dir / "module-id-map.json").write_text(
        json.dumps({"modules": identity_registry}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (generated_dir / "relation-index.json").write_text(
        json.dumps(relation_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    modules_md = "# 模块档案视图\n\n" + "\n\n---\n\n".join(render_module_view(module) for module in archives)
    (views_dir / "modules.md").write_text(modules_md.strip() + "\n", encoding="utf-8")

    for module in archives:
        (detail_dir / f"{module.module_id}.md").write_text(
            render_module_detail_view(module),
            encoding="utf-8",
        )

    return {
        "archives": archives,
        "module_index": module_index,
        "relation_index": relation_index,
        "page_index": page_index,
    }


class ModuleArchiveRepository:
    """Read module archives and keep generated views in sync."""

    def __init__(self, facts_root: str | Path = DEFAULT_FACTS_ROOT):
        self.facts_root = Path(facts_root).resolve()
        self.generated = ensure_generated_views(self.facts_root)

    @property
    def archives(self) -> List[ModuleArchive]:
        return self.generated["archives"]

    def list_modules(
        self,
        keyword: str = "",
        system: str = "",
        subsystem: str = "",
        status: str = "",
    ) -> List[Dict[str, Any]]:
        result = []
        keyword_lower = keyword.lower().strip()
        for module in self.archives:
            if system and module.system != system:
                continue
            if subsystem and module.subsystem != subsystem:
                continue
            if status and module.status != status:
                continue
            haystack = "\n".join(
                [
                    module.name,
                    module.system,
                    module.subsystem,
                    module.description,
                    " ".join(module.aliases),
                    " ".join(item.get("用例", "") for item in module.usecases),
                    " ".join(item.get("功能点", "") for item in module.function_points),
                    " ".join(item.get("API 名称", "") for item in module.apis),
                ]
            ).lower()
            if keyword_lower and keyword_lower not in haystack:
                continue
            result.append(
                {
                    "id": module.module_id,
                    "name": module.name,
                    "system": module.system,
                    "subsystem": module.subsystem,
                    "status": module.status,
                    "description": module.description,
                    "usecases": [row.get("用例", "") for row in module.usecases if row.get("用例")],
                    "submodules": _extract_submodules(module.function_points),
                    "counts": {
                        "usecases": len(module.usecases),
                        "submodules": len(_extract_submodules(module.function_points)),
                        "function_points": len(module.function_points),
                        "apis": len(module.apis),
                        "prototype_pages": len(module.prototype_pages),
                        "packages_or_classes": len(module.packages_or_classes),
                    },
                }
            )
        return result

    def get_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        for module in self.archives:
            if module.module_id != module_id:
                continue
            return {
                "id": module.module_id,
                "name": module.name,
                "system": module.system,
                "subsystem": module.subsystem,
                "status": module.status,
                "aliases": module.aliases,
                "description": module.description,
                "usecases": module.usecases,
                "submodules": _extract_submodules(module.function_points),
                "function_points": module.function_points,
                "apis": module.apis,
                "prototype_pages": module.prototype_pages,
                "packages_or_classes": module.packages_or_classes,
                "dependencies": module.dependencies,
                "remarks": module.remarks,
                "content": render_module_detail_view(module),
                "path": str(module.path.relative_to(self.facts_root)),
            }
        return None

    def get_module_map(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for module in self.archives:
            mapping[module.name] = module.module_id
            for alias in module.aliases:
                mapping[alias] = module.module_id
        return mapping

    def resolve_module_reference(self, reference: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Resolve a human-readable module reference to a stable module ID.

        Supported references:
        - module_id (e.g. mod-xxxx)
        - module name
        - module alias
        - strings containing an embedded module_id, such as "模块名(mod-xxxx)"

        Returns:
            (resolved_module_id, candidates)
            - resolved_module_id: resolved stable ID when unique
            - candidates: ambiguous candidates when multiple modules match
        """
        raw = (reference or "").strip()
        if not raw:
            return None, []

        embedded_id = re.search(r"\bmod-[0-9a-f]{12}\b", raw)
        if embedded_id:
            module_id = embedded_id.group(0)
            if self.get_module(module_id):
                return module_id, []

        if self.get_module(raw):
            return raw, []

        variants = [raw]
        for part in re.split(r"[／/]+", raw):
            stripped = part.strip()
            if stripped:
                variants.append(stripped)
        expanded_variants: List[str] = []
        for variant in variants:
            stripped = variant.strip()
            if not stripped:
                continue
            expanded_variants.append(stripped)
            if stripped.endswith("模块") and len(stripped) > 2:
                expanded_variants.append(stripped[:-2].strip())

        raw_normalized = _normalize_identity(raw)
        system_hits = {
            _normalize_identity(module.system): module.system
            for module in self.archives
            if module.system and _normalize_identity(module.system) in raw_normalized
        }
        subsystem_hits = {
            _normalize_identity(module.subsystem): module.subsystem
            for module in self.archives
            if module.subsystem and _normalize_identity(module.subsystem) in raw_normalized
        }

        normalized_variants = {
            _normalize_identity(value)
            for value in expanded_variants
            if _normalize_identity(value)
        }

        def collect_matches(match_mode: str) -> List[ModuleArchive]:
            matched_modules: List[ModuleArchive] = []
            seen_ids: set[str] = set()
            for module in self.archives:
                names = [module.name, *module.aliases]
                for name in names:
                    normalized_name = _normalize_identity(name)
                    if not normalized_name:
                        continue
                    if match_mode == "exact":
                        matched = normalized_name in normalized_variants
                    else:
                        matched = normalized_name in raw_normalized
                    if not matched:
                        continue
                    if module.module_id not in seen_ids:
                        matched_modules.append(module)
                        seen_ids.add(module.module_id)
                    break
            return matched_modules

        def apply_scope_filters(modules: List[ModuleArchive]) -> List[ModuleArchive]:
            filtered = modules
            if system_hits:
                scoped = [
                    module for module in filtered
                    if _normalize_identity(module.system) in system_hits
                ]
                if scoped:
                    filtered = scoped
            if subsystem_hits:
                scoped = [
                    module for module in filtered
                    if _normalize_identity(module.subsystem) in subsystem_hits
                ]
                if scoped:
                    filtered = scoped
            return filtered

        matched_modules = collect_matches("exact")
        matched_modules = apply_scope_filters(matched_modules)
        if not matched_modules:
            matched_modules = collect_matches("contains")
            matched_modules = apply_scope_filters(matched_modules)

        if len(matched_modules) == 1:
            return matched_modules[0].module_id, []

        if len(matched_modules) > 1:
            return None, [
                {
                    "id": module.module_id,
                    "name": module.name,
                    "system": module.system,
                    "subsystem": module.subsystem,
                }
                for module in matched_modules
            ]

        return None, []
