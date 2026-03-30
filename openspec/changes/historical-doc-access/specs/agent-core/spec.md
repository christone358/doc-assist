## MODIFIED Requirements

### Requirement: Agent 支持精准修改和版本管理

Agent 应该能够识别用户的修改需求，通过渐进式工具调用发现并加载历史已保存文档版本，以其作为写作基础进行精准修改。

#### Scenario: 修改场景草稿来源决策

- **WHEN** 用户意图为修改已有文档时，Agent 需要确定写作基础
- **THEN** Agent SHALL 按以下优先顺序决策：
  1. 调用 `get_current_draft()` —— 若本次对话已有中间草稿，直接以此为基础，进入 `write_document(context=草稿内容)`
  2. 若无对话内草稿，调用 `list_saved_documents(doc_type)` 查询历史已保存版本
  3. 若有匹配文档，告知用户版本信息并询问是否基于历史版本修改（除非用户已明确表示）
  4. 用户确认后调用 `load_saved_document(doc_type, doc_name)`，再调用 `write_document(context="")`（系统自动使用已加载内容）
  5. 若无匹配历史文档或用户要求全新创建，按新建场景走

#### Scenario: 历史文档类型匹配判断

- **WHEN** Agent 在 `list_saved_documents` 结果中发现文档时
- **THEN** Agent SHALL 判断历史文档的 `doc_type` 是否与本次写作任务使用的 Skill type 一致；仅类型匹配时才推荐以该历史文档为基础

#### Scenario: 用户意图不明确时询问

- **WHEN** 用户请求中涉及修改、更新、续写等语义，但未明确指定是否基于历史版本
- **THEN** Agent SHALL 调用 `ask_user` 询问用户意图，不得在未经确认的情况下直接以历史版本覆盖新建场景
