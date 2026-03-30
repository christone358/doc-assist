"""
write_document Tool - 调用 LLM 生成文档，流式输出到 WebSocket。

接收 skill_id（由 LLM 根据用户意图选择），工具内部加载对应 Skill 的写作规范，
自动注入 ctx.collected_facts_parts 中已收集的项目事实，
以及 LLM 显式传入的 context（修改场景为草稿）。

写作完成后，通过 tool_context.state 持久化草稿和 skill 选择，
工具向 ADK session 历史返回摘要字符串（而非完整草稿），避免历史膨胀。
"""

import logging
from typing import TYPE_CHECKING, Dict

from google.adk.tools import ToolContext

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext
    from agent.models import SkillInfo

logger = logging.getLogger(__name__)


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
        已通过 get_fact_overview / get_fact_detail 收集的项目事实会自动注入；
        修改场景请将现有草稿传入 context 参数；新建场景 context 传空字符串即可。

        Args:
            skill_id: 所选 Skill 的 id（如"write-requirements"），系统自动加载写作规范。
            module_name: 当前写作的模块名称（来自 get_fact_overview 已知信息）；纯对话场景传空字符串。
            context: 修改场景传入已有草稿内容；新建场景或已通过 load_saved_document 加载历史版本时传空字符串。
            user_intent: 用户的写作意图描述。

        Returns:
            写作完成的摘要信息（如"文档已生成，共 N 字"），完整草稿通过 session.state 持久化。
        """
        from agent.adk.llm_adapter import get_litellm_model_config
        import litellm

        llm_config = get_litellm_model_config()
        if llm_config is None:
            error_msg = "⚠️ 未配置 LLM 模型，无法生成文档。请在系统设置中添加模型配置。"
            await ctx.ws_sender({"type": "text", "content": error_msg})
            return error_msg

        # 加载 Skill 写作规范（渐进式披露：仅在写作时从磁盘读取）
        skill = skills_map.get(skill_id)
        if skill is None:
            error_msg = f"⚠️ 未找到 Skill '{skill_id}'，请确认 skill id 是否正确。"
            await ctx.ws_sender({"type": "text", "content": error_msg})
            return error_msg

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
        #   2. context 为空 + ctx.loaded_base_draft 有内容 → 历史已保存版本（由 load_saved_document 写入）
        #   3. 两者都空 → 纯新建场景
        effective_context = context.strip() or (ctx.loaded_base_draft or "")

        final_parts: list = list(ctx.collected_facts_parts)
        if effective_context:
            header = "## 已有草稿" if final_parts else ""
            final_parts.append(f"{header}\n{effective_context}".strip())
        final_context = "\n\n".join(final_parts) if final_parts else "（无上下文信息）"

        logger.info(
            f"write_document: 开始生成 conversation={ctx.conversation_id}, "
            f"skill_id={skill_id}, module_name={module_name!r}, "
            f"facts_parts={len(ctx.collected_facts_parts)}, "
            f"context_chars={len(context)}, loaded_base_draft_chars={len(ctx.loaded_base_draft or '')}, "
            f"final_context_chars={len(final_context)}"
        )

        system_prompt = (
            f"{skill_writing_inst}\n\n" if skill_writing_inst else ""
        ) + (
            "## 写作原则\n"
            "- 所有输出使用中文，语言专业、清晰\n"
            "- 文档内容严格基于提供的上下文信息，不虚构细节\n"
            "- 文档格式遵循 Markdown 规范，层次结构清晰\n"
        )
        user_message = f"用户需求：{user_intent}\n\n## 上下文\n\n{final_context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ]

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
                stream=True,
                stream_options={"include_usage": True},
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
        effective_doc_name = ctx.loaded_base_doc_name or module_name
        if effective_doc_name:
            tool_context.state["module_name"] = effective_doc_name

        logger.info(
            f"write_document: 生成完成 skill_id={skill_id}, chars={len(full_text)}, usage={usage}"
        )

        # 返回摘要字符串写入 ADK session 历史，完整草稿只在 session.state 中
        return f"文档已生成，共 {len(full_text)} 字（skill: {skill_id}）"

    return write_document
