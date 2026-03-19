"""
Version Management and Access Control for Project Fact Information

Provides version tracking and access control for fact information items.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import hashlib

from models import FactInformation, FactMetadata


@dataclass
class VersionInfo:
    """Version information for a fact item."""
    version_number: str                    # v1.0.0
    timestamp: datetime
    author: Optional[str] = None
    change_summary: Optional[str] = None
    content_hash: str = ""                 # For change detection


class FactInformationVersionManager:
    """Manages versioning of fact information items."""

    def __init__(self, storage_path: str = "project-facts"):
        """Initialize the version manager.

        Args:
            storage_path: Base path for fact information storage
        """
        self.storage_path = Path(storage_path)
        self.versions_dir = self.storage_path / ".versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)

    def _get_version_dir(self, fact_id: str) -> Path:
        """Get the version directory for a fact item."""
        version_dir = self.versions_dir / fact_id
        version_dir.mkdir(parents=True, exist_ok=True)
        return version_dir

    def _get_version_file(self, fact_id: str, version: str) -> Path:
        """Get the file path for a specific version."""
        return self._get_version_dir(fact_id) / f"{version}.json"

    def _get_version_history_file(self, fact_id: str) -> Path:
        """Get the file path for version history."""
        return self._get_version_dir(fact_id) / "history.json"

    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    async def save_version(
        self,
        fact_info: FactInformation,
        author: Optional[str] = None,
        change_summary: Optional[str] = None
    ) -> bool:
        """Save a version of the fact information.

        Args:
            fact_info: The fact information to version
            author: Who made this change
            change_summary: Summary of what changed

        Returns:
            True if successful
        """
        try:
            fact_id = fact_info.metadata.id
            version = fact_info.metadata.version

            # Compute content hash
            content_hash = self._compute_content_hash(fact_info.content)

            # Create version info
            version_info = VersionInfo(
                version_number=version,
                timestamp=datetime.utcnow(),
                author=author,
                change_summary=change_summary,
                content_hash=content_hash
            )

            # Save versioned content
            version_file = self._get_version_file(fact_id, version)
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        "metadata": asdict(fact_info.metadata),
                        "content": fact_info.content,
                        "raw_data": fact_info.raw_data,
                        "relationships": fact_info.relationships,
                        "status": fact_info.status,
                        "version_info": asdict(version_info, dict_factory=str)
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str
                )

            # Update history
            await self._update_history(fact_id, version_info)

            return True
        except Exception as e:
            print(f"Error saving version: {e}")
            return False

    async def _update_history(self, fact_id: str, version_info: VersionInfo) -> None:
        """Update the version history for a fact item."""
        history_file = self._get_version_history_file(fact_id)

        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = {"fact_id": fact_id, "versions": []}

        history["versions"].append(asdict(version_info, dict_factory=str))
        history["last_updated"] = datetime.utcnow().isoformat()

        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False, default=str)

    async def get_version(self, fact_id: str, version: str) -> Optional[FactInformation]:
        """Get a specific version of a fact item.

        Args:
            fact_id: The fact item ID
            version: The version number (e.g., "1.0.0")

        Returns:
            The FactInformation at that version or None
        """
        version_file = self._get_version_file(fact_id, version)
        if not version_file.exists():
            return None

        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Reconstruct the object (simplified)
            return self._deserialize_fact_info(data)
        except Exception as e:
            print(f"Error loading version: {e}")
            return None

    async def get_version_history(self, fact_id: str) -> List[VersionInfo]:
        """Get the version history for a fact item.

        Args:
            fact_id: The fact item ID

        Returns:
            List of VersionInfo objects in chronological order
        """
        history_file = self._get_version_history_file(fact_id)
        if not history_file.exists():
            return []

        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)

            versions = []
            for v_data in history.get("versions", []):
                version_info = VersionInfo(
                    version_number=v_data.get("version_number", ""),
                    timestamp=datetime.fromisoformat(
                        v_data.get("timestamp", datetime.utcnow().isoformat())
                    ),
                    author=v_data.get("author"),
                    change_summary=v_data.get("change_summary"),
                    content_hash=v_data.get("content_hash", "")
                )
                versions.append(version_info)

            return versions
        except Exception as e:
            print(f"Error loading history: {e}")
            return []

    def _deserialize_fact_info(self, data: Dict[str, Any]) -> FactInformation:
        """Deserialize FactInformation from JSON data."""
        # This is a simplified implementation
        # In reality, you would reconstruct the full object with proper types
        metadata_data = data.get("metadata", {})
        return FactInformation(
            metadata=FactMetadata(
                id=metadata_data.get("id", ""),
                name=metadata_data.get("name", "")
            ),
            content=data.get("content", ""),
            raw_data=data.get("raw_data", {}),
            relationships=data.get("relationships", {}),
            status=data.get("status", "active")
        )


class AccessController:
    """Controls access to fact information based on user roles."""

    def __init__(self):
        """Initialize the access controller."""
        self.permissions = {
            "admin": ["read", "write", "delete", "admin"],
            "maintainer": ["read", "write"],
            "agent": ["read"],
            "viewer": ["read"]
        }

    def can_read(self, user_role: str) -> bool:
        """Check if user can read fact information."""
        return "read" in self.permissions.get(user_role, [])

    def can_write(self, user_role: str) -> bool:
        """Check if user can write/modify fact information."""
        return "write" in self.permissions.get(user_role, [])

    def can_delete(self, user_role: str) -> bool:
        """Check if user can delete fact information."""
        return "delete" in self.permissions.get(user_role, [])

    def can_admin(self, user_role: str) -> bool:
        """Check if user can perform admin operations."""
        return "admin" in self.permissions.get(user_role, [])

    def get_allowed_operations(self, user_role: str) -> List[str]:
        """Get list of allowed operations for a user."""
        return self.permissions.get(user_role, [])


# Sample data initialization
SAMPLE_PROJECT_FACTS = {
    "layer1_inventory": {
        "usecases": [
            {
                "id": "UC-001",
                "name": "Agent理解用户需求",
                "module": "Agent核心",
                "description": "Agent通过自然语言理解用户的文档编写需求",
                "status": "active"
            },
            {
                "id": "UC-002",
                "name": "调度合适的Skill",
                "module": "Agent核心",
                "description": "Agent根据需求调度合适的文档编写Skill",
                "status": "active"
            },
            {
                "id": "UC-003",
                "name": "生成文档",
                "module": "Skill执行",
                "description": "Skill生成用户所需的文档",
                "status": "active"
            },
            {
                "id": "UC-004",
                "name": "管理文档版本",
                "module": "版本管理",
                "description": "系统自动管理文档的版本和修改历史",
                "status": "active"
            },
            {
                "id": "UC-005",
                "name": "多轮对话交互",
                "module": "Web UI",
                "description": "用户与Agent进行多轮对话，逐步完善文档",
                "status": "active"
            }
        ],
        "modules": [
            {
                "id": "MOD-AGENT",
                "name": "Agent核心",
                "description": "负责理解用户需求并调度Skill",
                "submodules": ["MOD-NLU", "MOD-DISPATCH"],
                "tech_stack": ["Python", "FastAPI"]
            },
            {
                "id": "MOD-SKILL",
                "name": "Skill框架",
                "description": "定义和执行文档编写Skill",
                "submodules": [],
                "tech_stack": ["Python"]
            },
            {
                "id": "MOD-WEB",
                "name": "Web UI",
                "description": "用户交互界面",
                "submodules": [],
                "tech_stack": ["Svelte", "TypeScript"]
            }
        ],
        "users": [
            {
                "id": "ROLE-USER",
                "name": "普通用户",
                "description": "文档编写用户",
                "permissions": ["use_skill", "view_documents"]
            },
            {
                "id": "ROLE-ADMIN",
                "name": "管理员",
                "description": "系统管理员",
                "permissions": ["all"]
            }
        ],
        "risks": [
            {
                "id": "R-001",
                "title": "Skill质量问题",
                "severity": "high",
                "mitigation": "建立Skill验证机制和测试框架"
            },
            {
                "id": "R-002",
                "title": "LLM准确度不足",
                "severity": "medium",
                "mitigation": "优化提示词工程和使用更先进的模型"
            }
        ]
    }
}


async def initialize_sample_data(service) -> None:
    """Initialize sample project fact data for testing.

    Args:
        service: The FactInformationService instance
    """
    print("Initializing sample project fact data...")

    # This is a placeholder function
    # In production, you would load actual project data from files
    # For now, we just print a message indicating the function was called

    print("Sample data initialization would load data from project-facts/")
    print("Make sure to populate the project fact information manually")


if __name__ == "__main__":
    # Test the access controller
    ac = AccessController()
    print("Agent permissions:", ac.get_allowed_operations("agent"))
    print("Admin permissions:", ac.get_allowed_operations("admin"))
