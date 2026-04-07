## MODIFIED Requirements

### Requirement: 文档保存时 module_name 与 doc_type 字段必须正确填写

`write_document` 工具完成写作后，SHALL 将 `module_name` 和 `doc_type` 写入 session.state，`done` 事件 SHALL 从 session.state 读取这两个字段并写入 `writing_state_data`，确保 `doc_version_service.save_document()` 以正确路径持久化文档，从而支持后续版本查询。

#### Scenario: write_document 写入 module_name 和 doc_type 到 session.state

- **WHEN** `write_document(skill_id, module_name, context, user_intent)` 被调用并完成写作时
- **THEN** 工具 SHALL 执行：
  1. 从 `skills_map[skill_id].type` 取 `doc_type`，写入 `tool_context.state["doc_type"]`
  2. 将传入的 `module_name` 写入 `tool_context.state["module_name"]`
- 若 `module_name` 为空（纯对话场景无模块名），则不写入该字段，`done` 事件中该字段为空字符串

#### Scenario: done 事件从 session.state 读取并写入 writing_state_data

- **WHEN** `done` 事件被触发时
- **THEN** `runner_adapter.py` SHALL 从 `session.state` 读取 `module_name` 和 `doc_type`，填入 `writing_state_data`，不再硬编码为空字符串
- **THEN** `doc_version_service.save_document()` 被调用时，路径为 `docs/[doc_type]/[module_name]/[date]/vX.Y.Z.md`，与 `list_saved_documents` / `load_saved_document` 查询路径一致

#### Scenario: module_name 作为 write_document 的新增参数

- **WHEN** 编排 LLM 调用 `write_document` 时
- **THEN** LLM SHALL 传入 `module_name` 参数（即当前写作的模块名，来自 `get_fact_overview` 已知信息）
- 若 `module_name` 为空字符串，系统正常运行，文档保存路径使用空字符串，不报错
