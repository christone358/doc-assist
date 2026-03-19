## ADDED Requirements

### Requirement: 消息气泡底部展示 Skill 与 token 元信息栏
Web UI SHALL 在每条 assistant 消息气泡底部渲染一个 meta bar，展示本轮调用的 Skill 标签和 token 统计。

#### Scenario: 流式完成后渲染 meta bar
- **WHEN** WebSocket 接收到 done chunk 且其中包含 skill 或 usage 数据
- **THEN** Web UI SHALL 在当前 assistant 消息气泡下方渲染 meta bar

#### Scenario: meta bar 仅在 done 后显示
- **WHEN** 流式输出进行中（done chunk 尚未到达）
- **THEN** Web UI SHALL 不显示 meta bar，避免数据不完整时闪烁

#### Scenario: 历史消息中展示 meta bar
- **WHEN** 用户打开历史对话，某轮消息的 skill_invoked 或 llm_info 字段有数据
- **THEN** Web UI SHALL 为该轮消息渲染对应的 meta bar
