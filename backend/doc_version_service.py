"""
Document Version Management Service

统一负责文档正式版本的保存、查询、加载、迁移与名称归一。

存储结构：
  doc_output/[doc_type]/[canonical_doc_name]/[YYYY-MM-DD]/v[X.Y.Z].md

当前策略：
- 正式版本只从仓库根目录下的 doc_output/ 读取与写入
- legacy 正式输出（如 backend/docs、docs）通过显式迁移收敛到 doc_output/
- backend/docs/conversations/ 保留为会话日志目录，不参与正式文档查询
- 同一文档类型下，对名称做“标题后缀剥离 + 别名归档 + 模糊匹配”解析，
  尽量将“同一对象不同叫法”合并到同一个文档目录
"""

import json
import logging
import re
import shutil
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, List, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = PROJECT_ROOT / "doc_output"
LEGACY_DOCS_ROOTS = [
    PROJECT_ROOT / "backend" / "docs",
    PROJECT_ROOT / "docs",
]
SERIES_META_FILENAME = ".series.json"
VERSION_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)\.md$")

DOC_TYPE_CONFIG = {
    "requirements": {
        "label": "需求规格",
        "aliases": {
            "requirements", "requirement", "req", "srs",
            "需求", "需求文档", "需求规格", "需求规格说明书", "需求规格文档",
        },
        "title_suffixes": [
            r"(?:软件)?需求规格(?:说明书|文档)?$",
            r"需求(?:说明书|文档)$",
            r"srs$",
        ],
    },
    "design": {
        "label": "软件设计方案",
        "aliases": {
            "design", "technical-design", "architecture",
            "设计", "设计文档", "设计方案", "软件设计方案", "软件设计说明",
        },
        "title_suffixes": [
            r"(?:软件)?设计(?:方案|说明|文档)$",
            r"技术方案$",
            r"架构设计$",
        ],
    },
    "test-plan": {
        "label": "测试方案",
        "aliases": {
            "test-plan", "test", "qa",
            "测试", "测试方案", "测试计划", "测试用例", "测试文档",
        },
        "title_suffixes": [
            r"测试(?:方案|计划|文档)$",
            r"测试用例(?:文档)?$",
        ],
    },
    "user-manual": {
        "label": "用户手册",
        "aliases": {
            "user-manual", "user-guide", "manual", "guide",
            "用户手册", "用户使用手册", "操作手册", "操作指南", "软件操作指南", "使用说明书",
        },
        "title_suffixes": [
            r"(?:软件)?用户(?:使用)?手册$",
            r"操作(?:手册|指南)$",
            r"使用说明书$",
            r"软件操作指南$",
        ],
    },
    "api": {
        "label": "API 文档",
        "aliases": {"api", "接口", "接口文档", "api文档"},
        "title_suffixes": [r"(?:api|接口)(?:设计|说明|文档)$"],
    },
    "general": {
        "label": "通用文档",
        "aliases": {"general", "document", "document-writing", "other", "通用", "文档"},
        "title_suffixes": [r"文档$"],
    },
}

GENERIC_ENTITY_SUFFIXES = [
    r"功能模块$",
    r"子模块$",
    r"模块$",
    r"子系统$",
    r"系统$",
    r"服务$",
    r"组件$",
    r"类$",
    r"包$",
]

GENERIC_ENTITY_DESCRIPTORS = [
    r"管理",
    r"配置",
    r"服务",
]


def _dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        text = (item or "").strip()
        if not text or text in seen:
            continue
        ordered.append(text)
        seen.add(text)
    return ordered


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", (value or "").strip()).lower()
    text = re.sub(r"[：:]", " ", text)
    text = re.sub(r"[\s\-_./\\|()[\]{}<>《》【】“”\"'‘’，,。；;！？!?·`~@#$%^&*+=]+", "", text)
    return text


@dataclass
class VersionRef:
    """Points to a specific version of a document on disk."""

    docs_root: Path
    doc_type: str
    doc_name: str
    date: str
    version: str
    file_path: Path
    doc_type_label: Optional[str] = None

    @property
    def docs_relative_path(self) -> str:
        try:
            return str(self.file_path.relative_to(self.docs_root))
        except ValueError:
            return self.file_path.name

    @property
    def relative_path(self) -> str:
        """Project-relative path when possible, else fallback to docs_root-relative."""
        try:
            return str(self.file_path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(Path(self.docs_root.name) / self.docs_relative_path)

    @property
    def version_tuple(self) -> Tuple[int, int, int]:
        parts = [int(x) for x in self.version.split(".")]
        return (parts[0], parts[1], parts[2])


@dataclass
class SeriesInfo:
    """Represents a document series (same type + same canonical object)."""

    docs_root: Path
    doc_type: str
    doc_type_label: str
    doc_name: str
    dir_name: str
    aliases: List[str]

    @property
    def series_dir(self) -> Path:
        return self.docs_root / self.doc_type / self.dir_name


class DocumentVersionService:
    """Creates, reads, and tracks versioned documents."""

    def __init__(
        self,
        docs_root: Path = DOCS_ROOT,
        legacy_docs_roots: Optional[List[Path]] = None,
    ):
        self.docs_root = Path(docs_root)
        roots = legacy_docs_roots if legacy_docs_roots is not None else LEGACY_DOCS_ROOTS
        self.legacy_docs_roots = [
            Path(root) for root in roots
            if Path(root).resolve() != self.docs_root.resolve()
        ]
        self.docs_root.mkdir(parents=True, exist_ok=True)
        self._migration_completed = False

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
        force_date: Optional[str] = None,
    ) -> VersionRef:
        """Save a document as the next version and return its VersionRef."""
        canonical_type = self._canonical_doc_type(doc_type)
        series = self._resolve_series(canonical_type, doc_name, create=True)
        today = force_date or datetime.now().strftime("%Y-%m-%d")

        date_dir = self._date_dir(series, today)
        date_dir.mkdir(parents=True, exist_ok=True)

        latest_same_day = self._latest_version_for_date(series, today)
        if latest_same_day is None:
            version = "1.0.0"
            previous_version = None
        else:
            major, minor, patch = latest_same_day.version_tuple
            version = f"{major}.{minor}.{patch + 1}"
            previous_version = latest_same_day.version

        file_path = date_dir / f"v{version}.md"
        file_path.write_text(content, encoding="utf-8")

        requested_name = (doc_name or "").strip() or series.doc_name
        aliases = self._merge_aliases(series.aliases, requested_name, series.doc_name)
        self._write_series_meta(series, aliases)
        self._write_meta(
            file_path=file_path,
            doc_type=series.doc_type,
            doc_type_label=series.doc_type_label,
            doc_name=series.doc_name,
            requested_name=requested_name,
            version=version,
            date=today,
            conversation_id=conversation_id,
            round_id=round_id,
            change_summary=change_summary,
            skill_id=skill_id,
            previous_version=previous_version,
            aliases=aliases,
        )

        ref = VersionRef(
            docs_root=self.docs_root,
            doc_type=series.doc_type,
            doc_name=series.doc_name,
            date=today,
            version=version,
            file_path=file_path,
            doc_type_label=series.doc_type_label,
        )
        logger.info(
            "Saved document: type=%s, name=%s, path=%s",
            ref.doc_type,
            ref.doc_name,
            ref.relative_path,
        )
        return ref

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def load_latest(self, doc_type: str, doc_name: str) -> Optional[Tuple[str, VersionRef]]:
        """Load the most recent version of a document."""
        series = self._resolve_series(self._canonical_doc_type(doc_type), doc_name, create=False)
        if series is None:
            return None
        ref = self._find_latest_ref(series)
        if ref is None:
            return None
        return ref.file_path.read_text(encoding="utf-8"), ref

    async def load_version(
        self, doc_type: str, doc_name: str, date: str, version: str
    ) -> Optional[Tuple[str, VersionRef]]:
        """Load a specific version."""
        series = self._resolve_series(self._canonical_doc_type(doc_type), doc_name, create=False)
        if series is None:
            return None

        for ref in self._list_refs_for_series(series):
            if ref.date == date and ref.version == version:
                return ref.file_path.read_text(encoding="utf-8"), ref
        return None

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list_versions(self, doc_type: str, doc_name: str) -> List[VersionRef]:
        """Return all versions of a document, oldest first."""
        series = self._resolve_series(self._canonical_doc_type(doc_type), doc_name, create=False)
        if series is None:
            return []
        refs = self._list_refs_for_series(series)
        refs.sort(key=lambda ref: (ref.date, ref.version_tuple))
        return refs

    async def list_documents(
        self,
        doc_type: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[dict]:
        """List documents, optionally filtered by type and document name query."""
        results = []
        types = (
            [self._canonical_doc_type(doc_type)]
            if doc_type
            else self._all_doc_types()
        )

        for dtype in types:
            for series in self._iter_merged_series(dtype):
                ref = self._find_latest_ref(series)
                if ref is None:
                    continue
                updated_at = self.ref_updated_at(ref)
                document = {
                    "doc_type": series.doc_type,
                    "doc_type_label": series.doc_type_label,
                    "doc_name": series.doc_name,
                    "display_name": series.doc_name,
                    "latest_version": ref.version,
                    "latest_date": ref.date,
                    "latest_updated_at": updated_at,
                    "path": ref.relative_path,
                    "aliases": series.aliases,
                }
                if self._matches_document_query(document, query):
                    results.append(document)

        results.sort(
            key=lambda item: (
                item.get("latest_updated_at") or item["latest_date"],
                item["doc_type"],
                item["doc_name"],
            ),
            reverse=True,
        )
        return results

    def migrate_legacy_outputs(self, *, cleanup: bool = True) -> Dict[str, int]:
        """Migrate legacy formal outputs into doc_output/ and optionally clean sources."""
        summary = {
            "migrated": 0,
            "skipped": 0,
            "reversioned": 0,
            "deleted_dirs": 0,
        }

        for legacy_root in self.legacy_docs_roots:
            if not legacy_root.exists():
                continue

            legacy_files = sorted(
                self._iter_legacy_version_files(legacy_root),
                key=lambda item: (
                    item["date"],
                    item["version_tuple"],
                    item["created_at"],
                    str(item["file_path"]),
                ),
            )
            for item in legacy_files:
                result = self._migrate_legacy_version(item)
                summary[result] += 1

            if cleanup:
                summary["deleted_dirs"] += self._cleanup_legacy_outputs(legacy_root)

        self._migration_completed = True
        return summary

    # ------------------------------------------------------------------
    # Helpers: resolution
    # ------------------------------------------------------------------

    def _canonical_doc_type(self, doc_type: Optional[str]) -> str:
        raw = (doc_type or "").strip()
        if not raw:
            return "general"

        direct = raw.lower()
        if direct in DOC_TYPE_CONFIG:
            return direct

        normalized = _normalize_text(raw)
        for canonical, config in DOC_TYPE_CONFIG.items():
            alias_keys = {_normalize_text(canonical)}
            alias_keys.update(_normalize_text(alias) for alias in config["aliases"])
            if normalized in alias_keys:
                return canonical

        return direct

    def _doc_type_label(self, doc_type: str) -> str:
        return DOC_TYPE_CONFIG.get(doc_type, {}).get("label", doc_type)

    def _all_doc_types(self) -> List[str]:
        types = set(DOC_TYPE_CONFIG.keys())
        if self.docs_root.exists():
            for item in self.docs_root.iterdir():
                if item.is_dir():
                    types.add(self._canonical_doc_type(item.name))
        return sorted(types)

    def _iter_merged_series(self, doc_type: str) -> Iterable[SeriesInfo]:
        merged: dict[str, SeriesInfo] = {}

        type_dir = self.docs_root / doc_type
        if not type_dir.exists():
            return merged.values()

        for series_dir in sorted(type_dir.iterdir()):
            if not series_dir.is_dir():
                continue

            series = self._load_series_info(doc_type, self.docs_root, series_dir)
            key = _normalize_text(series.doc_name)
            existing = merged.get(key)
            if existing is None:
                merged[key] = series
            else:
                merged[key] = SeriesInfo(
                    docs_root=existing.docs_root,
                    doc_type=doc_type,
                    doc_type_label=self._doc_type_label(doc_type),
                    doc_name=existing.doc_name,
                    dir_name=existing.dir_name,
                    aliases=self._merge_aliases(existing.aliases, *series.aliases),
                )

        return merged.values()

    def _resolve_series(
        self,
        doc_type: str,
        requested_name: Optional[str],
        *,
        create: bool,
    ) -> Optional[SeriesInfo]:
        cleaned_name = self._clean_requested_name(doc_type, requested_name)
        requested_aliases = self._build_name_aliases(doc_type, cleaned_name)

        candidates = list(self._iter_merged_series(doc_type))
        best_series: Optional[SeriesInfo] = None
        best_score = 0.0
        second_score = 0.0

        for series in candidates:
            score = self._score_series_match(requested_aliases, series.aliases)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_series = series
            elif score > second_score:
                second_score = score

        if best_series and (
            best_score >= 1.0
            or best_score >= 0.93
            or (best_score >= 0.82 and best_score - second_score >= 0.08)
        ):
            if best_series.docs_root == self.docs_root:
                aliases = self._merge_aliases(best_series.aliases, cleaned_name)
                if aliases != best_series.aliases:
                    updated = SeriesInfo(
                        docs_root=best_series.docs_root,
                        doc_type=best_series.doc_type,
                        doc_type_label=best_series.doc_type_label,
                        doc_name=best_series.doc_name,
                        dir_name=best_series.dir_name,
                        aliases=aliases,
                    )
                    self._write_series_meta(updated, aliases)
                    return updated
            return best_series

        if not create:
            return None

        canonical_name = cleaned_name or "未命名对象"
        dir_name = self._sanitize_dir_name(canonical_name)
        series = SeriesInfo(
            docs_root=self.docs_root,
            doc_type=doc_type,
            doc_type_label=self._doc_type_label(doc_type),
            doc_name=canonical_name,
            dir_name=dir_name,
            aliases=self._merge_aliases([canonical_name], requested_name or cleaned_name),
        )
        self._write_series_meta(series, series.aliases)
        return series

    def _load_series_info(self, doc_type: str, docs_root: Path, series_dir: Path) -> SeriesInfo:
        meta_path = series_dir / SERIES_META_FILENAME
        meta = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Failed to load series meta %s: %s", meta_path, exc)

        canonical_name = (
            (meta.get("doc_name") or "").strip()
            or self._clean_requested_name(doc_type, meta.get("display_name") or series_dir.name)
            or series_dir.name
        )
        aliases = self._merge_aliases(
            [series_dir.name, canonical_name],
            *(meta.get("aliases") or []),
        )

        return SeriesInfo(
            docs_root=docs_root,
            doc_type=doc_type,
            doc_type_label=self._doc_type_label(doc_type),
            doc_name=canonical_name,
            dir_name=series_dir.name,
            aliases=aliases,
        )

    def _score_series_match(self, requested_aliases: List[str], existing_aliases: List[str]) -> float:
        requested_keys = [_normalize_text(alias) for alias in requested_aliases if alias]
        existing_keys = [_normalize_text(alias) for alias in existing_aliases if alias]

        if not requested_keys or not existing_keys:
            return 0.0

        best = 0.0
        for req in requested_keys:
            for cur in existing_keys:
                if not req or not cur:
                    continue
                if req == cur:
                    return 1.0
                if len(req) >= 4 and (req in cur or cur in req):
                    best = max(best, 0.93)
                ratio = SequenceMatcher(None, req, cur).ratio()
                best = max(best, ratio)
        return best

    def _clean_requested_name(self, doc_type: str, doc_name: Optional[str]) -> str:
        raw = unicodedata.normalize("NFKC", (doc_name or "").strip())
        raw = raw.replace("/", " ").replace("\\", " ").strip()
        if not raw:
            return ""

        cleaned = raw
        for pattern in DOC_TYPE_CONFIG.get(doc_type, {}).get("title_suffixes", []):
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        cleaned = re.sub(r"[：:]\s*$", "", cleaned).strip()
        if re.search(r"[\u4e00-\u9fff]", cleaned):
            cleaned = cleaned.replace(" ", "")
        return cleaned or raw

    def _build_name_aliases(self, doc_type: str, doc_name: str) -> List[str]:
        base = self._clean_requested_name(doc_type, doc_name)
        aliases = [doc_name, base]

        entity_trimmed = base
        for pattern in GENERIC_ENTITY_SUFFIXES:
            entity_trimmed = re.sub(pattern, "", entity_trimmed).strip()
        if entity_trimmed and entity_trimmed != base:
            aliases.append(entity_trimmed)

        descriptor_trimmed = base
        for descriptor in GENERIC_ENTITY_DESCRIPTORS:
            descriptor_trimmed = re.sub(
                rf"{descriptor}(?=(?:{'|'.join(GENERIC_ENTITY_SUFFIXES)}))",
                "",
                descriptor_trimmed,
            ).strip()
        if descriptor_trimmed and descriptor_trimmed != base:
            aliases.append(descriptor_trimmed)

        no_acronym_prefix = re.sub(r"^[A-Za-z0-9]+\s*", "", base).strip()
        if no_acronym_prefix and no_acronym_prefix != base:
            aliases.append(no_acronym_prefix)

        if descriptor_trimmed:
            no_acronym_descriptor_trimmed = re.sub(r"^[A-Za-z0-9]+\s*", "", descriptor_trimmed).strip()
            if no_acronym_descriptor_trimmed and no_acronym_descriptor_trimmed != descriptor_trimmed:
                aliases.append(no_acronym_descriptor_trimmed)

        no_space = re.sub(r"\s+", "", base)
        if no_space and no_space != base:
            aliases.append(no_space)

        return _dedupe(aliases)

    def _merge_aliases(self, aliases: List[str], *extra_aliases: str) -> List[str]:
        merged = list(aliases)
        for alias in extra_aliases:
            if not alias:
                continue
            merged.extend(self._build_name_aliases("general", alias))
            merged.append(alias)
        return _dedupe(merged)

    def _sanitize_dir_name(self, name: str) -> str:
        sanitized = unicodedata.normalize("NFKC", name).strip()
        sanitized = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", "_", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip(" .")
        return sanitized or "未命名对象"

    # ------------------------------------------------------------------
    # Helpers: refs and versions
    # ------------------------------------------------------------------

    def _date_dir(self, series: SeriesInfo, date: str) -> Path:
        return series.series_dir / date

    def _list_refs_for_series(self, series: SeriesInfo) -> List[VersionRef]:
        refs: List[VersionRef] = []
        requested_aliases = self._build_name_aliases(series.doc_type, series.doc_name)

        type_dir = self.docs_root / series.doc_type
        if not type_dir.exists():
            return refs

        for series_dir in type_dir.iterdir():
            if not series_dir.is_dir():
                continue
            current = self._load_series_info(series.doc_type, self.docs_root, series_dir)
            if self._score_series_match(requested_aliases, current.aliases) < 0.82:
                continue
            refs.extend(self._list_refs_in_dir(current))

        refs.sort(key=lambda ref: (ref.date, ref.version_tuple))
        return refs

    def _list_refs_in_dir(self, series: SeriesInfo) -> List[VersionRef]:
        refs: List[VersionRef] = []
        if not series.series_dir.exists():
            return refs

        for date_dir in sorted(series.series_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            date = date_dir.name
            for file_path in sorted(date_dir.glob("v*.md")):
                match = VERSION_RE.match(file_path.name)
                if not match:
                    continue
                version = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
                refs.append(
                    VersionRef(
                        docs_root=series.docs_root,
                        doc_type=series.doc_type,
                        doc_name=series.doc_name,
                        date=date,
                        version=version,
                        file_path=file_path,
                        doc_type_label=series.doc_type_label,
                    )
                )
        return refs

    def _find_latest_ref(self, series: SeriesInfo) -> Optional[VersionRef]:
        refs = self._list_refs_for_series(series)
        if not refs:
            return None
        return max(refs, key=lambda ref: (ref.date, ref.version_tuple))

    def _latest_version_for_date(self, series: SeriesInfo, date: str) -> Optional[VersionRef]:
        same_day_refs = [ref for ref in self._list_refs_for_series(series) if ref.date == date]
        if not same_day_refs:
            return None
        return max(same_day_refs, key=lambda ref: ref.version_tuple)

    def _matches_document_query(self, document: dict, query: Optional[str]) -> bool:
        if not query:
            return True

        query_aliases = self._build_name_aliases(document["doc_type"], query)
        if not query_aliases:
            return True

        document_aliases = self._merge_aliases(
            [document["doc_name"]],
            *(document.get("aliases") or []),
        )
        return self._score_series_match(query_aliases, document_aliases) >= 0.82

    def _iter_legacy_version_files(self, legacy_root: Path) -> Iterable[Dict[str, Any]]:
        for file_path in sorted(legacy_root.rglob("v*.md")):
            if not file_path.is_file():
                continue
            if "conversations" in file_path.parts:
                continue

            match = VERSION_RE.match(file_path.name)
            if not match:
                continue

            rel_path = file_path.relative_to(legacy_root)
            meta = self._read_json(file_path.with_suffix(".meta.json"))
            legacy_type = self._canonical_doc_type(meta.get("doc_type") or rel_path.parts[0])
            date = str(meta.get("date") or file_path.parent.name)
            version = str(meta.get("version") or f"{match.group(1)}.{match.group(2)}.{match.group(3)}")
            created_at = str(meta.get("created_at") or "")
            requested_name = (
                (meta.get("requested_name") or "").strip()
                or (meta.get("doc_name") or "").strip()
                or self._legacy_doc_name_from_path(rel_path)
            )
            aliases = self._merge_aliases(
                meta.get("aliases") or [],
                requested_name,
                rel_path.parts[-3] if len(rel_path.parts) >= 4 else "",
            )

            yield {
                "legacy_root": legacy_root,
                "file_path": file_path,
                "meta": meta,
                "doc_type": legacy_type,
                "requested_name": requested_name,
                "date": date,
                "version": version,
                "version_tuple": tuple(int(x) for x in version.split(".")),
                "created_at": created_at,
                "content": file_path.read_text(encoding="utf-8"),
                "aliases": aliases,
            }

    def _migrate_legacy_version(self, item: Dict[str, Any]) -> str:
        series = self._resolve_series(item["doc_type"], item["requested_name"], create=True)
        assert series is not None

        aliases = self._merge_aliases(series.aliases, *(item["aliases"] or []), series.doc_name)
        if aliases != series.aliases:
            series = SeriesInfo(
                docs_root=series.docs_root,
                doc_type=series.doc_type,
                doc_type_label=series.doc_type_label,
                doc_name=series.doc_name,
                dir_name=series.dir_name,
                aliases=aliases,
            )
            self._write_series_meta(series, aliases)

        target_date_dir = self._date_dir(series, item["date"])
        target_date_dir.mkdir(parents=True, exist_ok=True)

        target_version = item["version"]
        target_path = target_date_dir / f"v{target_version}.md"
        result = "migrated"

        if target_path.exists():
            existing = target_path.read_text(encoding="utf-8")
            if existing == item["content"]:
                return "skipped"
            target_version = self._next_available_version(series, item["date"], item["version"])
            target_path = target_date_dir / f"v{target_version}.md"
            result = "reversioned"

        target_path.write_text(item["content"], encoding="utf-8")
        self._write_meta(
            file_path=target_path,
            doc_type=series.doc_type,
            doc_type_label=series.doc_type_label,
            doc_name=series.doc_name,
            requested_name=item["requested_name"] or series.doc_name,
            version=target_version,
            date=item["date"],
            conversation_id=item["meta"].get("conversation_id"),
            round_id=item["meta"].get("round_id"),
            change_summary=item["meta"].get("change_summary"),
            skill_id=item["meta"].get("skill_id"),
            previous_version=item["meta"].get("previous_version"),
            aliases=aliases,
            source_path=self._project_relative_or_absolute(item["file_path"]),
            source_version=item["version"],
        )
        return result

    def _legacy_doc_name_from_path(self, rel_path: Path) -> str:
        if len(rel_path.parts) >= 4:
            return rel_path.parts[-3]
        return ""

    def _next_available_version(self, series: SeriesInfo, date: str, base_version: str) -> str:
        refs = [ref for ref in self._list_refs_for_series(series) if ref.date == date]
        taken = {ref.version for ref in refs}
        if base_version not in taken:
            return base_version

        major, minor, patch = (int(x) for x in base_version.split("."))
        while True:
            patch += 1
            candidate = f"{major}.{minor}.{patch}"
            if candidate not in taken:
                return candidate

    def _cleanup_legacy_outputs(self, legacy_root: Path) -> int:
        deleted = 0
        for child in legacy_root.iterdir():
            if not child.is_dir():
                continue
            if child.name == "conversations":
                continue
            if not self._is_legacy_output_dir(child.name):
                continue
            shutil.rmtree(child)
            deleted += 1
        return deleted

    def _read_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load metadata %s: %s", path, exc)
            return {}

    def _project_relative_or_absolute(self, path: Path) -> str:
        try:
            return str(path.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path)

    def ref_metadata(self, ref: VersionRef) -> Dict[str, Any]:
        return self._read_json(ref.file_path.with_suffix(".meta.json"))

    def ref_updated_at(self, ref: VersionRef) -> str:
        meta = self.ref_metadata(ref)
        created_at = meta.get("created_at")
        if created_at:
            return str(created_at)
        modified_at = datetime.fromtimestamp(ref.file_path.stat().st_mtime, tz=timezone.utc)
        return modified_at.isoformat().replace("+00:00", "Z")

    def _is_legacy_output_dir(self, directory_name: str) -> bool:
        canonical = self._canonical_doc_type(directory_name)
        return canonical in DOC_TYPE_CONFIG

    # ------------------------------------------------------------------
    # Helpers: metadata
    # ------------------------------------------------------------------

    def _write_series_meta(self, series: SeriesInfo, aliases: List[str]) -> None:
        series.series_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "doc_type": series.doc_type,
            "doc_type_label": series.doc_type_label,
            "doc_name": series.doc_name,
            "display_name": series.doc_name,
            "aliases": _dedupe(aliases),
            "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        meta_path = series.series_dir / SERIES_META_FILENAME
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_meta(
        self,
        *,
        file_path: Path,
        doc_type: str,
        doc_type_label: str,
        doc_name: str,
        requested_name: str,
        version: str,
        date: str,
        conversation_id: Optional[str],
        round_id: Optional[int],
        change_summary: Optional[str],
        skill_id: Optional[str],
        previous_version: Optional[str],
        aliases: List[str],
        source_path: Optional[str] = None,
        source_version: Optional[str] = None,
    ) -> None:
        meta = {
            "doc_type": doc_type,
            "doc_type_label": doc_type_label,
            "doc_name": doc_name,
            "requested_name": requested_name,
            "version": version,
            "date": date,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "conversation_id": conversation_id,
            "round_id": round_id,
            "change_summary": change_summary,
            "previous_version": previous_version,
            "skill_id": skill_id,
            "aliases": aliases,
        }
        if source_path:
            meta["source_path"] = source_path
        if source_version:
            meta["source_version"] = source_version
        meta_path = file_path.with_suffix(".meta.json")
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


_service: Optional[DocumentVersionService] = None


def get_doc_version_service() -> DocumentVersionService:
    global _service
    if _service is None:
        _service = DocumentVersionService()
    return _service
