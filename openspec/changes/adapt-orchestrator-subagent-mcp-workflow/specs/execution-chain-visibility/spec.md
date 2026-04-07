## ADDED Requirements

### Requirement: 系统 SHALL 以结构化事件展示主子协作执行链路
系统 SHALL 为主 Agent 规划、Skill 调度和 Skill 执行过程输出结构化事件，以支持前端展示和对话记录。

#### Scenario: 执行链路包含规划与调度事件
- **WHEN** Orchestrator 接收用户任务并进入处理流程
- **THEN** 系统 SHALL 输出可展示的结构化事件，至少覆盖规划开始、Skill 选择、Skill 启动和完成/失败等关键阶段

#### Scenario: 执行链路包含资源与澄清事件
- **WHEN** Skill 执行过程中发生资源读取或用户澄清
- **THEN** 系统 SHALL 输出资源加载和澄清相关的结构化事件，供展示层理解执行进展

#### Scenario: 领域状态更新不通过展示事件回灌主 Agent
- **WHEN** 子 Agent 在执行过程中更新草稿或其他领域状态
- **THEN** 系统 SHALL 将其作为状态更新或状态快照处理，而不是要求主 Agent 通过展示事件重新理解完整领域产物

### Requirement: 执行链路展示不得直接暴露内部思维文本
系统 MUST 将“可展示执行过程”与“内部思维文本”区分处理。

#### Scenario: 展示层只接收安全事件
- **WHEN** 前端或日志系统消费执行链路
- **THEN** 系统 SHALL 提供经过抽象的执行事件，而不是直接透传原始 chain-of-thought 或完整内部 reasoning 文本
