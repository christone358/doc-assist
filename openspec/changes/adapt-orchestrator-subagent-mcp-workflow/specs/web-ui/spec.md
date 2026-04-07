## ADDED Requirements

### Requirement: Web UI SHALL 展示主子协作执行链路
Web UI SHALL 基于结构化事件展示 Orchestrator 规划、Skill 调度和 Skill 执行过程。

#### Scenario: 展示规划与调度阶段
- **WHEN** Orchestrator 开始处理一个需要委派的任务
- **THEN** Web UI SHALL 能展示规划开始、Skill 选择和 Skill 启动等关键阶段

#### Scenario: 展示执行阶段与完成状态
- **WHEN** Skill 执行过程中发生资源读取、澄清、写作完成或失败
- **THEN** Web UI SHALL 能展示这些结构化事件及其状态，而不是仅依赖零散文本提示

### Requirement: Web UI 展示链路时保持思维边界
Web UI SHALL 展示执行链路摘要，但不得直接展示内部原始思维文本。

#### Scenario: 用户查看执行链路
- **WHEN** 用户展开执行链路详情
- **THEN** Web UI SHALL 展示结构化阶段、状态和摘要，而不是直接渲染主 Agent 或子 Agent 的原始内部推理文本
