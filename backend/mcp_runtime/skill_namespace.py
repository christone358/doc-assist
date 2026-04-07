"""skill.* namespace adapters."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from .errors import MCPRuntimeError
from .models import (
    SkillListResourcesResult,
    SkillReadResourceResult,
    SkillResourceEntry,
    SkillRunScriptResult,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agent.models import SkillInfo

_TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".html", ".css", ".js", ".ts", ".tsx",
    ".py", ".csv", ".xml",
}


class SkillNamespace:
    """Adapters for internal skill.* MCP tools bound to one skill."""

    SCRIPT_TIMEOUT_SECONDS = 15

    def __init__(self, skill: Any):
        self.skill = skill
        if not skill.skill_md_path:
            raise MCPRuntimeError(
                error_type="skill_path_missing",
                message=f"Skill 缺少 skill_md_path：{skill.id}",
                target=skill.id,
            )
        self.skill_root = Path(skill.skill_md_path).resolve().parent

    def _scan_resources(self) -> list[Dict[str, str]]:
        resources = [
            {
                "category": getattr(item, "category", ""),
                "path": getattr(item, "path", ""),
                "name": getattr(item, "name", ""),
            }
            for item in getattr(self.skill, "resources", []) or []
        ]
        if resources:
            return resources

        discovered: list[Dict[str, str]] = []
        for path in sorted(self.skill_root.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(self.skill_root)
            if any(part.startswith(".") for part in relative_path.parts):
                continue
            category = "other"
            if relative_path.parts:
                head = relative_path.parts[0]
                if head in {"references", "reference"}:
                    category = "reference"
                elif head == "templates":
                    category = "template"
                elif head == "scripts":
                    category = "script"
            discovered.append({"category": category, "path": relative_path.as_posix(), "name": path.name})
        return discovered

    def _validate_relative_path(self, relative_path: str, *, script_only: bool = False) -> Path:
        raw = (relative_path or "").strip()
        if not raw:
            raise MCPRuntimeError("invalid_path", "relative_path 不能为空", target=relative_path)

        candidate = (self.skill_root / raw).resolve()
        try:
            candidate.relative_to(self.skill_root)
        except ValueError as exc:
            raise MCPRuntimeError(
                "path_out_of_scope",
                f"禁止访问 Skill 根目录之外的路径：{relative_path}",
                target=relative_path,
            ) from exc

        relative = candidate.relative_to(self.skill_root)
        if any(part.startswith(".") for part in relative.parts):
            raise MCPRuntimeError(
                "hidden_path_rejected",
                f"禁止访问隐藏路径：{relative_path}",
                target=relative_path,
            )
        if not candidate.exists() or not candidate.is_file():
            raise MCPRuntimeError(
                "resource_not_found",
                f"未找到 Skill 资源：{relative_path}",
                target=relative_path,
            )
        if script_only and candidate.suffix != ".py":
            raise MCPRuntimeError(
                "unsupported_script_type",
                f"仅支持执行 Python 脚本：{relative_path}",
                target=relative_path,
            )
        return candidate

    async def list_resources(self) -> dict:
        resources = [
            SkillResourceEntry(category=item["category"], path=item["path"], name=item["name"])
            for item in self._scan_resources()
        ]
        return SkillListResourcesResult(
            skill_id=self.skill.id,
            resources=resources,
            count=len(resources),
        ).model_dump()

    async def read_resource(self, relative_path: str) -> dict:
        candidate = self._validate_relative_path(relative_path)
        if candidate.suffix.lower() not in _TEXT_EXTENSIONS:
            raise MCPRuntimeError(
                "unsupported_resource_type",
                f"当前仅支持读取文本资源：{relative_path}",
                target=relative_path,
            )
        content = candidate.read_text(encoding="utf-8")
        category = "other"
        for resource in self._scan_resources():
            if resource["path"] == Path(relative_path).as_posix():
                category = resource["category"]
                break
        return SkillReadResourceResult(
            skill_id=self.skill.id,
            path=Path(relative_path).as_posix(),
            category=category,
            content=content,
        ).model_dump()

    async def run_script(self, relative_path: str, payload: Optional[Dict[str, Any]] = None) -> dict:
        candidate = self._validate_relative_path(relative_path, script_only=True)
        payload = payload or {}
        result: Any = None
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        exit_code = 0

        module_name = f"doc_assist_skill_{self.skill.id.replace('-', '_')}_{candidate.stem}"
        spec = importlib.util.spec_from_file_location(module_name, candidate)
        if spec is None or spec.loader is None:
            raise MCPRuntimeError(
                "script_load_failed",
                f"无法加载脚本：{relative_path}",
                target=relative_path,
            )

        module = importlib.util.module_from_spec(spec)
        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                spec.loader.exec_module(module)
                handler = None
                for attr_name in ("handle_request", "main", "run"):
                    maybe_handler = getattr(module, attr_name, None)
                    if callable(maybe_handler):
                        handler = maybe_handler
                        break

                if handler is not None:
                    call_result = handler(payload)
                    if asyncio.iscoroutine(call_result):
                        result = await asyncio.wait_for(
                            call_result,
                            timeout=self.SCRIPT_TIMEOUT_SECONDS,
                        )
                    else:
                        result = call_result
                    exit_code = 0
                else:
                    proc = await asyncio.create_subprocess_exec(
                        sys.executable,
                        str(candidate),
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdin_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(stdin_payload),
                        timeout=self.SCRIPT_TIMEOUT_SECONDS,
                    )
                    exit_code = proc.returncode or 0
                    stdout_buffer.write(stdout_bytes.decode("utf-8", errors="replace"))
                    stderr_buffer.write(stderr_bytes.decode("utf-8", errors="replace"))
        except asyncio.TimeoutError as exc:
            raise MCPRuntimeError(
                "script_timeout",
                f"Skill 脚本执行超时：{relative_path}",
                target=relative_path,
                details={"timeout_seconds": self.SCRIPT_TIMEOUT_SECONDS},
            ) from exc

        stderr_summary = stderr_buffer.getvalue().strip()
        stdout = stdout_buffer.getvalue().strip()
        if result is not None and not stdout:
            if isinstance(result, str):
                stdout = result
            else:
                stdout = json.dumps(result, ensure_ascii=False, indent=2)

        return SkillRunScriptResult(
            skill_id=self.skill.id,
            path=Path(relative_path).as_posix(),
            exit_code=exit_code,
            stdout=stdout,
            stderr_summary=stderr_summary,
            result=result,
        ).model_dump()
