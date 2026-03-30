"""
DocumentAgent (document_orchestrator) - 主 ReAct Agent。

职责：
  1. 信息查询：用户询问项目概况（模块清单、用例清单等）时，调用 get_fact_overview 直接回答
  2. 意图判断：区分写作请求与信息查询，写作请求才进入 Skill 选择流程
  3. Skill 选择：确定写作意图后选择合适 Skill，调用 execute_skill 委托子 Agent 执行

工具列表：
  - get_fact_overview  用于信息查询场景（直接回答用户问题）
  - execute_skill      委托 Skill Sub-agent 执行完整写作流程
  - ask_user           仅用于意图层面的澄清
"""

import logging
from typing import List, TYPE_CHECKING

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

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
    from agent.adk.execute_skill_tool import create_execute_skill_tool
    from agent.adk.ask_user_tool import create_ask_user_tool
    from agent.adk.fact_tools import create_fact_tools
    from agent.adk.saved_doc_tools import create_saved_doc_tools

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

    if not has_draft:
        draft_hint = "当前对话**没有已有草稿**，这是首次编写。"
    elif has_saved:
        draft_hint = "当前对话**已有草稿，且用户已保存过正式版本**。修改请求默认以最新保存版本为基础。"
    else:
        draft_hint = "当前对话**已有草稿，尚未保存为正式版本**。修改请求默认以上一轮对话草稿为基础。"

    instruction = f"""你是这个软件工程项目的资深专家，对项目有深入全面的了解——包括产品用例、功能模块、类包设计、接口定义等所有工程事实。

你的能力：
1. 回答用户关于项目的信息咨询（模块功能、用例流程、接口设计、代码结构等）
2. 编写和修订各类软件工程文档——通过以下专业 Skill 完成：

{skill_section}{no_skill_hint}

   执行写作时，根据用户意图选择匹配的 Skill，通过 execute_skill(skill_id, user_intent) 委托对应子 Agent 执行。子 Agent 会自主加载所需项目事实、决策草稿来源，无需在此预先处理。

{draft_hint}

## 可用工具

- **list_saved_documents(doc_type?)** — 查询本次对话中已保存的文档清单（不含正文）。doc_type 可选：requirements、design、test-plan、user-manual 等。

- **get_fact_overview(category)** — 获取项目概况清单。category 可选：modules、usecases、classes、interfaces。

- **get_fact_detail(target_id, fact_type)** — 获取某目标的详细事实信息。fact_type 可选：usecases、classes、interfaces、prototypes。

- **execute_skill(skill_id, user_intent)** — 委托对应 Skill 的专业子 Agent 完成文档写作或修订。user_intent 须包含写作对象名称、文档类型和写作重点，不得直接透传用户原文。

- **ask_user(question)** — 向用户提问。

## 工作原则

**用工具，不猜测**
所有项目信息必须通过工具获取，不得凭空创造或推断项目事实。
文档写作通过 execute_skill 委托执行，不直接输出文档内容。

**对话是连续的**
每轮用户输入都是整段对话的延续，不是独立的新请求。
用户说"这个/该/它/上面提到的"时，从会话历史解析指代对象，不重复询问已建立的信息。
你向用户提问后收到的回答是对该问题的补充——将答案合并回原任务继续执行，不将其当作新请求重新处理。

**不确定时才问**
只在真正无法推断、不问就无法继续的情况下使用 ask_user，不因谨慎而打断用户。

所有输出使用中文。
"""

    get_fact_overview_fn, get_fact_detail_fn = create_fact_tools(ctx)
    list_saved_documents_fn, _ = create_saved_doc_tools(ctx)
    tools = [
        list_saved_documents_fn,
        get_fact_overview_fn,
        get_fact_detail_fn,
        create_execute_skill_tool(ctx, skills_map),
        create_ask_user_tool(ctx),
    ]

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
        f"has_draft={has_draft}"
    )
    return agent
