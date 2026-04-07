"""docs.* namespace adapters."""

from __future__ import annotations

from typing import Optional

from doc_version_service import DocumentVersionService, get_doc_version_service

from .errors import MCPRuntimeError
from .models import DocsListSavedResult, DocsLoadSavedResult, SavedDocumentSummary


class DocsNamespace:
    """Adapters for public docs.* MCP tools."""

    def __init__(self, service: Optional[DocumentVersionService] = None):
        self.service = service or get_doc_version_service()

    async def list_saved(self, doc_type: Optional[str] = None) -> dict:
        documents = await self.service.list_documents(doc_type)
        summaries = [
            SavedDocumentSummary(
                doc_type=item["doc_type"],
                doc_type_label=item.get("doc_type_label", ""),
                doc_name=item["doc_name"],
                latest_version=item["latest_version"],
                latest_date=item["latest_date"],
                latest_updated_at=item.get("latest_updated_at", ""),
                path=item["path"],
                aliases=item.get("aliases", []),
            )
            for item in documents
        ]
        return DocsListSavedResult(documents=summaries, count=len(summaries)).model_dump()

    async def load_saved(
        self,
        doc_type: str,
        doc_name: str,
        version: Optional[str] = None,
    ) -> dict:
        if not version:
            result = await self.service.load_latest(doc_type, doc_name)
        else:
            versions = await self.service.list_versions(doc_type, doc_name)
            ref = next((item for item in reversed(versions) if item.version == version), None)
            if ref is None:
                raise MCPRuntimeError(
                    error_type="document_version_not_found",
                    message=f"未找到历史版本：[{doc_type}] {doc_name} v{version}",
                    target=f"{doc_type}:{doc_name}:{version}",
                )
            result = await self.service.load_version(doc_type, doc_name, ref.date, ref.version)

        if result is None:
            raise MCPRuntimeError(
                error_type="document_not_found",
                message=f"未找到历史文档：[{doc_type}] {doc_name}",
                target=f"{doc_type}:{doc_name}",
            )

        content, ref = result
        return DocsLoadSavedResult(
            doc_type=ref.doc_type,
            doc_type_label=ref.doc_type_label or "",
            doc_name=ref.doc_name,
            version=ref.version,
            date=ref.date,
            path=ref.relative_path,
            content=content,
        ).model_dump()
