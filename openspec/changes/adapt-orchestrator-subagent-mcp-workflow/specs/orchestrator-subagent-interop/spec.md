## ADDED Requirements

### Requirement: 主 Agent 向 Skill Sub-agent 传递最小委派 handoff
系统 SHALL 将主 Agent 到 Skill Sub-agent 的通信收敛为调度决定与连续性记忆，不得把执行期资源正文或执行路径预判作为标准 handoff 内容。

#### Scenario: 委派 handoff 只包含最小必要信息
- **WHEN** 主 Agent 决定调用 `execute_skill(...)` 委派一个 Skill Sub-agent
- **THEN** 系统 SHALL 至少传递调度决定、任务意图、上一轮压缩摘要和已有澄清记录，而不是传递 facts/docs/skill resources 的大块正文内容

### Requirement: 主 Agent 与 Skill Sub-agent 使用结构化执行协议通信
系统 SHALL 为主 Agent 与通过 `execute_skill(...)` 调度的 Skill Sub-agent 定义结构化通信协议，而不是只依赖自由文本摘要。

#### Scenario: Skill 执行完成返回结构化结果
- **WHEN** Skill Sub-agent 完成一次执行
- **THEN** 系统 SHALL 返回以执行状态、压缩摘要和失败/恢复信号为核心的结构化执行结果，供主 Agent 消费

#### Scenario: Skill 执行失败返回结构化失败结果
- **WHEN** Skill Sub-agent 在执行中失败或中断
- **THEN** 系统 SHALL 返回结构化失败结果，至少包含失败类型、失败原因和是否可重试信息

### Requirement: 领域状态与执行结果分离
系统 MUST 将子 Agent 的领域状态持久化与主 Agent 消费的执行结果分离建模。

#### Scenario: 写作型子 Agent 将草稿写入状态而不是回灌给主 Agent
- **WHEN** 写作型 Skill Sub-agent 完成一次生成或修改
- **THEN** 系统 SHALL 通过会话状态或等价状态补丁保存草稿与文档标识，而不是将草稿正文直接作为主 Agent 的结果上下文回传

#### Scenario: 非写作型子 Agent 可不产生写作领域状态
- **WHEN** 系统在未来接入非写作型子 Agent
- **THEN** 系统 SHALL 允许其复用同一主子协作协议，而不要求返回写作领域专属状态字段

### Requirement: 主子 Agent 保持上下文隔离
系统 MUST 保持主 Agent 与 Skill Sub-agent 的执行上下文隔离，不得将子 Agent 的完整推理历史直接泄漏回主 Agent。

#### Scenario: 主 Agent 不接收子 Agent 完整推理历史
- **WHEN** Skill Sub-agent 完成一次执行
- **THEN** 系统 SHALL 仅向主 Agent 返回结构化结果和压缩摘要，而不是完整内部推理文本

#### Scenario: 子 Agent 维持独立执行上下文
- **WHEN** `execute_skill(...)` 创建 Skill Sub-agent
- **THEN** 系统 SHALL 为其使用独立执行上下文，并确保主 Agent 的提示词和状态不直接混入子 Agent 的完整执行历史

#### Scenario: 子 Agent working context 在执行结束后释放
- **WHEN** Skill Sub-agent 完成本轮执行并返回结构化结果
- **THEN** 系统 SHALL 释放本轮子 Agent 的执行 working context，仅保留回传给主 Agent 所需的结构化结果和压缩摘要
