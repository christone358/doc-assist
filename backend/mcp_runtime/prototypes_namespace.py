"""prototypes.* namespace adapters."""

from __future__ import annotations

from pathlib import Path

from project_fact_modules import DEFAULT_FACTS_ROOT, ModuleArchiveRepository
from prototype_parser import PrototypeRepository

from .errors import MCPRuntimeError
from .models import ModuleSummary, PrototypeGetPageResult, PrototypeListPagesResult, PrototypePageSummary


def _build_page_list_summary(module_name: str, pages: list[PrototypePageSummary]) -> str:
    if not pages:
        return f"模块“{module_name}”当前没有匹配到可用原型页面。"
    names = "、".join(page.page_name for page in pages[:5])
    suffix = f" 等 {len(pages)} 个页面" if len(pages) > 5 else ""
    matched = sum(1 for page in pages if page.match_status == "matched")
    ambiguous = sum(1 for page in pages if page.match_status == "ambiguous")
    unmatched = sum(1 for page in pages if page.match_status == "unmatched")
    state_parts = [f"已匹配 {matched} 页"]
    if ambiguous:
        state_parts.append(f"歧义 {ambiguous} 页")
    if unmatched:
        state_parts.append(f"待确认 {unmatched} 页")
    return f"模块“{module_name}”关联 {len(pages)} 个页面：{names}{suffix}。{'，'.join(state_parts)}。"


class PrototypesNamespace:
    """Adapters for public prototypes.* MCP tools."""

    def __init__(self, facts_root: str | Path = DEFAULT_FACTS_ROOT):
        self.facts_root = Path(facts_root).resolve()

    def _module_repo(self) -> ModuleArchiveRepository:
        if not self.facts_root.exists():
            raise MCPRuntimeError(
                error_type="facts_root_missing",
                message=f"project-facts 目录不存在：{self.facts_root}",
                target=str(self.facts_root),
            )
        return ModuleArchiveRepository(self.facts_root)

    def _prototype_repo(self) -> PrototypeRepository:
        if not self.facts_root.exists():
            raise MCPRuntimeError(
                error_type="facts_root_missing",
                message=f"project-facts 目录不存在：{self.facts_root}",
                target=str(self.facts_root),
            )
        return PrototypeRepository(self.facts_root)

    async def list_pages(self, module_ref: str) -> dict:
        module_repo = self._module_repo()
        prototype_repo = self._prototype_repo()

        module_id, candidates = module_repo.resolve_module_reference(module_ref)
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

        module = module_repo.get_module(module_id)
        if module is None:
            raise MCPRuntimeError(
                error_type="module_not_found",
                message=f"未找到模块：{module_ref}",
                target=module_ref,
            )

        pages: list[PrototypePageSummary] = []
        for item in module.get("prototype_pages", []):
            page_name = item.get("name", "").strip()
            path = item.get("path", "").strip()
            match_status = "matched" if path else "unmatched"
            title = ""
            page_ref = page_name
            package_id = ""
            if path:
                page_id, page_candidates = prototype_repo.resolve_page_reference(path)
                if page_candidates:
                    match_status = "ambiguous"
                elif page_id:
                    fact = prototype_repo.get_page(page_id)
                    page_ref = page_id
                    title = (fact or {}).get("title", "")
                    package_id = (fact or {}).get("package_id", "")
            pages.append(
                PrototypePageSummary(
                    page_ref=page_ref,
                    page_name=page_name,
                    title=title,
                    relative_path=path,
                    match_status=match_status,
                    package_id=package_id,
                )
            )

        module_summary = ModuleSummary(
            id=module["id"],
            name=module["name"],
            system=module.get("system", ""),
            subsystem=module.get("subsystem", ""),
            status=module.get("status", ""),
            description=module.get("description", ""),
            aliases=module.get("aliases", []),
            submodules=module.get("submodules", []),
        )
        return PrototypeListPagesResult(
            module=module_summary,
            pages=pages,
            count=len(pages),
            llm_summary=_build_page_list_summary(module["name"], pages),
        ).model_dump()

    async def get_page(self, page_ref: str) -> dict:
        prototype_repo = self._prototype_repo()
        page_id, candidates = prototype_repo.resolve_page_reference(page_ref)
        if candidates:
            raise MCPRuntimeError(
                error_type="prototype_page_ambiguous",
                message=f"页面引用存在歧义：{page_ref}",
                target=page_ref,
                details={"candidates": candidates},
            )
        if not page_id:
            raise MCPRuntimeError(
                error_type="prototype_page_not_found",
                message=f"未找到原型页面：{page_ref}",
                target=page_ref,
            )

        fact = prototype_repo.get_page(page_id)
        if fact is None:
            raise MCPRuntimeError(
                error_type="prototype_page_not_found",
                message=f"未找到原型页面：{page_ref}",
                target=page_ref,
            )

        page_summary = PrototypePageSummary(
            page_ref=fact["page_id"],
            page_name=fact.get("page_name", ""),
            title=fact.get("title", ""),
            relative_path=fact.get("relative_path", ""),
            package_id=fact.get("package_id", ""),
            match_status="matched",
        )
        return PrototypeGetPageResult(
            page=page_summary,
            fact=fact,
            llm_summary=fact.get("llm_summary", ""),
            parser_warnings=fact.get("parser_warnings", []),
        ).model_dump()
