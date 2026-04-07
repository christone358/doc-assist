## 1. 依赖安装和项目准备

- [x] 1.1 在 `requirements.txt` 中新增 `google-adk` 和 `litellm` 依赖
- [x] 1.2 在 `react-mode` 分支中验证 `google-adk` 和 `litellm` 可正常安装
- [x] 1.3 新建 `backend/agent/adk/` 目录，创建 `__init__.py`

## 2. LiteLLM 适配层

- [x] 2.1 在 `backend/agent/adk/llm_adapter.py` 中实现 LiteLLM 配置转换：将现有 `llm_configs.json` 格式映射为 LiteLLM `model` 参数格式（例如 `deepseek/deepseek-chat`、`openai/qwen-plus`）
- [x] 2.2 实现 `get_litellm_model_config()` 函数，读取当前激活的 LLM 配置，返回 LiteLLM 可用的 model string 和 api_key/api_base

## 3. 项目事实加载 Tools

- [x] 3.1 在 `backend/agent/adk/fact_tools.py` 中将现有 `fact_info_service` 方法包装为 ADK Tool：实现 `get_fact_overview(category: str = None)` 工具，返回项目概览信息（模块清单、用例清单等）
- [x] 3.2 实现 `get_fact_detail(target_id: str, fact_type: str)` 工具，按写作目标和事实类型加载详细内容（用例描述、模块功能、类包结构等）

## 4. gather_facts 工具实现

- [x] 4.1 在 `backend/agent/adk/gather_facts_tool.py` 中创建内部 ReAct Agent（ADK `LlmAgent`），工具集为第 3 节的事实加载工具和第 6 节的 `ask_user` 工具
- [x] 4.2 实现内部 Agent 的系统提示：注入 Skill 的上下文需求描述，指导 Agent 以推理-行动循环逐步加载所需项目事实；每次行动前向用户输出加载意图，行动后向用户输出加载结果摘要
- [x] 4.3 配置 `max_steps` 步骤上限，步骤达到上限时以已收集内容继续，并向用户提示收集未完全完成
- [x] 4.4 将 `gather_facts(skill_context_desc: str, user_intent: str)` 包装为 DocumentAgent 可调用的 ADK Tool，返回值为收集到的事实内容字符串

## 5. write_document 工具实现

- [x] 5.1 在 `backend/agent/adk/write_document_tool.py` 中实现写作逻辑：接收 Skill 写作指令、已收集事实内容（或已有草稿）、用户意图，单次调用 LLM 生成文档
- [x] 5.2 支持流式输出，每个 token chunk 通过 ADK 事件机制向外传递
- [x] 5.3 将 `write_document(skill_writing_inst: str, context: str, user_intent: str)` 包装为 DocumentAgent 可调用的 ADK Tool，返回生成的文档内容

## 6. ask_user 工具实现

- [x] 6.1 在 `backend/agent/adk/ask_user_tool.py` 中实现 `ask_user(question: str)` 工具：向 WebSocket 发送提问消息，暂停等待用户下一条消息，将用户回复作为工具返回值
- [x] 6.2 验证 `ask_user` 在 ADK ReAct 循环中暂停/恢复的可行性，确认异步状态机设计方案

## 7. get_current_draft 工具实现

- [x] 7.1 在 `backend/agent/adk/draft_tool.py` 中实现 `get_current_draft()` 工具：从当前对话的 `ConversationInfo.writing_state` 读取已有草稿全文并返回；无草稿时返回空值

## 8. DocumentAgent（主 Agent）实现

- [x] 8.1 在 `backend/agent/adk/document_agent.py` 中创建 `DocumentAgent`（ADK `LlmAgent`，ReAct 模式），持有工具集：`gather_facts`、`get_current_draft`、`write_document`、`ask_user`
- [x] 8.2 实现系统提示：注入所有已注册 Skill 的名称和描述（含各 Skill 的能力边界），注入当前对话是否存在已有草稿的布尔标识；指导 Agent 基于用户意图自主选择 Skill 并决定工具调用顺序
- [x] 8.3 实现无匹配 Skill 的兜底响应：当 LLM 推理无法匹配任何 Skill 时，向用户说明可用 Skill 列表

## 9. ADK Runner 与 WebSocket 适配层

- [x] 9.1 在 `backend/agent/adk/runner_adapter.py` 中实现 ADK Runner 事件到 WebSocket 消息的映射：`PartialResponseEvent` → `text`、工具调用事件 → `status`（展示工具调用信息）、`FinalResponseEvent` → `done`、`ErrorEvent` → `error`
- [x] 9.2 实现 `stream_message()` 异步生成器：启动 ADK Runner，将映射后的事件 yield 出来，保持与现有 `AgentCore.stream_message()` 相同的接口签名
- [x] 9.3 实现 done 事件的元数据填充：skill_id、skill_name、skill_reason、token 用量、is_draft_updated

## 10. AgentCore 接口层替换

- [x] 10.1 修改 `backend/agent/core.py`：将 `stream_message()` 和 `process_message()` 的实现替换为调用 `runner_adapter.py` 中的新实现，保持接口签名不变
- [x] 10.2 保留 `AgentCore.get_instance()` 单例模式，`initialize()` 方法改为初始化 ADK Runner 和加载 Skills
- [x] 10.3 移除原有流水线方法：`_select_skill()`、`_infer_context_needs()`、`_resolve_module()`、`_load_context()`、`_stream_llm_response()`、`_build_system_prompt()`

## 11. Skill.md 内容更新

- [x] 11.1 检查 `backend/skills/` 目录下所有现有 Skill 的 `skill.md` 文件，确认其内容能够清晰表达两类信息：该 Skill 需要哪类项目事实、以及文档写作规范；格式和段落结构由 Skill 作者自定

## 12. 集成测试

- [x] 12.1 测试新编写流程：用户发送编写请求 → DocumentAgent 选 Skill → 调用 gather_facts 加载项目事实 → 调用 write_document 生成文档 → WebSocket done 事件
- [x] 12.2 测试修改流程：用户发送修改指令且对话存在已有草稿时，Agent 以已有草稿为基础生成修改后文档，结果符合用户的修改要求
- [x] 12.3 测试多轮对话：第二轮指令无需重新描述文档类型和写作目标，Agent 基于已有上下文继续迭代
- [x] 12.4 测试向用户提问：gather_facts 过程中找不到目标信息时调用 ask_user，用户回复后继续收集
- [x] 12.5 测试无匹配 Skill 场景：DocumentAgent 返回可用 Skill 列表引导用户
- [x] 12.6 验证 WebSocket 协议不变：前端无需修改，现有 Chat.svelte 正常工作
