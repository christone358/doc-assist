## MODIFIED Requirements

### Requirement: 对话数据模型
对话 SHALL 持有写作状态字段，支持在多轮写作过程中保持和更新写作上下文。

#### Scenario: ConversationInfo 包含 writing_state 字段
- **WHEN** 对话对象被创建或加载时
- **THEN** ConversationInfo SHALL 包含可选的 writing_state 字段，初始值为 null

#### Scenario: WritingState 包含必要字段
- **WHEN** writing_state 被创建时
- **THEN** 其 SHALL 包含以下字段：module_id、module_name、skill_id、doc_type、draft_content、saved_version（可选）、saved_path（可选）

#### Scenario: writing_state 随对话完整持久化
- **WHEN** 对话保存到磁盘时
- **THEN** writing_state 的所有字段 SHALL 被序列化到 conversation_log.json 中，重新加载后可完整恢复
