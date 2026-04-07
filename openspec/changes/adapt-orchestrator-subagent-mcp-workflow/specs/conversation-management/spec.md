## ADDED Requirements

### Requirement: 对话记录 SHALL 保存结构化主子执行链路
系统 SHALL 在对话记录中保存主 Agent 与 Skill Sub-agent 的结构化执行链路信息，而不仅是普通文本轮次。

#### Scenario: 记录结构化执行结果
- **WHEN** 一次 Skill 执行完成
- **THEN** 系统 SHALL 在对应对话轮次或等价结构中分别记录结构化执行结果、必要的状态快照和执行事件，而不是将三者混为同一文本块

#### Scenario: 记录执行链路事件
- **WHEN** 主 Agent 规划、调度或 Skill 执行过程中产生可展示事件
- **THEN** 系统 SHALL 将这些事件以结构化形式记录到对话日志中

### Requirement: 对话记录 SHALL 保持主子上下文分层
系统 SHALL 在对话记录层区分主 Agent 状态、子 Agent 执行结果和展示事件，不得把子 Agent 完整推理历史直接混入主对话文本。

#### Scenario: 子 Agent 内部历史不直接写入主对话正文
- **WHEN** Skill Sub-agent 完成一次执行
- **THEN** 系统 SHALL 仅在对话记录中保存必要的结构化结果与展示事件，而不是把完整子 Agent 内部推理文本直接拼接进主对话记录

#### Scenario: 写作领域状态单独持久化
- **WHEN** 写作型子 Agent 产生或更新草稿
- **THEN** 系统 SHALL 通过 `writing_state` 或等价的领域状态结构持久化草稿状态，而不是把草稿正文写入主 Agent 的结构化执行结果
