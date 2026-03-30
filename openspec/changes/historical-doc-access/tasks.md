## 1. 前置：修复 writing_state_data bug

- [x] 1.1 在 `write_document_tool.py` 中新增 `module_name: str` 参数，写作完成后将 `module_name` 写入 `tool_context.state["module_name"]`，将 `skills_map[skill_id].type` 写入 `tool_context.state["doc_type"]`
- [x] 1.2 在 `runner_adapter.py` 的 `done` 事件处理中，从 `session.state` 读取 `module_name` 和 `doc_type`，替换 `writing_state_data` 中原来的空字符串硬编码

## 2. ConversationContext 新增字段

- [x] 2.1 在 `backend/agent/models.py` 的 `ConversationContext` 中新增 `loaded_base_draft: Optional[str] = None` 字段（per-round，无需持久化）

## 3. 新增历史文档访问工具

- [x] 3.1 新建 `backend/agent/adk/saved_doc_tools.py`，实现 `list_saved_documents(doc_type: Optional[str], tool_context: ToolContext)` 工具函数：调用 `doc_version_service.list_documents(doc_type)`，将结果格式化为元数据清单字符串返回（写入 ADK session 历史）；若无文档则返回说明性文字
- [x] 3.2 在 `saved_doc_tools.py` 中实现 `load_saved_document(doc_type: str, doc_name: str, tool_context: ToolContext)` 工具函数：调用 `doc_version_service.load_latest(doc_type, doc_name)`，执行双路输出——向 ADK 历史返回摘要字符串（含版本号、日期、字数），将正文写入 `ctx.loaded_base_draft`；若文档不存在返回说明性文字，不更新 `ctx.loaded_base_draft`
- [x] 3.3 在 `saved_doc_tools.py` 中实现 `create_saved_doc_tools(ctx)` 工厂函数，返回两个工具的 ADK 包装列表（类比 `create_fact_tools`）

## 4. write_document 自动衔接 loaded_base_draft

- [x] 4.1 在 `write_document_tool.py` 中修改草稿来源优先级逻辑：`context` 参数有内容时使用 `context`；`context` 为空且 `ctx.loaded_base_draft` 有内容时使用 `ctx.loaded_base_draft`；两者都空时为纯新建场景

## 5. Agent 注册新工具并更新 instruction

- [x] 5.1 在 `document_agent.py` 中导入 `create_saved_doc_tools`，在 `build_agent()` 中将两个新工具注册到 agent 的工具列表
- [x] 5.2 在 `document_agent.py` 的 instruction 中更新修改场景决策树：按五步优先顺序引导 LLM 决策（优先对话内草稿 → 查询历史文档 → 告知并确认 → 加载历史文档 → 无匹配则新建），并说明 `write_document` 新增 `module_name` 参数的使用方式
- [x] 5.3 在 instruction 中补充历史文档 `doc_type` 匹配判断原则：仅当历史文档 `doc_type` 与本次 skill type 一致时才推荐以其为基础
- [x] 5.4 在 instruction 中补充意图不明确时须调用 `ask_user` 的规则：不得在未经用户确认的情况下以历史版本覆盖新建场景

## 6. 验证

- [x] 6.1 验证新文档写作完成后，`doc_version_service` 保存的路径包含正确的 `doc_type` 和 `module_name`（不再为空字符串）
- [x] 6.2 验证 `list_saved_documents` 返回元数据清单，不含文档正文；验证 `load_saved_document` 返回摘要，正文写入 `ctx.loaded_base_draft`
- [x] 6.3 验证修改场景中 LLM 调用 `write_document(context="")` 后，写作 LLM 收到 `ctx.loaded_base_draft` 作为草稿基础
- [x] 6.4 验证对话内中间草稿（`context` 参数非空）优先于 `ctx.loaded_base_draft`
