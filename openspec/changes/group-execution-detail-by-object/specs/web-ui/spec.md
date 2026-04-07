## ADDED Requirements

### Requirement: Web UI SHALL 以执行对象分组展示右侧过程明细
Web UI SHALL 将右侧“过程明细”展示为按执行对象分组的结构，而不是混合的线性时间线。顶层对象至少覆盖 LLM 思考、工具调用、Skill 调用、用户提问和系统状态。

#### Scenario: 按对象类型渲染过程明细
- **WHEN** 用户展开右侧过程明细
- **THEN** Web UI SHALL 以对象卡片而不是零散状态列表展示本轮执行过程，并清晰区分 LLM 思考、工具调用和 Skill 调用

#### Scenario: Skill 作为父级容器展示
- **WHEN** 某个 Skill 被选择并开始执行
- **THEN** Web UI SHALL 将该 Skill 渲染为可展开的父级对象，并在其下展示该 Skill 的思考节点和工具调用节点

#### Scenario: Skill 内部对象不在顶层双显
- **WHEN** 某个思考节点或工具调用节点已经属于某个 Skill 容器
- **THEN** Web UI SHALL 仅在该 Skill 容器内部渲染该对象，而不得在顶层再重复渲染

#### Scenario: Skill 内部问题和状态遵循单一归属
- **WHEN** 某个用户提问或系统状态已经归属于某个 Skill 容器
- **THEN** Web UI SHALL 仅在该 Skill 容器内部渲染该对象，而不得在顶层再重复渲染

### Requirement: Web UI SHALL 展示工具调用的输入输出信息
Web UI SHALL 在工具调用对象中展示输入、输出摘要和可折叠详情，并以“工具名称 + 执行状态”为主要标题。

#### Scenario: 工具卡片展示输入和输出摘要
- **WHEN** 某个工具调用对象有可用的输入输出信息
- **THEN** Web UI SHALL 在该工具卡片中展示输入区和输出摘要区，而不是只显示一条结果文本

#### Scenario: 工具详情默认可折叠
- **WHEN** 某个工具调用对象包含详细输出
- **THEN** Web UI SHALL 提供折叠/展开交互查看详细信息，并默认保持详细输出折叠

#### Scenario: 工具详情使用可展示版本
- **WHEN** 工具调用对象携带输入或输出字段
- **THEN** Web UI SHALL 仅展示后端提供的可展示版本，而不得自行拼接原始参数对象、原始结果或猜测性详情

#### Scenario: 工具卡片展示固定最小字段
- **WHEN** Web UI 渲染任意一个工具调用对象
- **THEN** 该卡片 SHALL 展示 `display_input` 和 `output_preview`，并为 `output_detail` 预留折叠区域，即使该详情为空

### Requirement: Web UI SHALL 以可展示思考记录呈现详细思考内容
Web UI SHALL 在右侧过程明细中展示详细思考内容，但该内容仅限于系统显式发出的可展示思考记录。

#### Scenario: 右侧展示完整思考文本块
- **WHEN** 流式事件包含可展示的思考对象
- **THEN** Web UI SHALL 在右侧过程明细中展示该思考对象完整的可展示文本内容，并支持折叠或展开查看

#### Scenario: 不渲染 raw reasoning
- **WHEN** 后端未显式提供可展示思考对象，或某段内容属于内部 raw reasoning
- **THEN** Web UI MUST NOT 通过猜测或透传方式将其渲染为右侧思考详情

### Requirement: Web UI SHALL 按稳定顺序渲染执行对象
Web UI SHALL 按执行对象的创建顺序渲染右侧过程明细，而不是按对象类型重新分组排序。

#### Scenario: 顶层对象按创建顺序渲染
- **WHEN** 本轮存在多个顶层执行对象
- **THEN** Web UI SHALL 按这些对象的首次创建顺序渲染，而不得按对象类型重排

#### Scenario: Skill 子对象按创建顺序渲染
- **WHEN** 某个 Skill 容器下存在多个子对象
- **THEN** Web UI SHALL 按这些子对象的首次创建顺序渲染，而不得按对象类型重排

#### Scenario: 实时状态更新不改变对象位置
- **WHEN** 某个执行对象在流式过程中只发生内容补充或状态更新
- **THEN** Web UI SHALL 保持该对象在列表中的原始位置，而不得因为更新重新排序或跳动

### Requirement: Web UI SHALL 支持历史轮次的回退展示
Web UI SHALL 能够在新对象面板中展示仅包含旧事件格式的历史轮次。

#### Scenario: 打开旧格式历史轮次
- **WHEN** 某个历史轮次缺少对象节点字段
- **THEN** Web UI SHALL 使用回退归一化逻辑渲染只读过程视图，而不得显示空白、错误或不完整占位
