## ADDED Requirements

### Requirement: Agent 流式事件 SHALL 携带执行对象归属信息
Agent 在向前端发送流式过程事件时 SHALL 携带足够的对象标识信息，使展示层能够稳定构建 LLM、工具、Skill、提问和系统状态对象，而不是依赖文本和时间顺序推断。

#### Scenario: 工具调用事件携带对象标识
- **WHEN** Agent 发出工具开始、工具结果或执行事件
- **THEN** 对应消息 SHALL 包含稳定的对象标识和状态信息，使前端能够将开始和完成状态归并到同一个工具调用对象

#### Scenario: Skill 链路事件携带父子关系
- **WHEN** Agent 进入 Skill 委派并在其内部继续执行思考或工具调用
- **THEN** 对应流式事件 SHALL 携带父子关系信息，使前端能够把这些事件归并到所属 Skill 对象下

#### Scenario: 提问和系统状态事件也带对象标识
- **WHEN** Agent 发出澄清提问、等待用户回复、执行完成或执行失败等关键过程事件
- **THEN** 对应消息 SHALL 携带稳定的对象标识和对象类型，使这些状态能纳入统一的过程明细模型

#### Scenario: 所有对象携带稳定排序依据
- **WHEN** Agent 首次发出某个执行对象
- **THEN** 对应消息 SHALL 携带稳定的创建时序信息，使前端能够按创建顺序展示对象而不依赖接收时机猜测

### Requirement: Agent SHALL 为工具过程提供结构化输入输出观测数据
Agent 发出的工具相关流式事件 SHALL 支持展示输入、输出摘要和详细信息，而不是只提供零散状态文本。

#### Scenario: 发出工具输入信息
- **WHEN** Agent 发起一次工具调用
- **THEN** 流式事件 SHALL 包含 `display_input` 字段，用于提供可展示输入摘要

#### Scenario: 发出工具输出摘要和详情
- **WHEN** 工具调用完成
- **THEN** 流式事件 SHALL 包含 `output_preview` 和 `output_detail` 字段；其中 `output_detail` 可为空，但字段不可缺失

#### Scenario: 工具观测数据在发送前完成可展示化
- **WHEN** 工具参数或结果包含高体积正文、内部 prompt、绝对路径或敏感字段
- **THEN** Agent SHALL 在流式事件中发送脱敏、摘要化或截断后的 UI 字段，而不是直接透传原始对象

### Requirement: Agent SHALL 对过程明细字段实施预算控制
Agent 在发送和持久化过程明细字段时 SHALL 实施统一的预算控制，避免对象化后无限放大消息体和历史存储。

#### Scenario: 流式事件只发送预算内字段
- **WHEN** Agent 发送包含 `display_input`、`output_preview` 或 `output_detail` 的流式事件
- **THEN** 这些字段 SHALL 被限制在预算范围内，超出部分必须截断或摘要化

#### Scenario: 历史持久化不保存原始 detail 全文
- **WHEN** Agent 将过程事件持久化到会话历史
- **THEN** 系统 SHALL 持久化预算后的可展示字段，而不是另外保存未裁剪的原始 detail 全文

#### Scenario: 截断结果可被用户识别
- **WHEN** 某个可展示字段因预算限制被截断
- **THEN** Agent SHALL 在对应字段或其元信息中表达“内容已截断”的语义
