## ADDED Requirements

### Requirement: 写作前所需事实信息必须已准备就绪
Agent SHALL 确保在生成文档时，写作所依赖的项目事实信息已经收集完毕。收集的时机和范围由 Agent 根据用户意图和 Skill 的上下文需求自主决定，不由代码强制规定执行顺序。

#### Scenario: 新编写时先收集后写作
- **WHEN** Agent 判断当前任务需要项目事实信息时
- **THEN** Agent SHALL 先完成必要的事实收集，再执行文档写作，确保写作时上下文充足

#### Scenario: 修改时无需重新收集
- **WHEN** Agent 判断当前任务是基于已有草稿的修改时
- **THEN** Agent SHALL 直接进入写作，不重复收集已有草稿所涵盖的项目事实

#### Scenario: 收集范围由 Agent 自主判断
- **WHEN** Agent 决定收集项目事实时
- **THEN** 收集的内容和深度 SHALL 由 Agent 根据 Skill 的上下文需求和用户意图推理决定，而非由固定规则规定必须收集哪些类型

### Requirement: 写作阶段只接收事实收集的结果
文档写作 SHALL 基于清晰的上下文进行，写作时的输入只包含收集到的事实内容，不包含收集过程中的推理过程。

#### Scenario: 写作输入上下文干净
- **WHEN** Agent 执行文档写作时
- **THEN** 写作所使用的上下文 SHALL 只包含：Skill 写作指令、已收集的事实内容、用户原始意图，不包含事实收集过程中的推理痕迹
