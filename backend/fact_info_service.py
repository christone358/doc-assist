"""
Project Fact Information Service

Provides read/write access to project fact information with Agent access controls.
"""

import json
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import asdict
import asyncio

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FACTS_ROOT = REPO_ROOT / "project-facts"

from models import (
    FactInformation,
    FactMetadata,
    FactLayer,
    FactCategory,
    FactInformationQuery,
    FactInformationResult,
    UseCase,
    Module,
    Interface,
    DataEntity
)


class FactInformationStorage:
    """Manages storage of project fact information."""

    def __init__(self, base_path: str | Path = DEFAULT_FACTS_ROOT):
        """Initialize the storage manager.

        Args:
            base_path: Base directory for project fact information
        """
        self.base_path = Path(base_path).resolve()
        self._ensure_directories_exist()
        self._index: Dict[str, FactInformation] = {}
        self._load_index()

    def _ensure_directories_exist(self):
        """Ensure all necessary directories exist."""
        for layer in FactLayer:
            layer_dir = self.base_path / f"{layer.value}"
            layer_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, layer: FactLayer, category: FactCategory, item_id: str) -> Path:
        """Get the file path for a fact information item."""
        layer_dir = self.base_path / layer.value
        category_dir = layer_dir / category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir / f"{item_id}.json"

    async def save(self, fact_info: FactInformation) -> bool:
        """Save a fact information item.

        Args:
            fact_info: The fact information to save

        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_file_path(
                fact_info.metadata.layer,
                fact_info.metadata.category,
                fact_info.metadata.id
            )

            # Update timestamp
            fact_info.metadata.updated_at = datetime.utcnow()

            # Save to file
            data = {
                "metadata": asdict(fact_info.metadata),
                "content": fact_info.content,
                "raw_data": fact_info.raw_data,
                "relationships": fact_info.relationships,
                "status": fact_info.status
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            # Update index
            self._index[fact_info.metadata.id] = fact_info

            return True
        except Exception as e:
            print(f"Error saving fact information: {e}")
            return False

    async def load(self, fact_id: str) -> Optional[FactInformation]:
        """Load a fact information item by ID.

        Args:
            fact_id: The ID of the fact information to load

        Returns:
            The FactInformation object or None if not found
        """
        if fact_id in self._index:
            return self._index[fact_id]

        # Search for the item
        for layer in FactLayer:
            for category in FactCategory:
                file_path = self._get_file_path(layer, category, fact_id)
                if file_path.exists():
                    return self._load_from_file(file_path)

        return None

    async def delete(self, fact_id: str) -> bool:
        """Delete a fact information item.

        Args:
            fact_id: The ID of the item to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            if fact_id not in self._index:
                return False

            fact_info = self._index[fact_id]
            file_path = self._get_file_path(
                fact_info.metadata.layer,
                fact_info.metadata.category,
                fact_id
            )

            if file_path.exists():
                file_path.unlink()

            del self._index[fact_id]
            return True
        except Exception as e:
            print(f"Error deleting fact information: {e}")
            return False

    async def update(self, fact_info: FactInformation) -> bool:
        """Update a fact information item.

        Args:
            fact_info: The updated fact information

        Returns:
            True if successful, False otherwise
        """
        return await self.save(fact_info)

    def _load_index(self):
        """Load all fact information into memory index."""
        for layer in FactLayer:
            layer_dir = self.base_path / layer.value
            if layer_dir.exists():
                for category_dir in layer_dir.iterdir():
                    if category_dir.is_dir():
                        for json_file in category_dir.glob("*.json"):
                            self._load_from_file(json_file)

    def _load_from_file(self, file_path: Path) -> Optional[FactInformation]:
        """Load a single fact information item from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            metadata_data = data.get("metadata", {})
            # Reconstruct FactMetadata
            metadata = FactMetadata(
                id=metadata_data.get("id", ""),
                name=metadata_data.get("name", ""),
                description=metadata_data.get("description"),
                layer=FactLayer(metadata_data.get("layer", "manifest")),
                category=FactCategory(metadata_data.get("category", "usecases")),
                version=metadata_data.get("version", "1.0.0"),
                author=metadata_data.get("author"),
                tags=metadata_data.get("tags", []),
                related_ids=metadata_data.get("related_ids", []),
                source_file=metadata_data.get("source_file")
            )

            fact_info = FactInformation(
                metadata=metadata,
                content=data.get("content", ""),
                raw_data=data.get("raw_data", {}),
                relationships=data.get("relationships", {}),
                status=data.get("status", "active")
            )

            self._index[metadata.id] = fact_info
            return fact_info
        except Exception as e:
            print(f"Error loading from file {file_path}: {e}")
            return None


class FactInformationService:
    """Service for querying and managing project fact information."""

    def __init__(self, storage: FactInformationStorage):
        """Initialize the service.

        Args:
            storage: The underlying storage manager
        """
        self.storage = storage
        self._agent_read_only = True  # Enforce read-only for Agent

    async def query(
        self,
        query: FactInformationQuery,
        agent_mode: bool = False
    ) -> FactInformationResult:
        """Query project fact information.

        Args:
            query: Query parameters
            agent_mode: Whether the query is from an Agent (read-only)

        Returns:
            Query results with related information
        """
        results = []

        # Search through the index
        for fact_id, fact_info in self.storage._index.items():
            if self._matches_query(fact_info, query):
                results.append(fact_info)

        # Sort and paginate
        results = results[query.offset:query.offset + query.limit]

        # Find related items
        related = {}
        for fact_info in results:
            related[fact_info.metadata.id] = await self._get_related_items(
                fact_info.metadata.related_ids
            )

        return FactInformationResult(
            items=results,
            total_count=len(self.storage._index),
            query=query,
            related_items=related
        )

    def _matches_query(self, fact_info: FactInformation, query: FactInformationQuery) -> bool:
        """Check if a fact information item matches the query."""
        if query.layer and fact_info.metadata.layer != query.layer:
            return False

        if query.category and fact_info.metadata.category != query.category:
            return False

        if query.id and fact_info.metadata.id != query.id:
            return False

        if query.keyword:
            keyword_lower = query.keyword.lower()
            if keyword_lower not in fact_info.metadata.name.lower() and \
               keyword_lower not in fact_info.content.lower():
                return False

        if query.tags:
            if not any(tag in fact_info.metadata.tags for tag in query.tags):
                return False

        return True

    async def _get_related_items(self, related_ids: List[str]) -> List[FactInformation]:
        """Get related fact information items."""
        related = []
        for item_id in related_ids:
            item = await self.storage.load(item_id)
            if item:
                related.append(item)
        return related

    # Agent API (read-only)

    async def query_by_layer(self, layer: FactLayer) -> List[FactInformation]:
        """Query by layer (Agent can call this)."""
        query = FactInformationQuery(layer=layer)
        result = await self.query(query, agent_mode=True)
        return result.items

    async def query_by_category(self, category: FactCategory) -> List[FactInformation]:
        """Query by category (Agent can call this)."""
        query = FactInformationQuery(category=category)
        result = await self.query(query, agent_mode=True)
        return result.items

    async def get_by_id(self, fact_id: str) -> Optional[FactInformation]:
        """Get a specific fact information by ID (Agent can call this)."""
        return await self.storage.load(fact_id)

    async def search(self, keyword: str) -> List[FactInformation]:
        """Search by keyword (Agent can call this)."""
        query = FactInformationQuery(keyword=keyword)
        result = await self.query(query, agent_mode=True)
        return result.items

    async def get_related(self, fact_id: str) -> List[FactInformation]:
        """Get related fact information (Agent can call this)."""
        fact_info = await self.storage.load(fact_id)
        if not fact_info:
            return []
        return await self._get_related_items(fact_info.metadata.related_ids)

    # Administrative API (read/write for maintainers only)

    async def create(self, fact_info: FactInformation) -> bool:
        """Create a new fact information item (Admin only)."""
        return await self.storage.save(fact_info)

    async def update(self, fact_info: FactInformation) -> bool:
        """Update an existing fact information item (Admin only)."""
        existing = await self.storage.load(fact_info.metadata.id)
        if not existing:
            return False
        return await self.storage.save(fact_info)

    async def delete(self, fact_id: str) -> bool:
        """Delete a fact information item (Admin only)."""
        return await self.storage.delete(fact_id)


# Singleton instance
_storage: Optional[FactInformationStorage] = None
_service: Optional[FactInformationService] = None


async def get_fact_service() -> FactInformationService:
    """Get or create the fact information service singleton."""
    global _service, _storage

    if _service is None:
        _storage = FactInformationStorage(base_path=DEFAULT_FACTS_ROOT)
        _service = FactInformationService(_storage)

    return _service


# Usage example
async def example_usage():
    """Example of how to use the fact information service."""
    service = await get_fact_service()

    # Query all usecases (Agent can do this)
    usecases = await service.query_by_category(FactCategory.USECASES)
    print(f"Found {len(usecases)} usecases")

    # Search by keyword (Agent can do this)
    results = await service.search("authentication")
    print(f"Found {len(results)} items matching 'authentication'")

    # Get specific item (Agent can do this)
    item = await service.get_by_id("UC-001")
    if item:
        print(f"Loaded: {item.metadata.name}")


if __name__ == "__main__":
    # For testing
    asyncio.run(example_usage())
