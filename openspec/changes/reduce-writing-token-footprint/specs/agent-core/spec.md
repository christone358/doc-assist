## MODIFIED Requirements

### Requirement: Agent 流式响应携带 Skill 和 token 元数据
Agent 在完成流式响应时 SHALL 在 done chunk 中附带本轮选择的 Skill 信息（含选择推理）、整轮聚合 token 用量、分阶段 token 明细和上下文体量指标，供前端展示和持久化使用。

#### Scenario: skill_start chunk 携带选择理由
- **WHEN** Agent 确定要使用某个 Skill，发出 skill_start chunk
- **THEN** skill_start chunk SHALL 包含 reason 字段，值为人类可读的中文选择理由字符串（由匹配信号推导，如"文档类型「design」吻合；关键词「设计」命中能力范围"）

#### Scenario: done chunk 携带完整元数据
- **WHEN** Agent 完成一轮流式响应
- **THEN** 发出的 done chunk SHALL 包含：skill_id（选中的 Skill ID，可为 null）、skill_name（Skill 显示名，可为 null）、skill_reason（选择推理字符串，可为 null）、usage（整轮聚合 prompt_tokens/completion_tokens/total_tokens 对象，不可用时为 null）、usage_breakdown（按执行阶段分组的 usage 对象，可为空）、context_metrics（包含写作上下文字符数、分层 part 数量、裁剪或去重结果的对象，可为空）

#### Scenario: 未匹配 Skill 时 done chunk 中字段为 null
- **WHEN** 本轮未匹配到任何 Skill
- **THEN** done chunk 中 skill_id、skill_name 和 skill_reason SHALL 为 null，usage 字段照常填充整轮聚合值（若有），usage_breakdown 和 context_metrics 仅在存在数据时填充

#### Scenario: 选择理由由评分信号推导，无需额外 LLM 调用
- **WHEN** _select_skill() 完成评分并选出最优 Skill
- **THEN** 理由 SHALL 从评分过程中收集的命中信号列表直接生成，不调用 LLM，确保零额外延迟和 token 消耗
