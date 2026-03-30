## MODIFIED Requirements

### Requirement: LLM 从 Skill 声明推断上下文需求
上下文需求推断 SHALL 作为资料收集过程的一部分自然发生，不作为独立步骤执行。Agent SHALL 读取 Skill 的上下文需求声明，由 LLM 自主理解并决定加载策略，无需产生中间结构化推断结果。

#### Scenario: 推断与收集合并为一个连续过程
- **WHEN** Agent 开始为某个 Skill 收集项目事实时
- **THEN** Agent SHALL 将理解 Skill 需求和执行加载合并为一个连续过程，用户看到的是直接的加载行为，而非先输出推断列表再执行加载

#### Scenario: 无需独立推断步骤
- **WHEN** Agent 处理文档编写请求时
- **THEN** 系统 SHALL 不再有独立的"上下文需求推断"阶段，Skill 需要什么由 Agent 在收集过程中自行理解和判断

#### Scenario: 推断过程可观测
- **WHEN** Agent 执行资料收集时
- **THEN** 用户 SHALL 能看到每一步的加载行为（加载了什么、加载结果如何），而无需关心 Agent 内部如何推断出这些加载决策
