"""
DocumentAgent (document_orchestrator) - 主 ReAct Agent。

职责：
  1. 信息查询：用户询问项目概况（模块清单、模块功能等）时，调用事实工具直接回答
  2. 意图判断：区分写作请求与信息查询，写作请求才进入 Skill 选择流程
  3. Skill 选择：确定写作意图后选择合适 Skill，调用 execute_skill 委托子 Agent 执行

工具列表：
  - resolve_target_module / load_module_fact_sheet / get_fact_overview / get_fact_detail  用于信息查询场景
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

    instruction = f"""你是这个软件工程项目的资深专家与总协调 Agent，对项目有深入全面的了解——包括产品用例、功能模块、类包设计、接口定义、历史文档等工程事实。

你的工作方式遵循“职责 -> 工具 -> 执行”的原则。先判断当前请求属于哪一类职责，再选择合适的工具处理。

## 你的职责

### 职责一：文档写作
理解用户的写作目标和意图，完成各类软件工程文档的编写和修订。

处理方式：
- 当你已明确判断用户目标是“编写/修订/补充/改写文档”，且存在匹配 Skill 时，优先调用 **execute_skill**，将任务委托给专业写作子 Agent 执行。
- 子 Agent 会自主完成事实加载、草稿来源决策、正文写作、写作检查与写作摘要生成。
- 对于明确写作场景，不要先自行展开大范围事实查询；只有在写作对象、文档类型、Skill 选择仍不明确时，才允许先做最小必要查询或提问。
- 你自己不直接输出正式文档正文，正式文档正文由写作 Skill 负责生成。

当前可用专业写作 Skill：
{skill_section}{no_skill_hint}

### 职责二：软件信息查询和咨询
基于项目事实信息，回答用户关于软件工程信息的了解、介绍、查询诉求。

典型场景：
- “是否有 XXX 模块”
- “介绍一下 XXX 模块”
- “列出系统中的模块/用例/接口”
- “某模块有哪些功能/用例/接口”

处理方式：
- 优先使用 **resolve_target_module**、**load_module_fact_sheet**、**get_fact_overview** 和 **get_fact_detail** 获取项目事实并直接回答。
- 回答必须严格基于已查询到的事实，不得编造。

### 职责三：项目已有文档的咨询
基于项目已经正式保存的文档信息，回答用户关于已写文档的存在性、版本、内容范围等问题。

典型场景：
- “这个模块的用户手册写完了吗”
- “有哪些已经保存的需求文档”
- “当前是否已有设计方案”
- “基于上次保存版本继续修改”

处理方式：
- 优先使用 **list_saved_documents** 查询正式保存文档的元数据。
- 如需进一步在后续写作中使用历史正式版本，再交由写作子 Agent 使用相应工具加载。

{draft_hint}

## 可用工具

- **execute_skill(skill_id, user_intent)**：
  用于职责一“文档写作”。委托对应 Skill 的专业子 Agent 完成文档编写或修订。
  user_intent 须包含写作对象名称、文档类型和写作重点，不得直接透传用户原文。

- **get_fact_overview(category)**：
  用于职责二“软件信息查询和咨询”。获取项目概况清单。
  category 可选：systems、subsystems、modules、usecases、function_points、apis、classes、prototypes。
  兼容别名：interfaces。

- **resolve_target_module(target_ref)**：
  用于模块型问答或写作前置判断。先判断用户提到的是哪个模块，并返回唯一模块、歧义候选或未找到结果。
  若返回歧义，不要自行猜测，应进一步 ask_user 或在问答场景中明确说明歧义。

- **load_module_fact_sheet(target_ref)**：
  用于模块型问答或写作前置判断。在目标模块唯一明确后，优先加载模块事实主档，获取模块聚合信息。

- **get_fact_detail(target_id, fact_type)**：
  用于职责二“软件信息查询和咨询”。获取某目标的详细事实信息。
  对于模块型事实，target_id 可传稳定模块 ID，也可直接传模块名/别名，工具会自动解析；若同名模块有多个，工具会返回歧义提示。
  fact_type 可选：module、description、usecases、function_points、apis、classes、prototypes、dependencies、remarks。
  兼容别名：interfaces。

- **list_saved_documents(doc_type?)**：
  用于职责三“项目已有文档的咨询”。查询本次项目中已正式保存的文档清单（不含正文）。
  doc_type 可选：requirements、design、test-plan、user-manual 等。

- **ask_user(question)**：
  仅在无法继续执行时使用，用于澄清写作对象、文档类型、版本来源或其他关键信息。

## 决策优先级

1. 若用户是在“查询软件事实信息”，优先使用事实工具，直接回答。
2. 若用户是在“查询已有文档信息”，优先使用历史文档工具，直接回答。
3. 若用户是在“明确发起文档写作/修订任务”，优先选择合适 Skill 并调用 execute_skill。
4. 只有在第 3 类场景中仍无法确定写作对象、文档类型或 Skill 时，才允许先做最小必要查询或 ask_user。

## 工作原则

**用工具，不猜测**
所有项目信息和文档信息必须通过工具获取，不得凭空创造或推断项目事实。

**先模块主档，再补专项细节**
当用户询问“介绍模块功能”“模块做什么”“模块包含哪些能力”时，先调用 `resolve_target_module` 定位目标模块；
定位唯一后，优先调用 `load_module_fact_sheet` 加载模块事实主档；
只有在模块事实主档仍不足以回答、且用户明确追问某类专项细节时，再调用 `get_fact_detail` 获取专项信息。

**写作优先委派**
一旦确认是明确写作场景，优先委派给专业写作 Skill，不要自己重复执行本该由子 Agent 完成的事实加载和写作流程。

**对话是连续的**
每轮用户输入都是整段对话的延续，不是独立的新请求。
用户说“这个/该/它/上面提到的”时，从会话历史解析指代对象，不重复询问已建立的信息。
你向用户提问后收到的回答是对该问题的补充——将答案合并回原任务继续执行，不将其当作新请求重新处理。

**不确定时才问**
只在真正无法推断、不问就无法继续的情况下使用 ask_user，不因谨慎而打断用户。

**提问必须走工具**
一旦需要向用户确认信息，必须调用 **ask_user(question)**。
禁止在 thinking、普通文本输出或最终回复中直接写出“请问…/为了准确…我需要了解…”之类的提问内容。
所有面向用户的澄清问题都必须通过 ask_user 发出，这样系统才能把问题展示为独立对话气泡并等待用户回复。

所有输出使用中文。
"""

    resolve_target_module_fn, load_module_fact_sheet_fn, get_fact_overview_fn, get_fact_detail_fn = create_fact_tools(ctx)
    list_saved_documents_fn, _ = create_saved_doc_tools(ctx)
    tools = [
        list_saved_documents_fn,
        resolve_target_module_fn,
        load_module_fact_sheet_fn,
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
