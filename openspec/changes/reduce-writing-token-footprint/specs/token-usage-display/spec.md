## MODIFIED Requirements

### Requirement: 聊天界面展示每轮 token 消耗统计
每轮 Agent 响应完成后，Web UI SHALL 在消息气泡下方展示本轮整轮聚合 token 用量；若后端提供分阶段明细，Web UI SHALL 同时展示阶段级 usage breakdown。

#### Scenario: 显示整轮总量与阶段明细
- **WHEN** Agent 完成一轮响应且 done chunk 中包含整轮 usage 与 usage_breakdown
- **THEN** Web UI SHALL 在该条 assistant 消息底部展示整轮 prompt tokens、completion tokens、total tokens，并展示各执行阶段的对应 token 数量

#### Scenario: 仅有聚合 usage 时降级展示
- **WHEN** Agent 完成一轮响应仅返回聚合 usage 而未返回 usage_breakdown
- **THEN** Web UI SHALL 继续展示聚合 prompt tokens、completion tokens、total tokens，不因为缺少 breakdown 而隐藏 token 区域

#### Scenario: LLM 未返回 token 数据时不显示
- **WHEN** Agent 完成一轮响应但整轮 usage 不可用
- **THEN** Web UI SHALL 不显示 token 统计区域

#### Scenario: 历史对话中恢复 token 统计
- **WHEN** 用户打开一个已有的对话记录
- **THEN** 对于 llm_info 字段包含聚合 usage 或 usage_breakdown 的历史轮次，Web UI SHALL 在对应消息底部恢复显示 token 统计
