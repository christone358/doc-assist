"""Structured models shared by MCP runtime namespaces."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # pragma: no cover - test fallback when pydantic is unavailable
    class BaseModel:  # type: ignore[override]
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self) -> Dict[str, Any]:
            def _dump(value: Any):
                if isinstance(value, BaseModel):
                    return value.model_dump()
                if isinstance(value, list):
                    return [_dump(item) for item in value]
                if isinstance(value, dict):
                    return {key: _dump(item) for key, item in value.items()}
                return value

            return {key: _dump(value) for key, value in self.__dict__.items()}

    def Field(default=None, default_factory=None):  # type: ignore[override]
        if default_factory is not None:
            return default_factory()
        return default


class ToolVisibility(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"


class MCPErrorResult(BaseModel):
    error_type: str
    message: str
    target: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ModuleSummary(BaseModel):
    id: str
    name: str
    system: str = ""
    subsystem: str = ""
    status: str = ""
    description: str = ""
    submodules: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)


class FactsListModulesResult(BaseModel):
    modules: List[ModuleSummary]
    count: int
    overview_markdown: str = ""
    source_path: str = ""


class FactsGetModuleResult(BaseModel):
    module: ModuleSummary
    content: str
    source_path: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SavedDocumentSummary(BaseModel):
    doc_type: str
    doc_type_label: str = ""
    doc_name: str
    latest_version: str
    latest_date: str
    latest_updated_at: str = ""
    path: str
    aliases: List[str] = Field(default_factory=list)


class DocsListSavedResult(BaseModel):
    documents: List[SavedDocumentSummary]
    count: int


class DocsLoadSavedResult(BaseModel):
    doc_type: str
    doc_name: str
    version: str
    date: str
    path: str
    content: str
    doc_type_label: str = ""


class ArtifactFileInfo(BaseModel):
    path: str
    absolute_path: str
    size_bytes: int = 0
    mime_type: str = "application/octet-stream"
    is_text: bool = False
    updated_at: str = ""


class ArtifactsReadFileResult(BaseModel):
    file: ArtifactFileInfo
    content: str = ""
    content_truncated: bool = False


class ArtifactsWriteFileResult(BaseModel):
    file: ArtifactFileInfo
    created: bool = False
    overwritten: bool = False


class SkillResourceEntry(BaseModel):
    category: str
    path: str
    name: str


class SkillListResourcesResult(BaseModel):
    skill_id: str
    resources: List[SkillResourceEntry]
    count: int


class SkillReadResourceResult(BaseModel):
    skill_id: str
    path: str
    category: str
    content: str


class SkillRunScriptResult(BaseModel):
    skill_id: str
    path: str
    exit_code: int
    stdout: str = ""
    stderr_summary: str = ""
    result: Optional[Any] = None


class PrototypePageSummary(BaseModel):
    page_ref: str
    page_name: str
    title: str = ""
    relative_path: str = ""
    match_status: str = "matched"
    package_id: str = ""


class PrototypeListPagesResult(BaseModel):
    module: ModuleSummary
    pages: List[PrototypePageSummary]
    count: int
    llm_summary: str = ""


class PrototypeGetPageResult(BaseModel):
    page: PrototypePageSummary
    fact: Dict[str, Any] = Field(default_factory=dict)
    llm_summary: str = ""
    parser_warnings: List[str] = Field(default_factory=list)
