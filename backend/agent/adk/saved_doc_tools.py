"""
历史已保存文档访问 Tools - 渐进式披露双步工具。

提供两个工具：
- list_saved_documents:  发现层，返回历史已保存文档元数据清单（不加载正文）
- load_saved_document:   加载层，双路输出：摘要写入 ADK session 历史，正文存入 ctx.loaded_base_draft

create_saved_doc_tools(ctx) 返回带进程内上下文的异步工具对，
供 DocumentAgent 在修改场景中发现并加载历史已保存文档版本。
"""

import logging
from typing import Optional, Tuple, TYPE_CHECKING

try:
    from google.adk.tools import ToolContext
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    class ToolContext:  # type: ignore[override]
        pass

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext

logger = logging.getLogger(__name__)


def create_saved_doc_tools(ctx: "ConversationContext") -> Tuple:
    """创建历史已保存文档访问工具对。

    返回的工具函数遵循渐进式披露原则：
    - list_saved_documents：只返回元数据清单，不加载正文
    - load_saved_document：正文写入 ctx.loaded_base_draft，ADK 历史只写摘要

    Returns:
        (list_saved_documents_fn, load_saved_document_fn) 元组
    """
    from agent.adk.runner_adapter import complete_tool_node
    from agent.models import ExecutionNodeStatus

    execution_id = ctx.current_execution_id or ctx.orchestrator_execution_id
    parent_node_id = ctx.current_skill_node_id if ctx.current_execution_id else None

    async def list_saved_documents(
        doc_type: Optional[str] = None,
        tool_context: ToolContext = None,
    ) -> str:
        """列出历史已保存的文档版本（元数据清单，不含正文）。

        Args:
            doc_type: 按文档类型过滤，如 requirements、design 等；不传则列出所有类型。

        Returns:
            文档元数据清单字符串（含 doc_type、doc_name、latest_version、latest_date）；
            若无文档则返回说明性文字。
        """
        from doc_version_service import get_doc_version_service

        svc = get_doc_version_service()
        try:
            docs = await svc.list_documents(doc_type)
        except Exception as e:
            logger.error(f"list_saved_documents: 查询失败: {e}")
            return f"查询历史文档失败：{e}"

        if not docs:
            filter_hint = f"（类型：{doc_type}）" if doc_type else ""
            return f"暂无历史已保存文档{filter_hint}。"

        lines = ["历史已保存文档清单：\n"]
        for doc in docs:
            lines.append(
                f"- [{doc['doc_type']}] {doc['doc_name']} "
                f"最新版本：v{doc['latest_version']}，日期：{doc['latest_date']}"
            )

        result = "\n".join(lines)
        logger.info(f"list_saved_documents: doc_type={doc_type}, count={len(docs)}")

        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "list_saved_documents",
            "content": f"已查询历史文档清单：{len(docs)} 份",
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="list_saved_documents",
            parent_node_id=parent_node_id,
            status=ExecutionNodeStatus.COMPLETED,
            output_preview=f"已查询历史文档清单：{len(docs)} 份",
            output_detail=result,
        )

        return result

    async def load_saved_document(
        doc_type: str,
        doc_name: str,
        tool_context: ToolContext = None,
    ) -> str:
        """加载指定历史已保存文档的最新版本正文（双路输出）。

        正文写入 ctx.loaded_base_draft 供 write_document 自动衔接；
        ADK session 历史只记录摘要（版本号、日期、字数），不含正文，避免历史膨胀。

        Args:
            doc_type: 文档类型，如 requirements、design 等。
            doc_name: 文档名称（即模块名，与 list_saved_documents 返回的 doc_name 一致）。

        Returns:
            加载摘要字符串（如"已加载 [doc_name] v1.0.1 · 2026-03-20，共 N 字，就绪"）；
            若文档不存在则返回说明性文字，ctx.loaded_base_draft 不更新。
        """
        from doc_version_service import get_doc_version_service

        svc = get_doc_version_service()
        try:
            result = await svc.load_latest(doc_type, doc_name)
        except Exception as e:
            logger.error(f"load_saved_document: 加载失败 doc_type={doc_type}, doc_name={doc_name}: {e}")
            return f"加载历史文档失败：{e}"

        if result is None:
            return f"未找到历史文档：[{doc_type}] {doc_name}，请确认文档名称是否正确。"

        content, ref = result

        # 双路输出：正文存入 ctx.loaded_base_draft，不进 ADK session 历史
        ctx.loaded_base_draft = content
        # 记录解析后的 canonical doc_name，供 write_document 保存时保持版本连续性
        ctx.loaded_base_doc_name = ref.doc_name
        ctx.current_module_name = ref.doc_name

        try:
            from project_fact_modules import ModuleArchiveRepository
            from agent.adk.fact_tools import _FACTS_ROOT

            if _FACTS_ROOT.exists():
                repo = ModuleArchiveRepository(_FACTS_ROOT)
                module_id, candidates = repo.resolve_module_reference(ref.doc_name)
                if module_id and not candidates:
                    module = repo.get_module(module_id)
                    ctx.loaded_base_module_id = module_id
                    ctx.current_module_id = module_id
                    if module:
                        ctx.current_system_name = module.get("system") or ctx.current_system_name
                        ctx.current_subsystem_name = module.get("subsystem") or ctx.current_subsystem_name
        except Exception as e:  # pragma: no cover - 模块身份恢复只是增强能力
            logger.warning(f"load_saved_document: 恢复模块身份失败 doc_name={ref.doc_name}: {e}")

        summary = (
            f"已加载 {ref.doc_name} v{ref.version} · {ref.date}，"
            f"共 {len(content)} 字，就绪"
        )

        logger.info(
            f"load_saved_document: doc_type={doc_type}, doc_name={ref.doc_name}, "
            f"version={ref.version}, chars={len(content)}"
        )

        await ctx.ws_sender({
            "type": "status",
            "sub": "detail",
            "tool": "load_saved_document",
            "content": summary,
        })
        await complete_tool_node(
            ctx,
            execution_id=execution_id,
            tool_name="load_saved_document",
            parent_node_id=parent_node_id,
            status=ExecutionNodeStatus.COMPLETED,
            output_preview=summary,
            output_detail=(
                f"文档：{ref.doc_name}\n"
                f"类型：{doc_type}\n"
                f"版本：v{ref.version}\n"
                f"日期：{ref.date}\n"
                f"正文长度：{len(content)} 字"
            ),
        )

        # 向 ADK session 历史返回摘要，正文不进历史
        return summary

    return list_saved_documents, load_saved_document
