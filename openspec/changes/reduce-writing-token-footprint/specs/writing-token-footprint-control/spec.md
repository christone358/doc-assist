## ADDED Requirements

### Requirement: 写作链路记录整轮与分阶段 token 用量
系统 SHALL 为每轮写作记录整轮聚合 token 用量，并分别记录 orchestrator、subagent、write_document 和 context_summary 等阶段的 token 明细。

#### Scenario: 单轮写作聚合多次 LLM 调用
- **WHEN** 一轮写作中发生多次 LLM 调用
- **THEN** 系统 SHALL 为该轮生成整轮聚合 usage，并为每次调用归类到对应执行阶段的 usage breakdown

#### Scenario: 某阶段缺少 provider usage
- **WHEN** 某个阶段的 provider 未返回原生 usage
- **THEN** 系统 SHALL 在 breakdown 中保留该阶段条目并标记 usage 缺失原因，且整轮聚合仅累加可用阶段

### Requirement: 写作上下文按来源分层并受预算控制
系统 SHALL 在构建写作 prompt 前对 facts、skill resources、docs 和 draft 进行分层收集、去重、优先级排序和预算裁剪，不得无上限拼接所有已加载原文。

#### Scenario: 写作上下文超出预算
- **WHEN** 某轮写作的候选上下文超过默认预算
- **THEN** 系统 SHALL 按来源优先级保留高价值内容，并对低优先级内容执行摘要化或裁剪，而不是继续全量注入

#### Scenario: 同一资源被多次加载
- **WHEN** 同一路径或同一逻辑资源被重复加载到写作上下文
- **THEN** 系统 SHALL 只在最终写作 prompt 中保留一次，并在 context metrics 中记录去重结果

### Requirement: 工具历史与写作 working context 分离
系统 SHALL 将“大体量原文进入 working context”和“摘要进入 ADK 历史”明确分离，避免同一内容在推理历史和最终写作 prompt 中重复消耗 token。

#### Scenario: MCP 工具加载模块事实或原型页
- **WHEN** `facts.*`、`prototypes.*`、`docs.*` 或 `skill.read_resource` 加载到大体量正文
- **THEN** 返回给 Agent 历史的 tool result SHALL 仅包含摘要，而原始正文 SHALL 仅保留在当轮 working context 中供写作阶段使用

#### Scenario: 写作阶段消费 working context
- **WHEN** `write_document` 构建最终写作 prompt
- **THEN** 它 SHALL 只消费分层 working context，而不依赖 tool result 历史中的大段原文

### Requirement: 写作摘要生成使用低成本输入
系统 SHALL 使用结构化结果和有限正文 excerpt 生成跨轮续写摘要，不得默认再次消费大段正文和大段完成总结。

#### Scenario: 生成跨轮续写摘要
- **WHEN** 写作流程需要生成供后续轮次使用的压缩摘要
- **THEN** 系统 SHALL 优先使用文档对象、文档类型、事实来源摘要、已识别待确认项和有限正文摘要生成结果

#### Scenario: 结构化输入不足
- **WHEN** 结构化结果不足以支撑摘要生成
- **THEN** 系统 MAY 回退使用有限正文 excerpt，但 SHALL 受明确的输入长度上限约束
