## Why

用户在与 Agent 对话过程中，无法直观看到系统如何选择 Skill 以及本次对话消耗了多少 token，导致系统行为不透明，也不利于用户了解成本和调试问题。

## What Changes

- Agent 在 `_select_skill()` 中记录每个匹配信号，生成人类可读的选择理由字符串（如"文档类型「design」吻合；关键词「设计」命中能力范围"）
- 选择理由在 `skill_start` chunk 的 `reason` 字段中实时发送，流式输出前用户即可看到
- LLM 服务在每次调用后返回 token 用量（prompt tokens、completion tokens、total tokens）
- 每轮对话结束后，前端展示：已调用的 Skill 名称 + 选择理由（可折叠）+ 本轮 token 消耗统计
- 对话历史记录中持久化保存每轮的 token 用量、Skill 选择信息及选择理由

## Capabilities

### New Capabilities

- `skill-selection-display`: 在 Web UI 聊天界面展示每轮对话中 Agent 选择的 Skill 信息（Skill 名称、ID）及选择推理过程和理由
- `token-usage-display`: 在 Web UI 聊天界面展示每轮对话消耗的 token 数量（prompt、completion、total）

### Modified Capabilities

- `llm-integration`: LLM 服务调用需要返回 token 用量数据（目前只返回文本响应）
- `agent-core`: stream_message 流程需要在 done chunk 中携带 Skill 选择信息和 token 用量
- `web-ui`: 聊天消息气泡需要展示 Skill 选择和 token 用量信息

## Impact

- `backend/llm/service.py`：修改 `complete()` 和 `stream_complete()` 以返回 token 用量
- `backend/agent/core.py`：收集 token 数据，在 `done` chunk 中附带元数据
- `backend/main.py`：WebSocket handler 将 token 数据写入 `add_round` 的 `llm_info`
- `frontend/src/lib/components/Chat.svelte`：渲染 Skill 标签和 token 统计信息
- `agent/models.py`：`ConversationRound.llm_info` 字段已存在，无需变更
