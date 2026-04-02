"""
Context Loader - Loads project facts context based on the module-archive fact store.
"""

import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from project_fact_modules import ModuleArchiveRepository

logger = logging.getLogger(__name__)

LEGACY_VOCAB_FILE_MAP = {
    "modules": "modules.md",
    "usecases": "usecases.md",
    "classes": "classes.md",
    "interfaces": "interfaces.md",
}

SECTION_VOCAB_MAP = {
    "description": "功能描述",
    "usecases": "用例信息",
    "function_points": "功能点",
    "apis": "API 清单",
    "classes": "包 / 类",
    "prototypes": "页面 / 原型",
    "dependencies": "依赖模块",
    "remarks": "备注",
}

VOCAB_ALIASES = {"interfaces": "apis"}


def load_context(vocab: str, module_id: Optional[str], facts_root: Path) -> List[str]:
    """
    Load context content for a given vocabulary type and module ID.

    Args:
        vocab: Supported values include:
            overviews: "systems", "subsystems", "modules",
                       "usecases", "function_points", "apis", "classes", "prototypes"
            details:   "module", "description", "usecases", "function_points", "apis",
                       "classes", "prototypes", "dependencies", "remarks"
            legacy alias: "interfaces" -> "apis"
        module_id: Target module ID (e.g., "mod-agent"). Required for filtered vocabs.
        facts_root: Path to the project-facts directory.

    Returns:
        List of content strings loaded (typically one item per file loaded).
    """
    requested_vocab = (vocab or "").strip().lower()
    normalized_vocab = _normalize_vocab(vocab)

    if normalized_vocab == "systems":
        return _load_systems(facts_root)
    elif normalized_vocab == "subsystems":
        return _load_subsystems(facts_root)
    elif normalized_vocab == "modules":
        return _load_modules(facts_root)
    elif normalized_vocab == "module":
        return _load_module_detail(module_id, facts_root)
    elif normalized_vocab in ("usecases", "function_points", "apis", "classes"):
        if module_id:
            results = _load_module_section(module_id, SECTION_VOCAB_MAP[normalized_vocab], facts_root)
            if results:
                return results
            if requested_vocab in ("usecases", "classes", "interfaces"):
                return _load_legacy_filtered(requested_vocab, module_id, facts_root)
            return []
        results = _load_relation_overview(normalized_vocab, facts_root, source_vocab=vocab)
        if results:
            return results
        if requested_vocab in ("usecases", "classes", "interfaces"):
            return _load_legacy_filtered(requested_vocab, None, facts_root)
        return []
    elif normalized_vocab == "prototypes":
        if module_id:
            return _load_prototype(module_id, facts_root)
        return _load_relation_overview("prototypes", facts_root, source_vocab=vocab)
    elif normalized_vocab in ("description", "dependencies", "remarks"):
        return _load_module_section(module_id, SECTION_VOCAB_MAP[normalized_vocab], facts_root)
    elif vocab in ("usecases", "classes", "interfaces"):
        return _load_legacy_filtered(vocab, module_id, facts_root)
    elif vocab == "prototypes":
        return _load_prototype(module_id, facts_root)
    else:
        logger.warning(f"Unknown vocabulary type: {vocab}")
        return []


def _normalize_vocab(vocab: str) -> str:
    normalized = (vocab or "").strip().lower()
    return VOCAB_ALIASES.get(normalized, normalized)


def _load_modules(facts_root: Path) -> List[str]:
    """Load generated module view or fallback modules.md in full."""
    ModuleArchiveRepository(facts_root)
    file_path = facts_root / "generated" / "views" / "modules.md"
    if not file_path.exists():
        file_path = facts_root / "modules.md"
    if not file_path.exists():
        logger.warning(f"modules.md not found at {file_path}")
        return []
    content = file_path.read_text(encoding="utf-8")
    logger.debug(f"Loaded modules.md ({len(content)} chars) from {file_path}")
    return [content]


def _load_systems(facts_root: Path) -> List[str]:
    repo = ModuleArchiveRepository(facts_root)
    grouped: dict[str, list] = defaultdict(list)
    for module in repo.archives:
        grouped[module.system or "待补充系统"].append(module)

    lines = ["# 系统概览"]
    for system_name, modules in grouped.items():
        subsystem_names = sorted(
            {
                module.subsystem
                for module in modules
                if module.subsystem
            }
        )
        module_names = "、".join(module.name for module in modules[:8])
        suffix = f" 等 {len(modules)} 个模块" if len(modules) > 8 else ""
        lines.extend([
            "",
            f"## {system_name}",
            f"- 模块数: {len(modules)}",
            f"- 子系统数: {len(subsystem_names)}",
        ])
        if subsystem_names:
            lines.append(f"- 子系统: {'、'.join(subsystem_names)}")
        if module_names:
            lines.append(f"- 模块: {module_names}{suffix}")

    return ["\n".join(lines).strip()]


def _load_subsystems(facts_root: Path) -> List[str]:
    repo = ModuleArchiveRepository(facts_root)
    grouped: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for module in repo.archives:
        system_name = module.system or "待补充系统"
        subsystem_name = module.subsystem or "未设置子系统"
        grouped[system_name][subsystem_name].append(module)

    lines = ["# 子系统概览"]
    for system_name, subsystem_map in grouped.items():
        lines.extend(["", f"## {system_name}"])
        for subsystem_name, modules in subsystem_map.items():
            module_names = "、".join(module.name for module in modules[:8])
            suffix = f" 等 {len(modules)} 个模块" if len(modules) > 8 else ""
            lines.extend([
                "",
                f"### {subsystem_name}",
                f"- 模块数: {len(modules)}",
            ])
            if module_names:
                lines.append(f"- 模块: {module_names}{suffix}")

    return ["\n".join(lines).strip()]


def _load_module_detail(module_id: Optional[str], facts_root: Path) -> List[str]:
    if module_id is None:
        logger.debug("Skipping module detail load: no module_id")
        return []

    ModuleArchiveRepository(facts_root)
    detail_file = facts_root / "generated" / "views" / "module-details" / f"{module_id}.md"
    if not detail_file.exists():
        logger.debug(f"Module detail file not found for module_id={module_id}")
        return []

    return [detail_file.read_text(encoding="utf-8")]


def _extract_section(content: str, section_title: str) -> str:
    match = re.search(
        rf"^##\s+{re.escape(section_title)}\s*$([\s\S]*?)(?=^##\s+|\Z)",
        content,
        re.MULTILINE,
    )
    if not match:
        return ""
    body = match.group(1).strip()
    if not body:
        return ""
    return f"## {section_title}\n{body}".strip()


def _load_module_section(module_id: Optional[str], section_title: str, facts_root: Path) -> List[str]:
    details = _load_module_detail(module_id, facts_root)
    if not details:
        return []

    section_content = _extract_section(details[0], section_title)
    return [section_content] if section_content else []


def _render_relation_overview_entry(module_name: str, module_id: str, lines: List[str]) -> List[str]:
    rendered = [f"## {module_name} {{#{module_id}}}"]
    rendered.extend(lines or ["- 待补充"])
    return rendered


def _load_relation_overview(vocab: str, facts_root: Path, source_vocab: str = "") -> List[str]:
    repo = ModuleArchiveRepository(facts_root)
    normalized_source = (source_vocab or vocab).strip().lower()
    legacy_source = normalized_source if normalized_source in LEGACY_VOCAB_FILE_MAP else ""

    lines = [f"# {_overview_title(vocab)}"]
    has_content = False

    for module in repo.archives:
        entry_lines: List[str] = []
        if vocab == "usecases":
            for row in module.usecases[:12]:
                name = row.get("用例", "").strip()
                if not name:
                    continue
                roles = row.get("参与角色", "").strip()
                desc = row.get("描述", "").strip()
                role_text = f" [{roles}]" if roles else ""
                suffix = f": {desc}" if desc else ""
                entry_lines.append(f"- {name}{role_text}{suffix}")
        elif vocab == "function_points":
            for row in module.function_points[:12]:
                submodule = row.get("子模块", "").strip()
                name = row.get("功能点", "").strip()
                if not name:
                    continue
                desc = row.get("描述", "").strip()
                prefix = f"[{submodule}] " if submodule else ""
                suffix = f": {desc}" if desc else ""
                entry_lines.append(f"- {prefix}{name}{suffix}")
        elif vocab == "apis":
            for row in module.apis[:12]:
                name = row.get("API 名称", "").strip()
                if not name:
                    continue
                method = row.get("方法", "").strip()
                path = row.get("路径", "").strip()
                desc = row.get("说明", "").strip()
                route = " ".join(part for part in [method, path] if part).strip()
                route_text = f" [{route}]" if route else ""
                suffix = f" - {desc}" if desc else ""
                entry_lines.append(f"- {name}{route_text}{suffix}")
        elif vocab == "classes":
            entry_lines = [f"- {item}" for item in module.packages_or_classes[:12] if item]
        elif vocab == "prototypes":
            for page in module.prototype_pages[:12]:
                if not page.get("name"):
                    continue
                path = page.get("path", "").strip()
                suffix = f" ({path})" if path else ""
                entry_lines.append(f"- {page['name']}{suffix}")

        if not entry_lines:
            continue

        has_content = True
        lines.extend(["", *_render_relation_overview_entry(module.name, module.module_id, entry_lines)])

    if has_content:
        return ["\n".join(lines).strip()]

    if legacy_source:
        return _load_legacy_filtered(legacy_source, None, facts_root)

    return []


def _overview_title(vocab: str) -> str:
    return {
        "usecases": "用例概览",
        "function_points": "功能点概览",
        "apis": "API 概览",
        "classes": "包 / 类概览",
        "prototypes": "页面 / 原型概览",
    }.get(vocab, f"{vocab} 概览")


def _load_legacy_filtered(vocab: str, module_id: Optional[str], facts_root: Path) -> List[str]:
    """Fallback loader for legacy flat markdown files."""
    file_name = LEGACY_VOCAB_FILE_MAP[vocab]
    file_path = facts_root / file_name

    if not file_path.exists():
        logger.warning(f"{file_name} not found at {file_path}")
        return []

    content = file_path.read_text(encoding="utf-8")

    if module_id is None:
        logger.debug(f"Loaded {file_name} in full (no module_id filter)")
        return [content]

    # Split into entries at heading level 3 (###)
    # Each entry starts with a ### heading
    entries = re.split(r"(?=^### )", content, flags=re.MULTILINE)

    matched = []
    for entry in entries:
        # Accept Markdown emphasis around the field name, for example:
        # "- **模块**: mod-llm" or "模块: mod-llm".
        pattern = rf"(?:\*\*)?\s*模块\s*(?:\*\*)?\s*[：:]\s*{re.escape(module_id)}\b"
        if re.search(pattern, entry, re.IGNORECASE):
            matched.append(entry.strip())

    if not matched:
        logger.debug(f"No entries in {file_name} matched module_id={module_id}")
        return []

    result = "\n\n".join(matched)
    logger.debug(
        f"Loaded {len(matched)} entries from {file_name} for module_id={module_id}"
    )
    return [result]


def _load_prototype(module_id: Optional[str], facts_root: Path) -> List[str]:
    """
    Load prototype file by convention: prototypes/{module_id}.*

    Searches for any file matching the module ID in the prototypes directory.
    """
    if module_id is None:
        logger.debug("Skipping prototypes load: no module_id")
        return []

    section_content = _load_module_section(module_id, "页面 / 原型", facts_root)
    if section_content:
        return section_content

    prototypes_dir = facts_root / "prototypes"
    if not prototypes_dir.exists():
        logger.debug(f"prototypes/ directory not found at {prototypes_dir}")
        return []

    # Find any file matching the module_id prefix
    matches = list(prototypes_dir.glob(f"{module_id}.*"))
    if not matches:
        logger.debug(f"No prototype file found for module_id={module_id}")
        return []

    # Use the first match (there should normally be only one)
    proto_file = matches[0]
    content = proto_file.read_text(encoding="utf-8")
    logger.debug(
        f"Loaded prototype {proto_file.name} ({len(content)} chars) for module_id={module_id}"
    )
    return [content]


def resolve_module_id(
    user_message: str,
    modules_md_content: str,
) -> tuple[Optional[str], dict]:
    """
    Try to resolve target module ID from user message via exact string match.

    Returns:
        (module_id, module_map) — module_id is None if no exact match found.
        module_map is always returned so the caller can use it for LLM fallback.
    """
    module_map = _parse_module_map(modules_md_content)

    if not module_map:
        logger.warning("No modules parsed from modules.md")
        return None, {}

    normalized_message = re.sub(r"\s+", "", user_message).casefold()

    for name, mod_id in module_map.items():
        normalized_name = re.sub(r"\s+", "", name).casefold()
        if name in user_message or (normalized_name and normalized_name in normalized_message):
            logger.info(f"Module resolved via exact match: {name} -> {mod_id}")
            return mod_id, module_map

    logger.info("Exact string match failed, LLM fallback needed")
    return None, module_map


def _parse_module_map(modules_md_content: str) -> dict:
    module_map = {}
    pattern = r"^##\s+(.+?)\s+\{#([^}]+)\}\s*$"
    matches = list(re.finditer(pattern, modules_md_content, re.MULTILINE))

    for idx, match in enumerate(matches):
        name = match.group(1).strip()
        mod_id = match.group(2).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(modules_md_content)
        section = modules_md_content[start:end]
        module_map[name] = mod_id

        alias_match = re.search(r"(?:\*\*别名\*\*|-+\s*别名)\s*[：:]\s*(.+)", section)
        if alias_match:
            for alias in re.split(r"[，,、；;\n]+", alias_match.group(1)):
                normalized = alias.strip()
                if normalized:
                    module_map[normalized] = mod_id

    logger.debug(f"Parsed {len(module_map)} modules from modules.md: {list(module_map.keys())}")
    return module_map
