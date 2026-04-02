"""
Skill Manager - Discovers, validates, loads and manages document writing skills.
"""

import logging
import re
from pathlib import Path
from typing import Optional, List, Dict

from agent.models import SkillInfo, SkillResourceInfo

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SKILLS_DIR = PROJECT_ROOT / "skills"

REQUIRED_METADATA_KEYS = {
    "name": ("name", "Skill Name"),
    "description": ("description", "Description"),
    "type": ("type", "Type"),
}
RESOURCE_CATEGORY_BY_DIR = {
    "scripts": "script",
    "templates": "template",
    "reference": "reference",
    "references": "reference",
}


class SkillLoader:
    """Parses and validates a single skill directory."""

    def __init__(self, skill_dir: Path):
        self.skill_dir = skill_dir
        self.skill_id = skill_dir.name

    def is_valid(self) -> bool:
        """Check that required files exist and metadata is complete."""
        skill_md = self._find_skill_md()
        if not skill_md:
            logger.warning(f"Skill '{self.skill_id}': missing skill.md")
            return False

        metadata = self._parse_metadata(skill_md)
        for key, aliases in REQUIRED_METADATA_KEYS.items():
            if self._get_metadata_value(metadata, *aliases) is None:
                logger.warning(
                    f"Skill '{self.skill_id}': missing required field '{key}' in skill.md"
                )
                return False

        return True

    def load(self) -> Optional[SkillInfo]:
        """Load and return SkillInfo from this directory."""
        skill_md = self._find_skill_md()
        if not skill_md:
            return None

        try:
            metadata = self._parse_metadata(skill_md)
            caps = self._parse_list_metadata(metadata, "capabilities", "Capabilities")
            resources = self._scan_resources(skill_md)

            return SkillInfo(
                id=self.skill_id,
                name=self._get_metadata_value(metadata, "name", "Skill Name", default=self.skill_id),
                description=self._get_metadata_value(metadata, "description", "Description", default=""),
                type=self._get_metadata_value(metadata, "type", "Type", default="general"),
                version=self._get_metadata_value(metadata, "version", "Version"),
                capabilities=caps,
                resources=resources,
                skill_md_path=str(skill_md),
            )

        except Exception as e:
            logger.error(f"Failed to load skill '{self.skill_id}': {e}")
            return None

    def _read_body(self, skill_md: Path) -> str:
        """Return the body of skill.md after the frontmatter block."""
        content = skill_md.read_text(encoding="utf-8")
        if content.startswith("---"):
            end = content.find("\n---", 3)
            if end != -1:
                return content[end + 4:].strip()
        # Legacy: strip first ```yaml...``` block
        stripped = re.sub(r"```yaml.*?```", "", content, count=1, flags=re.DOTALL).strip()
        return stripped

    def _find_skill_md(self) -> Optional[Path]:
        """Find skill.md (case-insensitive)."""
        for candidate in ["skill.md", "SKILL.md", "Skill.md"]:
            p = self.skill_dir / candidate
            if p.exists():
                return p
        return None

    def _parse_metadata(self, skill_md: Path) -> dict:
        """Parse metadata from YAML frontmatter (---) or fallback yaml code block."""
        content = skill_md.read_text(encoding="utf-8")

        # Primary: YAML frontmatter  ---\n...\n---
        if content.startswith("---"):
            end = content.find("\n---", 3)
            if end != -1:
                block = content[3:end].strip()
                return self._parse_simple_yaml(block)

        # Fallback: first ```yaml ... ``` block (legacy format)
        match = re.search(r"```yaml\s*\n(.*?)```", content, re.DOTALL)
        if not match:
            match = re.search(r"```\s*\n(.*?)```", content, re.DOTALL)
        if match:
            return self._parse_simple_yaml(match.group(1))

        return {}

    def _get_metadata_value(self, metadata: dict, *keys: str, default=None):
        for key in keys:
            if key in metadata:
                value = metadata[key]
                if isinstance(value, str):
                    value = value.strip()
                return value
        return default

    def _parse_list_metadata(self, metadata: dict, *keys: str) -> List[str]:
        raw = self._get_metadata_value(metadata, *keys, default=[])
        if isinstance(raw, str):
            return [item.strip() for item in raw.split(",") if item.strip()]
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return []

    def _scan_resources(self, skill_md: Path) -> List[SkillResourceInfo]:
        resources: List[SkillResourceInfo] = []
        for path in sorted(self.skill_dir.rglob("*")):
            if not path.is_file():
                continue

            rel_path = path.relative_to(self.skill_dir)
            rel_parts = rel_path.parts
            if any(part.startswith(".") for part in rel_parts):
                continue
            if path == skill_md:
                continue

            top_level = rel_parts[0] if rel_parts else ""
            category = RESOURCE_CATEGORY_BY_DIR.get(top_level, "other")
            resources.append(
                SkillResourceInfo(
                    category=category,
                    path=rel_path.as_posix(),
                    name=path.name,
                )
            )

        return resources

    def _parse_simple_yaml(self, text: str) -> dict:
        """Parse a simple YAML block (key: value, lists as `- item`)."""
        result = {}
        current_key = None
        current_list = None

        for line in text.splitlines():
            stripped = line.rstrip()

            if not stripped or stripped.startswith("#"):
                continue

            # List item
            if stripped.lstrip().startswith("- "):
                value = stripped.lstrip()[2:].strip()
                if current_key and current_list is not None:
                    current_list.append(value)
                continue

            # Key: value
            if ":" in stripped and not stripped.lstrip().startswith("-"):
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()

                if value == "":
                    # Start of a list
                    current_key = key
                    current_list = []
                    result[current_key] = current_list
                else:
                    current_key = key
                    current_list = None
                    result[key] = value

        return result


class SkillManager:
    """Manages all loaded skills."""

    def __init__(self, skills_dir: str | Path = DEFAULT_SKILLS_DIR):
        self.skills_dir = Path(skills_dir).resolve()
        self._skills: Dict[str, SkillInfo] = {}

    async def discover_and_load(self) -> None:
        """Scan skills directory and load all valid skills."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return

        loaded_count = 0
        failed_count = 0

        for entry in self.skills_dir.iterdir():
            # Skip hidden dirs and the _template directory
            if not entry.is_dir() or entry.name.startswith((".", "_")):
                continue

            loader = SkillLoader(entry)
            if not loader.is_valid():
                logger.warning(f"Skipping invalid skill: {entry.name}")
                failed_count += 1
                continue

            skill = loader.load()
            if skill:
                self._skills[skill.id] = skill
                loaded_count += 1
                logger.info(f"Loaded skill: {skill.name} ({skill.id})")
            else:
                failed_count += 1

        logger.info(
            f"Skill discovery complete: {loaded_count} loaded, {failed_count} failed"
        )

    async def get_all_skills(self) -> List[SkillInfo]:
        """Return all loaded skills."""
        return list(self._skills.values())

    async def get_skill(self, skill_id: str) -> Optional[SkillInfo]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    async def reload(self) -> None:
        """Reload all skills from disk."""
        self._skills.clear()
        await self.discover_and_load()

    def count(self) -> int:
        return len(self._skills)
