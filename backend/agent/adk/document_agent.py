"""
DocumentAgent (document_orchestrator) - 主 ReAct Agent。

职责：
  1. 信息查询：用户询问项目概况（模块清单、模块功能等）时，调用事实工具直接回答
  2. 意图判断：区分写作请求与信息查询，写作请求才进入 Skill 选择流程
  3. Skill 选择：确定写作意图后选择合适 Skill，调用 execute_skill 委托子 Agent 执行

工具列表：
  - facts.list_modules / facts.get_module / prototypes.list_pages / prototypes.get_page / docs.list_saved / docs.load_saved  用于公共 MCP 信息查询场景
  - execute_skill  委托 Skill Sub-agent 执行完整写作流程
  - ask_user       仅用于意图层面的澄清
"""

import logging
from typing import List, TYPE_CHECKING

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from agent.adk.prompt_loader import load_prompt_template
from agent.adk.thought_tool import create_thought_tool, should_enable_thought_tool
from agent.adk.tool_catalog import build_main_agent_tool_view, render_tool_section

if TYPE_CHECKING:
    from agent.adk.runner_adapter import ConversationContext
    from agent.models import SkillInfo

logger = logging.getLogger(__name__)


def build_document_agent(
    ctx: "ConversationContext",
    skills: List["SkillInfo"],
    has_draft: bool,
    has_saved: bool = False,
) -> LlmAgent:
    from agent.adk.llm_adapter import get_litellm_model_config

    llm_config = get_litellm_model_config()
    if llm_config is None:
        raise RuntimeError("未配置 LLM 模型，无法初始化 DocumentAgent")

    skills_map = {s.id: s for s in skills}

    if skills:
        skill_list = "\n".join(
            f"- **{s.name}** (`{s.id}`)：{s.description}"
            for s in skills
        )
        skill_section = f"## 可用 Skill\n{skill_list}"
        no_skill_hint = ""
    else:
        skill_section = "## 当前没有加载任何 Skill"
        no_skill_hint = "\n告知用户暂无可用 Skill，请管理员在 skills 目录中添加。"

    tool_view = build_main_agent_tool_view(ctx, skills_map)
    tool_section = render_tool_section(tool_view, "## 可用工具")
    instruction = load_prompt_template(
        "document_orchestrator.md",
        slots={
            "skill_section": skill_section,
            "no_skill_hint": no_skill_hint,
            "tool_section": tool_section,
        },
    )
    tools = list(tool_view.tools)
    if should_enable_thought_tool(llm_config):
        tools.append(create_thought_tool())

    agent = LlmAgent(
        name="document_orchestrator",
        model=LiteLlm(
            model=llm_config.model,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
        ),
        instruction=instruction,
        tools=tools,
    )

    logger.info(
        f"DocumentAgent 构建完成: skills={[s.id for s in skills]}, "
        f"has_draft={has_draft}, tool_ids={list(tool_view.tool_ids)}"
    )
    return agent
