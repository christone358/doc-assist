## 1. Skill Sub-agent 构建

- [x] 1.1 新建 `backend/agent/adk/execute_skill_tool.py`，实现 `_extract_and_load_skill_tools(skill_body, skill_dir)` 函数：通过 LLM 从 skill.md 正文中提取工具文件路径列表（相对于 skill 目录），动态 import 每个模块，提取与文件同名的可调用函数，返回工具函数列表；skill.md 中未声明工具时返回空列表
- [x] 1.2 实现 `_build_skill_subagent(skill, ctx, llm_config)` 函数：以 skill.md 正文 + 固定执行规范拼接为 instruction，创建 `LlmAgent` 实例，工具列表 = 通用工具集（get_current_draft、list_saved_documents、load_saved_document、get_fact_overview、get_fact_detail、write_document、ask_user）+ Skill 专属工具（由 `_extract_and_load_skill_tools` 加载）
- [x] 1.3 Sub-agent 的通用工具直接复用现有工具创建函数（传入相同 ctx）；write_document 从主 Agent 工具列表移除，仅注册到 Sub-agent

## 2. execute_skill 工具实现

- [x] 2.1 在 `execute_skill` 内部为 Sub-agent 创建独立的 `InMemorySessionService` 和 `Runner`，使用派生自 conversation_id 的临时 session_id；Sub-agent 的 ask_user 工具通过相同 ctx（含 WebSocket 引用）与用户通信
- [x] 2.2 实现 `_build_subagent_input(user_intent, ctx)` 函数：将 ctx 状态摘要（已有草稿字数、last_skill_execution_summary）拼接为 Sub-agent 初始输入前缀，与 user_intent 合并；主 Agent 历史摘要通过 tool_context 访问 session events，提取最近相关轮次的用户消息和 Agent 回复
- [x] 2.3 实现 `execute_skill(skill_id, user_intent, tool_context)` 主函数：从 skills_map 获取 skill，调用 `_build_skill_subagent` 创建 Sub-agent，调用 `_build_subagent_input` 构造输入，通过 Sub-agent 的 Runner 运行，等待完成后将执行摘要写入 `ctx.last_skill_execution_summary`，返回摘要字符串
- [x] 2.4 实现 `create_execute_skill_tool(ctx, skills_map)` 工厂函数，返回注册到主 Agent 的工具

## 3. 主 Agent 工具列表和 instruction 更新

- [x] 3.1 在 `document_agent.py` 中导入 `create_execute_skill_tool`，替换工具列表：移除所有事实加载和写作相关工具（含 write_document），仅保留 `execute_skill` 和 `ask_user`
- [x] 3.2 重写 `document_agent.py` 的 instruction：职责收窄为意图判断和 Skill 选择；说明 ask_user 仅用于意图层面澄清（写作对象不明确、Skill 无法判断），执行层面问题由 Sub-agent 负责
- [x] 3.3 更新 instruction 工作流：「理解意图 → 若不明确则 ask_user → 选择 Skill → 提炼 user_intent（含写作对象名称）→ 调用 execute_skill」
- [x] 3.4 在 instruction 中说明：user_intent 须由主 Agent 提炼生成（含写作对象名称），不得直接透传用户原文

## 4. Session 管理

- [x] 4.1 在 `ConversationContext` 中新增 `last_skill_execution_summary: Optional[str] = None` 字段，用于跨轮传递 Sub-agent 执行摘要

## 5. 内置 Skill 验证与补充

- [x] 5.1 检查三个内置 skill.md 正文：验证是否明确描述了事实上下文需求（上下文类型、加载时机）；不足处补充完善，确保 Sub-agent 能从描述中可靠推断所需事实

## 6. 验证

- [ ] 6.1 验证新建场景：主 Agent 只调用 execute_skill，Sub-agent 通过 ReAct 自主完成草稿决策、事实加载、写作全流程
- [ ] 6.2 验证修改场景：Sub-agent 内部调用 get_current_draft / list_saved_documents / load_saved_document 完成草稿来源决策，正确衔接已有草稿
- [ ] 6.3 验证 skill.md 上下文描述不足时：Sub-agent 调用 ask_user 确认，用户要求不依据事实则跳过事实加载直接写作；否则终止写作
- [ ] 6.4 验证多轮对话上下文连续：第二轮 execute_skill 创建的 Sub-agent 能通过 ctx 和注入摘要感知第一轮的写作历史
- [ ] 6.5 验证写作对象无法从 user_intent 定位时：Sub-agent 调用 ask_user 澄清或终止，不进入写作阶段
- [ ] 6.6 验证 session.state 写入正确（doc_type、module_name、draft_content），done 事件保存路径与保存按钮行为与修改前一致
- [ ] 6.7 验证不同 skill 对应不同 Sub-agent instruction，上下文加载行为与 skill 声明一致
- [ ] 6.8 验证 Skill 专属工具加载：在测试 skill 中声明工具路径，验证 Sub-agent 能正确发现并注册；未声明工具时正常运行不报错
