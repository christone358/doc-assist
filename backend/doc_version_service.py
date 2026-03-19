"""
Document Version Management Service

Handles versioned storage of generated documents using the structure:
  docs/[doc_type]/[doc_name]/[YYYY-MM-DD]/v[X.Y.Z].md
"""

import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DOCS_ROOT = Path("docs")
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.md$")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VersionRef:
    """Points to a specific version of a document on disk."""
    doc_type: str
    doc_name: str
    date: str          # YYYY-MM-DD
    version: str       # e.g. "1.0.0"
    file_path: Path    # absolute path

    @property
    def relative_path(self) -> str:
        """Relative path from docs/ root, e.g. requirements/auth/2026-03-17/v1.0.0.md"""
        return str(self.file_path.relative_to(DOCS_ROOT))

    @property
    def version_tuple(self) -> Tuple[int, int, int]:
        parts = [int(x) for x in self.version.split(".")]
        return (parts[0], parts[1], parts[2])


@dataclass
class VersionMeta:
    """Metadata stored alongside each version file."""
    doc_type: str
    doc_name: str
    version: str
    date: str
    created_at: str            # ISO datetime
    conversation_id: Optional[str]
    round_id: Optional[int]
    change_summary: Optional[str]
    previous_version: Optional[str]   # e.g. "1.0.0"
    skill_id: Optional[str]


# ---------------------------------------------------------------------------
# Core service
# ---------------------------------------------------------------------------

class DocumentVersionService:
    """Creates, reads, and tracks versioned documents."""

    def __init__(self, docs_root: Path = DOCS_ROOT):
        self.docs_root = docs_root

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save_document(
        self,
        content: str,
        doc_type: str,
        doc_name: str,
        *,
        conversation_id: Optional[str] = None,
        round_id: Optional[int] = None,
        change_summary: Optional[str] = None,
        skill_id: Optional[str] = None,
        force_date: Optional[str] = None,   # override for testing
    ) -> VersionRef:
        """Save a document as the next version and return its VersionRef.

        Same-day saves increment the patch number (v1.0.0 → v1.0.1).
        Cross-day saves start at v1.0.0 in the new date directory.
        """
        today = force_date or datetime.now().strftime("%Y-%m-%d")
        date_dir = self._date_dir(doc_type, doc_name, today)
        date_dir.mkdir(parents=True, exist_ok=True)

        # Determine next version
        latest = self._latest_version_in_dir(date_dir)
        if latest is None:
            # First save of the day
            version = "1.0.0"
        else:
            major, minor, patch = latest
            version = f"{major}.{minor}.{patch + 1}"

        file_path = date_dir / f"v{version}.md"
        file_path.write_text(content, encoding="utf-8")

        # Write sidecar metadata
        await self._write_meta(
            file_path, doc_type, doc_name, version, today,
            conversation_id, round_id, change_summary, skill_id,
        )

        ref = VersionRef(
            doc_type=doc_type,
            doc_name=doc_name,
            date=today,
            version=version,
            file_path=file_path,
        )
        logger.info(f"Saved document: {ref.relative_path}")
        return ref

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def load_latest(self, doc_type: str, doc_name: str) -> Optional[Tuple[str, VersionRef]]:
        """Load the most recent version of a document.

        Returns (content, VersionRef) or None if not found.
        """
        ref = self._find_latest_ref(doc_type, doc_name)
        if ref is None:
            return None
        return ref.file_path.read_text(encoding="utf-8"), ref

    async def load_version(
        self, doc_type: str, doc_name: str, date: str, version: str
    ) -> Optional[Tuple[str, VersionRef]]:
        """Load a specific version."""
        file_path = self._date_dir(doc_type, doc_name, date) / f"v{version}.md"
        if not file_path.exists():
            return None
        ref = VersionRef(doc_type=doc_type, doc_name=doc_name,
                         date=date, version=version, file_path=file_path)
        return file_path.read_text(encoding="utf-8"), ref

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list_versions(self, doc_type: str, doc_name: str) -> List[VersionRef]:
        """Return all versions of a document, oldest first."""
        doc_dir = self.docs_root / doc_type / doc_name
        if not doc_dir.exists():
            return []

        refs: List[VersionRef] = []
        for date_dir in sorted(doc_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            date = date_dir.name
            for f in sorted(date_dir.glob("v*.md")):
                m = VERSION_RE.match(f.name)
                if m:
                    version = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
                    refs.append(VersionRef(
                        doc_type=doc_type, doc_name=doc_name,
                        date=date, version=version, file_path=f,
                    ))
        return refs

    async def list_documents(self, doc_type: Optional[str] = None) -> List[dict]:
        """List documents, optionally filtered by type."""
        results = []
        root = self.docs_root

        types = [doc_type] if doc_type else [
            d.name for d in root.iterdir()
            if d.is_dir() and d.name not in ("conversations",)
        ]

        for dtype in types:
            type_dir = root / dtype
            if not type_dir.exists():
                continue
            for name_dir in type_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                ref = self._find_latest_ref(dtype, name_dir.name)
                if ref:
                    results.append({
                        "doc_type": dtype,
                        "doc_name": name_dir.name,
                        "latest_version": ref.version,
                        "latest_date": ref.date,
                        "path": ref.relative_path,
                    })

        results.sort(key=lambda x: (x["latest_date"], x["doc_name"]), reverse=True)
        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _date_dir(self, doc_type: str, doc_name: str, date: str) -> Path:
        return self.docs_root / doc_type / doc_name / date

    def _latest_version_in_dir(self, date_dir: Path) -> Optional[Tuple[int, int, int]]:
        """Return the highest (major, minor, patch) tuple found in date_dir."""
        best = None
        for f in date_dir.glob("v*.md"):
            m = VERSION_RE.match(f.name)
            if m:
                t = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if best is None or t > best:
                    best = t
        return best

    def _find_latest_ref(self, doc_type: str, doc_name: str) -> Optional[VersionRef]:
        """Find the VersionRef for the most recent version of a document."""
        doc_dir = self.docs_root / doc_type / doc_name
        if not doc_dir.exists():
            return None

        best_date = None
        for date_dir in doc_dir.iterdir():
            if date_dir.is_dir():
                if best_date is None or date_dir.name > best_date.name:
                    best_date = date_dir

        if best_date is None:
            return None

        t = self._latest_version_in_dir(best_date)
        if t is None:
            return None

        version = f"{t[0]}.{t[1]}.{t[2]}"
        file_path = best_date / f"v{version}.md"
        return VersionRef(
            doc_type=doc_type,
            doc_name=doc_name,
            date=best_date.name,
            version=version,
            file_path=file_path,
        )

    async def _write_meta(
        self, file_path: Path, doc_type, doc_name, version, date,
        conversation_id, round_id, change_summary, skill_id,
    ):
        """Write a JSON sidecar file next to the document."""
        import json
        meta = {
            "doc_type": doc_type,
            "doc_name": doc_name,
            "version": version,
            "date": date,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "conversation_id": conversation_id,
            "round_id": round_id,
            "change_summary": change_summary,
            "skill_id": skill_id,
        }
        meta_path = file_path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: Optional[DocumentVersionService] = None


def get_doc_version_service() -> DocumentVersionService:
    global _service
    if _service is None:
        _service = DocumentVersionService()
    return _service
