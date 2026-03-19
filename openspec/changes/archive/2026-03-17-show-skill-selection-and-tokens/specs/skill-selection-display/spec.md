## ADDED Requirements

### Requirement: 聊天界面展示已选择的 Skill 信息及选择推理
每轮 Agent 响应完成后，Web UI SHALL 在消息气泡下方展示本轮调用的 Skill 标识及 Agent 选择该 Skill 的推理过程与理由。

#### Scenario: 显示选中的 Skill 名称
- **WHEN** Agent 完成一轮响应且选择了某个 Skill
- **THEN** Web UI SHALL 在该条 assistant 消息底部显示一个 Skill badge，内容为 Skill 的显示名称（name 字段）

#### Scenario: 显示 Skill 选择理由
- **WHEN** Agent 完成一轮响应且选择了某个 Skill，且 skill_reason 字段非空
- **THEN** Web UI SHALL 在 Skill badge 下方展示选择理由文本，说明 Agent 为何选择该 Skill（如"文档类型「design」吻合；关键词「设计方案」命中能力范围"）

#### Scenario: 进度步骤中实时显示理由
- **WHEN** Agent 在流式输出开始前发出 skill_start 状态步骤且携带 reason 字段
- **THEN** Web UI SHALL 在该进度步骤文本后附加选择理由（如"使用 Skill: 需求规格文档编写 · 文档类型「requirements」吻合"）

#### Scenario: 未匹配到 Skill 时不显示标签
- **WHEN** Agent 完成一轮响应但未选择任何 Skill（skill_id 为 null）
- **THEN** Web UI SHALL 不显示 Skill badge 和选择理由，保持消息气泡整洁

#### Scenario: 历史对话中恢复 Skill 标签和理由
- **WHEN** 用户打开一个已有的对话记录
- **THEN** 对于 skill_invoked 字段有值的历史轮次，Web UI SHALL 展示 Skill badge；若 llm_info 中保存了 skill_reason，SHALL 同时展示选择理由
