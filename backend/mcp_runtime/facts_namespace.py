"""facts.* namespace adapters."""

from __future__ import annotations

import logging
from pathlib import Path

from project_fact_modules import DEFAULT_FACTS_ROOT, ModuleArchiveRepository

from .errors import MCPRuntimeError
from .models import FactsGetModuleResult, FactsListModulesResult, ModuleSummary

logger = logging.getLogger(__name__)


class FactsNamespace:
    """Adapters for public facts.* MCP tools."""

    def __init__(self, facts_root: str | Path = DEFAULT_FACTS_ROOT):
        self.facts_root = Path(facts_root).resolve()

    def _repo(self) -> ModuleArchiveRepository:
        if not self.facts_root.exists():
            raise MCPRuntimeError(
                error_type="facts_root_missing",
                message=f"project-facts 目录不存在：{self.facts_root}",
                target=str(self.facts_root),
            )
        return ModuleArchiveRepository(self.facts_root)

    async def list_modules(self) -> dict:
        repo = self._repo()
        modules = [
            ModuleSummary(
                id=item["id"],
                name=item["name"],
                system=item.get("system", ""),
                subsystem=item.get("subsystem", ""),
                status=item.get("status", ""),
                description=item.get("description", ""),
                submodules=item.get("submodules", []),
            )
            for item in repo.list_modules()
        ]
        overview_path = self.facts_root / "generated" / "views" / "modules.md"
        overview_markdown = overview_path.read_text(encoding="utf-8") if overview_path.exists() else ""
        result = FactsListModulesResult(
            modules=modules,
            count=len(modules),
            overview_markdown=overview_markdown,
            source_path=str(overview_path.relative_to(self.facts_root)) if overview_path.exists() else "",
        )
        return result.model_dump()

    async def get_module(self, module_ref: str) -> dict:
        repo = self._repo()
        module_id, candidates = repo.resolve_module_reference(module_ref)
        if candidates:
            raise MCPRuntimeError(
                error_type="ambiguous_module_ref",
                message=f"模块引用存在歧义：{module_ref}",
                target=module_ref,
                details={"candidates": candidates},
            )
        if not module_id:
            raise MCPRuntimeError(
                error_type="module_not_found",
                message=f"未找到模块：{module_ref}",
                target=module_ref,
            )

        module = repo.get_module(module_id)
        if module is None:
            raise MCPRuntimeError(
                error_type="module_not_found",
                message=f"未找到模块：{module_ref}",
                target=module_ref,
            )

        summary = ModuleSummary(
            id=module["id"],
            name=module["name"],
            system=module.get("system", ""),
            subsystem=module.get("subsystem", ""),
            status=module.get("status", ""),
            description=module.get("description", ""),
            aliases=module.get("aliases", []),
            submodules=module.get("submodules", []),
        )
        result = FactsGetModuleResult(
            module=summary,
            content=module["content"],
            source_path=module.get("path", ""),
            metadata={
                "usecases_count": len(module.get("usecases", [])),
                "function_points_count": len(module.get("function_points", [])),
                "apis_count": len(module.get("apis", [])),
                "prototype_pages_count": len(module.get("prototype_pages", [])),
            },
        )
        return result.model_dump()
