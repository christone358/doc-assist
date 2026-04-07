## ADDED Requirements

### Requirement: 系统 SHALL 以执行对象节点输出可展示的过程明细
系统 SHALL 将右侧过程明细所需的执行信息组织为稳定的对象节点，而不是仅依赖线性事件文本。对象节点至少覆盖 `llm_thought`、`tool_call`、`skill_call`、`user_question`、`system_state` 五类。

#### Scenario: 为每个对象生成稳定标识
- **WHEN** Orchestrator、Sub-agent 或运行时开始一个可展示的执行对象
- **THEN** 系统 SHALL 为该对象生成稳定的 `node_id`，并输出对象类型、标题、状态和所属 actor

#### Scenario: 通过父子关系表达 Skill 内部过程
- **WHEN** Skill 执行过程中产生思考节点或工具调用节点
- **THEN** 系统 SHALL 为这些子对象设置 `parent_node_id` 指向所属的 Skill 对象节点，使展示层能够按 Skill 聚合其内部执行过程

#### Scenario: 提问和收尾状态具有稳定对象归属
- **WHEN** 运行时进入等待用户澄清、执行完成或执行失败等关键状态
- **THEN** 系统 SHALL 以 `user_question` 或 `system_state` 对象节点表达这些状态，而不是让它们游离于对象模型之外

#### Scenario: Skill 内部问题和状态遵循单一归属
- **WHEN** 某个提问或状态只描述某个 Skill 的内部执行过程
- **THEN** 系统 SHALL 将其归属到对应的 `skill_call` 节点下，而不得同时在顶层重复创建同语义对象

#### Scenario: 会话级问题和状态保持顶层展示
- **WHEN** 某个提问或状态描述整轮流程，例如等待用户继续输入、主链路完成或主链路失败
- **THEN** 系统 SHALL 将其作为顶层 `user_question` 或 `system_state` 对象展示

### Requirement: 系统 SHALL 为状态节点采用确定的生成规则
系统 SHALL 使用确定的状态节点生成规则，避免父节点状态与独立 `system_state` 节点重复表达同一语义。

#### Scenario: Skill 内部失败优先更新 Skill 节点
- **WHEN** 某个失败只描述单个 Skill 的内部执行
- **THEN** 系统 SHALL 优先更新对应 `skill_call` 节点状态，并且不得同时在顶层创建同语义失败状态节点

#### Scenario: 会话级失败生成顶层状态节点
- **WHEN** 某个失败描述整轮主链路失败
- **THEN** 系统 SHALL 生成顶层 `system_state` 节点表达该失败

#### Scenario: 提问后不重复生成同语义等待状态
- **WHEN** 系统已经生成用于等待用户回复的 `user_question` 节点
- **THEN** 系统 SHALL 不再额外生成同语义的等待型 `system_state` 节点

### Requirement: 工具调用节点 SHALL 携带输入、输出摘要和可展开详情
每个工具调用对象 SHALL 提供稳定的输入输出展示契约，支持在右侧过程面板中查看调用参数、结果摘要和可折叠的详细信息。

#### Scenario: 工具开始时记录输入信息
- **WHEN** 主 Agent 或子 Agent 发起一次工具调用
- **THEN** 系统 SHALL 在对应 `tool_call` 节点中记录工具名称、来源类型、执行状态和 `display_input`

#### Scenario: 工具完成时记录输出信息
- **WHEN** 工具调用完成
- **THEN** 系统 SHALL 在同一 `tool_call` 节点中补充 `output_preview` 和 `output_detail`，而不是仅输出一条无法归属的结果文本

#### Scenario: 工具详情在展示前完成脱敏与裁剪
- **WHEN** 工具输入或输出包含大段正文、提示词、绝对路径、敏感字段或高体积内容
- **THEN** 系统 SHALL 在发送到前端前将其转换为可展示版本，进行脱敏、摘要化或截断，而不是原样透传

#### Scenario: 工具节点具备固定最小字段
- **WHEN** 系统输出任意一个 `tool_call` 节点
- **THEN** 该节点 SHALL 至少包含 `display_input`、`output_preview` 和 `output_detail` 三个 UI 字段；其中 `output_detail` 可为空，但字段不可缺失

#### Scenario: 正式正文类工具不在右侧复制最终正文
- **WHEN** 工具输出属于左侧正式结果区的正文产物，例如文档生成结果
- **THEN** 系统 SHALL 在右侧工具节点中仅展示摘要、状态和必要元信息，而不得把完整正式正文直接复制到过程详情中

### Requirement: Skill 调用节点 SHALL 聚合选择原因和子执行过程
每个 Skill 调用对象 SHALL 作为父级容器展示其状态、选择原因、交接摘要和下属执行对象。

#### Scenario: Skill 选择后创建 Skill 对象节点
- **WHEN** Orchestrator 确定并委派某个 Skill
- **THEN** 系统 SHALL 创建一个 `skill_call` 节点，并记录 Skill 标识、显示名称和选择原因

#### Scenario: Skill 节点展示执行完成状态
- **WHEN** 子 Agent 完成或失败
- **THEN** 系统 SHALL 在对应 `skill_call` 节点上更新最终状态，并使展示层能够在 Skill 容器中查看其内部思考和工具链路

#### Scenario: Skill 内部对象不在顶层重复展示
- **WHEN** 某个思考节点或工具节点已经归属于某个 Skill 调用节点
- **THEN** 展示层 SHALL 仅在该 Skill 容器内部展示该对象，而不得在顶层再重复渲染同一对象

### Requirement: 执行对象 SHALL 以稳定顺序展示
系统 SHALL 为所有执行对象提供稳定排序依据，避免对象化后出现顺序漂移。

#### Scenario: 顶层对象按创建顺序展示
- **WHEN** 一轮对话产生多个顶层执行对象
- **THEN** 展示层 SHALL 按对象首次创建时间升序展示这些对象，而不是按对象类型重新排序

#### Scenario: Skill 子对象按创建顺序展示
- **WHEN** 某个 Skill 容器下产生多个子对象
- **THEN** 展示层 SHALL 按这些子对象的首次创建时间升序展示，而不是按对象类型重新排序

### Requirement: 系统 SHALL 为历史轮次提供兼容回放
系统 SHALL 允许缺少对象节点字段的历史轮次在新过程面板中回放，而不要求先做历史数据迁移。

#### Scenario: 历史轮次缺少对象节点字段
- **WHEN** 用户打开仅包含旧事件格式的历史对话轮次
- **THEN** 系统 SHALL 通过回退归一化逻辑构造只读过程视图，而不得让右侧面板空白或报错

#### Scenario: 回退视图不要求补齐全部增强字段
- **WHEN** 回退归一化逻辑处理旧事件格式
- **THEN** 系统 MAY 缺省部分增强字段，但 SHALL 保证 Skill、工具、提问和关键状态可读

### Requirement: 思考节点 SHALL 仅包含可展示的详细思考记录
系统 MUST 将“可展示的详细思考记录”与 provider/raw chain-of-thought 区分处理。

#### Scenario: 展示详细思考记录
- **WHEN** 运行时显式发出可展示的思考文本块
- **THEN** 系统 SHALL 将其作为 `llm_thought` 节点供右侧面板展示完整的可展示思考记录文本，而不是尝试补全模型内部全部推理过程

#### Scenario: 不直接暴露 raw reasoning
- **WHEN** 模型内部存在未经过滤的原始 chain-of-thought 或其他隐藏 reasoning
- **THEN** 系统 MUST NOT 将该内容直接作为右侧过程明细节点发送给前端
