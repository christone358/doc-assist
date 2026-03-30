## Why

当前架构每轮用户消息都重建 ADK InMemorySessionService 和 DocumentAgent，导致 ADK 层没有跨轮对话记忆——`ask_user` 的回答、用户表达的偏好、前几轮的推理上下文在下一轮全部丢失。一个对话中多轮交互是文档迭代写作的核心场景，缺乏上下文记忆会导致 agent 反复询问同样问题、无法利用已有信息。

## What Changes

- **复用 ADK Session**：在一个 conversation 生命周期内，`InMemorySessionService` 和 `session_id` 固定不变，跨轮共享事件历史
- **复用 DocumentAgent**：`LlmAgent` 实例与 `Runner` 绑定到 conversation，不再每轮重建
- **写作状态迁移至 ADK state**：草稿内容、已选 skill、已收集事实等写作上下文通过 ADK `session.state` 持久化，替代 `ConversationContext` 中的一次性字段
- **启用 Events Compaction**：当 session 事件历史过长时，ADK 自动压缩（摘要化）历史事件，避免 context 超限
- **ConversationContext 简化**：移除跨轮不再需要的字段（如 `collected_facts_parts`、`generated_draft`），仅保留当轮运行时状态

## Capabilities

### New Capabilities

- `adk-session-lifecycle`: 管理 ADK Session 和 Runner 的创建、复用与销毁，绑定到 conversation 生命周期

### Modified Capabilities

- `agent-core`: stream_message() 接口语义变化——从"每轮构建 agent"改为"复用 session 追加消息"
- `conversation-management`: Conversation 关闭/删除时需同步清理 ADK session 资源

## Impact

- `backend/agent/adk/runner_adapter.py`：核心重构，引入全局 session 注册表，`stream_message()` 改为向已有 session 追加消息
- `backend/agent/adk/document_agent.py`：agent 实例改为与 session 绑定，不再每轮重建
- `backend/agent/adk/write_document_tool.py`：写作状态读写改为操作 ADK state，而非 ConversationContext 字段
- `backend/main.py`：conversation 删除接口需触发 session 清理
- 依赖 ADK `google-adk` 版本需支持 Events Compaction（确认 API）
