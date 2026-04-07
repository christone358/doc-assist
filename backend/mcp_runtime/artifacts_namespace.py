"""artifacts.* namespace adapters."""

from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from .errors import MCPRuntimeError
from .models import ArtifactFileInfo, ArtifactsReadFileResult, ArtifactsWriteFileResult

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ArtifactsNamespace:
    """Adapters for public artifacts.* MCP tools."""

    def __init__(self, root: Path | None = None):
        self.root = (root or PROJECT_ROOT).resolve()

    def _resolve_path(self, path: str) -> Path:
        raw = (path or "").strip()
        if not raw:
            raise MCPRuntimeError(
                error_type="invalid_path",
                message="path 不能为空",
                target=path,
            )

        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()

        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise MCPRuntimeError(
                error_type="path_out_of_scope",
                message=f"禁止访问工作区之外的路径：{path}",
                target=path,
                details={"root": str(self.root)},
            ) from exc

        return candidate

    def _build_file_info(self, candidate: Path) -> ArtifactFileInfo:
        stat = candidate.stat()
        mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        is_text = mime_type.startswith("text/") or candidate.suffix.lower() in {
            ".md",
            ".txt",
            ".json",
            ".yaml",
            ".yml",
            ".html",
            ".css",
            ".js",
            ".ts",
            ".tsx",
            ".py",
            ".csv",
            ".xml",
        }
        try:
            relative_path = candidate.relative_to(self.root).as_posix()
        except ValueError:
            relative_path = candidate.name

        return ArtifactFileInfo(
            path=relative_path,
            absolute_path=str(candidate),
            size_bytes=stat.st_size,
            mime_type=mime_type,
            is_text=is_text,
            updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        )

    async def read_file(
        self,
        path: str,
        include_content: bool = True,
        max_chars: int = 12000,
    ) -> dict:
        candidate = self._resolve_path(path)
        if not candidate.exists() or not candidate.is_file():
            raise MCPRuntimeError(
                error_type="artifact_not_found",
                message=f"未找到文件：{path}",
                target=path,
            )

        file_info = self._build_file_info(candidate)
        content = ""
        content_truncated = False

        if include_content and file_info.is_text:
            text = candidate.read_text(encoding="utf-8", errors="replace")
            if max_chars >= 0 and len(text) > max_chars:
                content = text[:max_chars]
                content_truncated = True
            else:
                content = text

        return ArtifactsReadFileResult(
            file=file_info,
            content=content,
            content_truncated=content_truncated,
        ).model_dump()

    async def write_file(
        self,
        path: str,
        content: str,
        overwrite: bool = True,
    ) -> dict:
        candidate = self._resolve_path(path)
        if candidate.exists() and candidate.is_dir():
            raise MCPRuntimeError(
                error_type="artifact_is_directory",
                message=f"目标路径是目录，无法写入文件：{path}",
                target=path,
            )
        if candidate.exists() and not overwrite:
            raise MCPRuntimeError(
                error_type="artifact_exists",
                message=f"文件已存在，未允许覆盖：{path}",
                target=path,
            )

        existed_before = candidate.exists()
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content or "", encoding="utf-8")
        file_info = self._build_file_info(candidate)

        return ArtifactsWriteFileResult(
            file=file_info,
            created=not existed_before,
            overwritten=existed_before,
        ).model_dump()
