"""
write_document Tool - 调用 LLM 生成文档，流式输出到 WebSocket。

接收 skill_id（由 LLM 根据用户意图选择），工具内部加载对应 Skill 的写作规范，
自动注入当前子 Agent working context 中已显式加载的 facts / skill resources / docs，
以及 LLM 显式传入的 context（修改场景为草稿）。

写作完成后，通过 tool_context.state 持久化草稿和 skill 选择，
工具向 ADK session 历史返回摘要字符串（而非完整草稿），避免历史膨胀。
"""

import logging
import re
from typing import TYPE_CHECKING, Dict

try:
    from google.adk.tools import ToolContext
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests
    class ToolContext:  # type: ignore[override]
        pass

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext
    from agent.models import SkillInfo

logger = logging.getLogger(__name__)


def _normalize_skill_token(value: str) -> str:
    text = (value or "").strip().lower()
    text = text.replace("_", "-")
    return re.sub(r"[^a-z0-9-]+", "-", text).strip("-")


def _resolve_skill(skill_id: str, skills_map: Dict[str, "SkillInfo"]):
    """Resolve the intended skill id from noisy model output.

    Some models may accidentally pass the sub-agent name like
    ``doc_worker_write_user_manual`` instead of the canonical skill id
    ``write-user-manual``. In writing mode there is only one valid skill,
    so we accept that fallback rather than surfacing an internal error
    into the generated document stream.
    """
    if skill_id in skills_map:
        return skill_id, skills_map[skill_id]

    normalized = _normalize_skill_token(skill_id)
    for candidate_id, candidate in skills_map.items():
        if _normalize_skill_token(candidate_id) == normalized:
            return candidate_id, candidate

    if normalized.startswith("doc-worker-"):
        normalized = normalized.removeprefix("doc-worker-")
        for candidate_id, candidate in skills_map.items():
            if _normalize_skill_token(candidate_id) == normalized:
                return candidate_id, candidate

    if len(skills_map) == 1:
        only_id, only_skill = next(iter(skills_map.items()))
        logger.warning(
            "write_document: fallback to sole skill %s for unexpected skill_id=%r",
            only_id,
            skill_id,
        )
        return only_id, only_skill

    return None, None


def create_write_document_tool(ctx: "ConversationContext", skills_map: Dict[str, "SkillInfo"]):
    """创建 write_document 工具函数，捕获对话上下文和 Skill 查找表。"""

    async def write_document(
        skill_id: str,
        module_name: str,
        context: str,
        user_intent: str,
        tool_context: ToolContext,
    ) -> str:
        """调用 LLM 生成文档，流式输出文档内容。

        根据 skill_id 自动加载对应 Skill 的写作规范，结合用户意图生成完整文档。
        已通过事实工具收集的项目事实会自动注入；
        修改场景请将现有草稿传入 context 参数；新建场景 context 传空字符串即可。

        Args:
            skill_id: 所选 Skill 的 id（如"write-requirements"），系统自动加载写作规范。
            module_name: 当前写作的模块名称；纯对话场景传空字符串。
            context: 修改场景传入已有草稿内容；新建场景或已通过 `docs.load_saved` 加载历史版本时传空字符串。
            user_intent: 用户的写作意图描述。

        Returns:
            写作完成的摘要信息（如"文档已生成，共 N 字"），完整草稿通过 session.state 持久化。
        """
        from agent.adk.llm_adapter import get_litellm_model_config
        from agent.adk.runner_adapter import emit_execution_event
        from agent.models import ExecutionActor, ExecutionEventStatus, ExecutionPhase
        import litellm

        llm_config = get_litellm_model_config()
        if llm_config is None:
            error_msg = "未配置 LLM 模型，无法生成文档。请在系统设置中添加模型配置。"
            await ctx.ws_sender({"type": "error", "content": error_msg})
            return error_msg

        # 加载 Skill 写作规范（渐进式披露：仅在写作时从磁盘读取）
        resolved_skill_id, skill = _resolve_skill(skill_id, skills_map)
        if skill is None or resolved_skill_id is None:
            error_msg = f"未找到 Skill '{skill_id}'，请确认 skill id 是否正确。"
            await ctx.ws_sender({"type": "error", "content": error_msg})
            return error_msg

        skill_id = resolved_skill_id
        ctx.selected_skill_id = skill_id
        ctx.selected_skill_name = skill.name

        skill_writing_inst = ""
        if skill.skill_md_path:
            try:
                from pathlib import Path
                md_text = Path(skill.skill_md_path).read_text(encoding="utf-8")
                # 跳过 frontmatter，取正文
                if md_text.startswith("---"):
                    end = md_text.find("\n---", 3)
                    if end != -1:
                        skill_writing_inst = md_text[end + 4:].strip()
                else:
                    skill_writing_inst = md_text.strip()
            except Exception as e:
                logger.warning(f"write_document: 读取 skill.md 失败: {e}")

        # ── 构建写作上下文 ──────────────────────────────────────────────────
        # 优先级：
        #   1. context 参数有内容 → 对话内中间草稿（修改场景，LLM 从 get_current_draft 取得后传入）
        #   2. context 为空 + ctx.loaded_base_draft 有内容 → 历史已保存版本（由 `docs.load_saved` 写入）
        #   3. 两者都空 → 纯新建场景
        effective_context = context.strip() or (ctx.loaded_base_draft or "")

        final_parts: list = []
        final_parts.extend(ctx.loaded_facts_parts)
        final_parts.extend(ctx.loaded_skill_resource_parts)
        final_parts.extend(ctx.loaded_docs_parts)
        if not final_parts:
            final_parts.extend(ctx.collected_facts_parts)
        if effective_context:
            header = "## 已有草稿" if final_parts else ""
            final_parts.append(f"{header}\n{effective_context}".strip())
        final_context = "\n\n".join(final_parts) if final_parts else "（无上下文信息）"

        logger.info(
            f"write_document: 开始生成 conversation={ctx.conversation_id}, "
            f"skill_id={skill_id}, module_name={module_name!r}, "
            f"facts_parts={len(ctx.loaded_facts_parts) or len(ctx.collected_facts_parts)}, "
            f"skill_parts={len(ctx.loaded_skill_resource_parts)}, "
            f"docs_parts={len(ctx.loaded_docs_parts)}, "
            f"context_chars={len(context)}, loaded_base_draft_chars={len(ctx.loaded_base_draft or '')}, "
            f"final_context_chars={len(final_context)}"
        )

        system_prompt = (
            f"{skill_writing_inst}\n\n" if skill_writing_inst else ""
        ) + (
            "## 写作原则\n"
            "- 所有输出使用中文，语言专业、清晰\n"
            "- 文档内容严格基于提供的上下文信息，不虚构细节\n"
            "\n"
            "## 输出边界\n"
            "- 本次 write_document 只输出正式文档正文，不输出过程总结、事实来源说明、质量检查结论、建议、待确认项汇总或编写说明\n"
            "- 写作完成后的执行总结与压缩摘要会由后续独立步骤生成，不要在正文中重复生成\n"
        )
        user_message = f"用户需求：{user_intent}\n\n## 上下文\n\n{final_context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ]
        await emit_execution_event(
            ctx,
            execution_id=ctx.current_execution_id or ctx.orchestrator_execution_id,
            parent_execution_id=ctx.orchestrator_execution_id if ctx.current_execution_id else None,
            actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.WRITE,
            name="write_document",
            status=ExecutionEventStatus.STARTED,
            display_text=f"开始生成文档：{module_name or ctx.current_module_name or '未命名文档'}",
            data={
                "tool": "write_document",
                "skill_id": skill_id,
                "parent_node_id": ctx.current_skill_node_id if ctx.current_execution_id else None,
            },
        )

        full_text = ""
        usage = None

        try:
            response = await litellm.acompletion(
                model=llm_config.model,
                messages=messages,
                api_key=llm_config.api_key,
                api_base=llm_config.api_base,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
                top_p=llm_config.top_p,
                stream=True,
                stream_options={"include_usage": True},
                **llm_config.request_kwargs,
            )

            async for chunk in response:
                if hasattr(chunk, "usage") and chunk.usage:
                    raw = chunk.usage
                    usage = {
                        "prompt_tokens":      getattr(raw, "prompt_tokens", 0),
                        "completion_tokens":  getattr(raw, "completion_tokens", 0),
                        "total_tokens":       getattr(raw, "total_tokens", 0),
                    }
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    await ctx.ws_sender({"type": "text", "content": token})

        except Exception as e:
            logger.error(f"write_document: LLM 调用失败: {e}")
            error_msg = f"\n⚠️ 文档生成中断：{str(e)}"
            await ctx.ws_sender({"type": "text", "content": error_msg})
            full_text += error_msg

        ctx.draft_updated = True
        if usage:
            ctx.llm_usage = usage

        # 写入 session.state：草稿和 skill 选择跨轮持久化
        # runner_adapter 的 done 事件将从 session.state 读取 draft_content 用于 ConversationManager 持久化
        tool_context.state["draft_content"] = full_text
        tool_context.state["selected_skill_id"] = skill_id
        tool_context.state["doc_type"] = skill.type
        # doc_name 优先用加载来源的 doc_name（保持版本连续性），否则用 LLM 传入的 module_name
        effective_doc_name = ctx.loaded_base_doc_name or module_name or ctx.current_module_name or ""
        effective_module_id = ctx.loaded_base_module_id or ctx.current_module_id or ""
        if effective_doc_name:
            tool_context.state["module_name"] = effective_doc_name
            ctx.current_module_name = effective_doc_name
        if effective_module_id:
            tool_context.state["module_id"] = effective_module_id
            ctx.current_module_id = effective_module_id

        logger.info(
            f"write_document: 生成完成 skill_id={skill_id}, chars={len(full_text)}, usage={usage}"
        )
        await emit_execution_event(
            ctx,
            execution_id=ctx.current_execution_id or ctx.orchestrator_execution_id,
            parent_execution_id=ctx.orchestrator_execution_id if ctx.current_execution_id else None,
            actor=ExecutionActor.SUBAGENT if ctx.current_execution_id else ExecutionActor.ORCHESTRATOR,
            phase=ExecutionPhase.WRITE,
            name="write_document",
            status=ExecutionEventStatus.COMPLETED,
            display_text=f"文档生成完成，共 {len(full_text)} 字",
            data={
                "tool": "write_document",
                "skill_id": skill_id,
                "chars": len(full_text),
                "parent_node_id": ctx.current_skill_node_id if ctx.current_execution_id else None,
                "output_preview": f"文档生成完成，共 {len(full_text)} 字",
                "output_detail": (
                    f"文档已生成。\n"
                    f"- 技能：{skill_id}\n"
                    f"- 模块：{effective_doc_name or module_name or '未命名文档'}\n"
                    f"- 字数：{len(full_text)}"
                ),
            },
        )

        # 返回摘要字符串写入 ADK session 历史，完整草稿只在 session.state 中
        return f"文档已生成，共 {len(full_text)} 字（skill: {skill_id}）"

    return write_document
