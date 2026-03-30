"""
Context Loader - Loads project facts context based on vocabulary type and module ID.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Any

logger = logging.getLogger(__name__)

# Vocabulary to file path mapping
VOCAB_FILE_MAP = {
    "modules": "modules.md",
    "usecases": "usecases.md",
    "classes": "classes.md",
    "interfaces": "interfaces.md",
}


def load_context(vocab: str, module_id: Optional[str], facts_root: Path) -> List[str]:
    """
    Load context content for a given vocabulary type and module ID.

    Args:
        vocab: One of "modules", "usecases", "classes", "interfaces", "prototypes"
        module_id: Target module ID (e.g., "mod-agent"). Required for filtered vocabs.
        facts_root: Path to the project-facts directory.

    Returns:
        List of content strings loaded (typically one item per file loaded).
    """
    if vocab == "modules":
        return _load_modules(facts_root)
    elif vocab in ("usecases", "classes", "interfaces"):
        return _load_filtered(vocab, module_id, facts_root)
    elif vocab == "prototypes":
        return _load_prototype(module_id, facts_root)
    else:
        logger.warning(f"Unknown vocabulary type: {vocab}")
        return []


def _load_modules(facts_root: Path) -> List[str]:
    """Load modules.md in full."""
    file_path = facts_root / "modules.md"
    if not file_path.exists():
        logger.warning(f"modules.md not found at {file_path}")
        return []
    content = file_path.read_text(encoding="utf-8")
    logger.debug(f"Loaded modules.md ({len(content)} chars) from {file_path}")
    return [content]


def _load_filtered(vocab: str, module_id: Optional[str], facts_root: Path) -> List[str]:
    """
    Load a vocabulary file and filter entries by module ID tag.

    Each entry with '模块: {module_id}' (case-insensitive) is included.
    If module_id is None, returns the full file content.
    """
    file_name = VOCAB_FILE_MAP[vocab]
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

    for name, mod_id in module_map.items():
        if name in user_message:
            logger.info(f"Module resolved via exact match: {name} -> {mod_id}")
            return mod_id, module_map

    logger.info("Exact string match failed, LLM fallback needed")
    return None, module_map


def _parse_module_map(modules_md_content: str) -> dict:
    module_map = {}
    # Match headings with anchors: ## Some Name {#some-id}
    pattern = r"^##\s+(.+?)\s+\{#([^}]+)\}"
    for match in re.finditer(pattern, modules_md_content, re.MULTILINE):
        name = match.group(1).strip()
        mod_id = match.group(2).strip()
        module_map[name] = mod_id

    logger.debug(f"Parsed {len(module_map)} modules from modules.md: {list(module_map.keys())}")
    return module_map

