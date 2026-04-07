## Why

Agent 目前无法访问用户已保存的历史文档版本，修改类请求只能依赖当前对话内的中间草稿；一旦开启新对话或跨会话，历史存档版本对 Agent 不可见，用户必须手动粘贴内容，违背了智能写作助手的核心价值主张。

## What Changes

- **新增** `list_saved_documents(doc_type?)` 工具：返回历史已保存文档的元数据清单（文档名、版本号、日期），供编排 LLM 发现可用版本，不加载正文（渐进式披露第一步）
- **新增** `load_saved_document(doc_type, doc_name)` 工具：加载指定文档最新版本的正文，双路输出——摘要写入 ADK session 历史，正文存入 `ctx.loaded_base_draft`，不进历史（渐进式披露第二步）
- **修改** `write_document` 工具：当 `context` 参数为空时，自动读取 `ctx.loaded_base_draft` 作为草稿基础，写作 LLM 的上下文始终干净
- **修改** `ConversationContext`：新增 `loaded_base_draft: Optional[str]` 字段（per-round）
- **修复** `runner_adapter.py` done 事件中 `writing_state_data` 的 `module_name` 和 `doc_type` 字段为空字符串的 bug，确保写作完成后保存路径与后续查询路径一致
- **修改** `document_agent.py` instruction：区分两种草稿来源，引入历史文档发现-确认-加载决策树，更新修改场景工作流

## Capabilities

### New Capabilities

- `saved-document-access`：Agent 通过两步工具调用访问历史已保存文档版本（发现 + 加载），遵循渐进式披露原则，正文不写入 ADK session 历史

### Modified Capabilities

- `agent-core`：编排 LLM 的修改场景决策流程增加历史版本查询分支，区分"对话内中间草稿"与"历史已保存版本"两种草稿来源
- `document-version-management`：文档保存路径依赖 module_name 和 doc_type 字段，需确保写作完成后这两个字段被正确写入，才能支持后续的版本查询

## Impact

- `backend/agent/adk/` — 新增 `saved_doc_tools.py`，修改 `write_document_tool.py`、`document_agent.py`、`runner_adapter.py`
- `backend/agent/models.py` — `ConversationContext` 新增字段
- `backend/doc_version_service.py` — 只读调用，不修改服务本身
- 无前端协议变更，无数据库 schema 变更
