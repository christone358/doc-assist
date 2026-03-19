## ADDED Requirements

### Requirement: 聊天界面展示每轮 token 消耗统计
每轮 Agent 响应完成后，Web UI SHALL 在消息气泡下方展示本轮 LLM 调用的 token 用量。

#### Scenario: 显示三项 token 统计
- **WHEN** Agent 完成一轮响应且 LLM 返回了 token 用量数据
- **THEN** Web UI SHALL 在该条 assistant 消息底部展示：prompt tokens 数量、completion tokens 数量、total tokens 数量

#### Scenario: LLM 未返回 token 数据时不显示
- **WHEN** Agent 完成一轮响应但 LLM 未返回 token 用量（如流式模式不支持）
- **THEN** Web UI SHALL 不显示 token 统计区域

#### Scenario: 历史对话中恢复 token 统计
- **WHEN** 用户打开一个已有的对话记录
- **THEN** 对于 llm_info 字段包含 token 数据的历史轮次，Web UI SHALL 在对应消息底部展示 token 统计
