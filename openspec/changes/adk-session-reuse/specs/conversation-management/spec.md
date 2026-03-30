## ADDED Requirements

### Requirement: Conversation 删除触发 ADK Session 清理
系统 SHALL 在 conversation 被删除时，同步清理对应的 ADK session 注册表条目，释放内存资源。

#### Scenario: 删除 conversation 时清理 session
- **WHEN** 用户通过 API 删除一个 conversation
- **THEN** 系统 SHALL 在 ConversationManager 完成删除后，调用 session 注册表的清理接口，移除对应 conversation_id 的 session entry
