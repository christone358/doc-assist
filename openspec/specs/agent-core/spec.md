## ADDED Requirements

### Requirement: Agent 访问项目事实信息
Agent SHALL 通过结构化的多步骤流程访问项目事实信息，替代原有的关键词扫描方式，实现精确的按模块、按类型加载。

#### Scenario: 上下文需求推断步骤
- **WHEN** Agent 选定 Skill 后，准备加载上下文时
- **THEN** Agent SHALL 执行上下文需求推断（LLM 推断或读取显式声明），得到 required 和 optional 词汇列表，并在日志中记录推断结果

#### Scenario: 模块定位步骤
- **WHEN** Agent 执行上下文推断后
- **THEN** Agent SHALL 从用户消息中提取目标模块名，通过精确匹配、LLM 语义匹配两级策略定位模块 ID，并在 status step 中展示定位结果

#### Scenario: 一次性加载所有推断上下文
- **WHEN** 模块 ID 定位完成后
- **THEN** Agent SHALL 按词汇列表逐项加载，每项按模块 ID 过滤，只加载目标模块相关的条目，并在 status step 中展示加载摘要

#### Scenario: modules.md 始终作为基础上下文
- **WHEN** Agent 执行任何文档生成任务时
- **THEN** modules.md SHALL 始终被加载，无论 required 列表内容如何，因为它提供项目全貌和检索入口

### Requirement: Agent 上下文加载过程可观测
Agent 的上下文加载决策和执行过程 SHALL 对用户和开发者可见。

#### Scenario: status steps 展示加载行为
- **WHEN** Agent 执行上下文加载时
- **THEN** 以下步骤 SHALL 在 status steps 中展示：
  - "已定位模块: {模块名}（{module-id}）"（定位成功时）
  - "未识别到目标模块"（定位失败时，随后中断并输出引导文字）
  - "加载项目上下文：modules（N个）: {模块名1}、{模块名2}... · {词汇}: {条目名1}、{条目名2} 等N条"

#### Scenario: 上下文加载 status step 展示条目名称
- **WHEN** Agent 完成上下文加载时
- **THEN** "加载项目上下文" status step SHALL 展示各词汇实际加载的条目名称：
  - modules 词汇：展示所有模块名（最多5个，超出显示省略号）
  - usecases / classes / interfaces 词汇：展示前3条条目名称，超出3条显示「等N条」
  - 各词汇之间以「·」分隔

#### Scenario: 日志记录推断和加载详情
- **WHEN** 上下文推断和加载完成时
- **THEN** 系统 SHALL 在日志中记录：推断来源、词汇列表、模块 ID、各词汇实际加载的条目数和文件路径

### Requirement: Agent 理解用户自然语言文档需求
Agent 应该能够接收用户的自然语言输入（文档需求描述），理解其中的关键信息（文档类型、项目背景、特定要求等），并提取结构化的需求数据。

#### Scenario: 用户提交文档需求
- **WHEN** 用户通过 Web UI 输入文档编写需求（例如："我需要一份技术设计文档来说明用户认证系统的架构"）
- **THEN** Agent 应该识别出文档类型为"技术设计文档"，并提取相关的上下文信息

#### Scenario: 歧义处理
- **WHEN** 用户的输入不够明确（例如缺少文档类型）
- **THEN** Agent 应该返回消息要求用户澄清或提供下拉选择的文档类型列表

### Requirement: Agent 匹配并调度合适的 Skill
Agent 应该根据解析的需求数据，从注册的 Skill 中选择最合适的一个或多个，并将需求参数传递给 Skill 执行。

#### Scenario: 单个 Skill 调度
- **WHEN** 用户需求匹配到唯一的 Skill
- **THEN** Agent 自动调度该 Skill，传递必要的参数和上下文

#### Scenario: 多个 Skill 协同（可选）
- **WHEN** 用户需求可能需要多个 Skill 组合
- **THEN** Agent 提示用户选择，或根据优先级自动选择主 Skill

### Requirement: Agent 接收并聚合 Skill 执行结果
Agent 应该等待 Skill 的执行完成，接收执行结果（生成的文档内容或错误信息），并返回给用户。

#### Scenario: Skill 执行成功
- **WHEN** Skill 成功执行并返回生成的文档
- **THEN** Agent 将结果返回给 Web UI，用户可以看到生成的文档

#### Scenario: Skill 执行失败
- **WHEN** Skill 执行过程中出现错误
- **THEN** Agent 捕获错误信息，返回友好的错误提示，允许用户修改参数重试

### Requirement: Agent 支持精准修改和版本管理
Agent 应该能够识别用户的修改需求，加载文档的上一版本，基于上一版本进行精准修改，并生成修改差异展示。

#### Scenario: 识别修改需求
- **WHEN** 用户输入指示修改的自然语言（例如："请修改需求文档中的用户认证部分"或"更新第3节的内容"）
- **THEN** Agent 应该识别出这是一个修改需求，而非新增编写

#### Scenario: 加载文档版本
- **WHEN** Agent 识别出修改需求时
- **THEN** Agent 应该：
  1. 识别要修改的文档类型和名称
  2. 从版本管理系统加载该文档的最新版本
  3. 向用户展示当前版本信息（版本号、修改时间等）

#### Scenario: 精准修改执行
- **WHEN** Agent 获取到文档版本和修改需求时
- **THEN** Agent 应该调度对应的 Skill 进行修改，传递：
  - 原始文档内容
  - 修改指令（哪个部分、如何修改）
  - 文档上下文（项目信息、编写规范等）

#### Scenario: 修改差异展示
- **WHEN** Skill 完成修改后返回新版本内容
- **THEN** Agent 应该：
  1. 计算修改前后的差异
  2. 生成类似代码 diff 的修改对比（展示删除行、新增行、修改行）
  3. 返回修改差异信息给 Web UI 展示

#### Scenario: 修改不明确处理
- **WHEN** Agent 无法完全理解用户的修改意图
- **THEN** Agent 应该与用户进行交互澄清：
  - 提出具体问题：要修改哪个部分？如何修改？
  - 展示候选修改位置供用户确认
  - 询问修改目标和期望结果

### Requirement: Agent 提供 Skill 发现接口
Agent 应该提供接口让用户和前端发现当前系统中可用的 Skill，包括每个 Skill 的描述、支持的文档类型、所需参数等。

#### Scenario: 查询可用 Skill 列表
- **WHEN** Web UI 请求 Agent 获取可用 Skill 列表
- **THEN** Agent 返回所有已注册 Skill 的元数据（名称、描述、支持的文档类型）

#### Scenario: 查询 Skill 详细信息
- **WHEN** 用户需要了解某个 Skill 的具体参数和使用方式
- **THEN** Agent 返回该 Skill 的详细规格（输入参数、参数类型、是否必需等）

### Requirement: Agent 支持多轮对话交互
Agent 应该支持多轮对话模式，允许用户与 Agent 进行交互式的文档编写需求描述、反馈和修正。

#### Scenario: 对话上下文维护
- **WHEN** 用户启动文档编写任务后进行多次交互
- **THEN** Agent 应该：
  1. 维护完整的对话历史和上下文
  2. 记住用户在之前对话中的需求、反馈和修正
  3. 在后续交互中参考这些历史信息
  4. 支持对话重新开始或分支

#### Scenario: 初始需求描述
- **WHEN** 用户首次提交文档编写需求
- **THEN** Agent 应该：
  - 理解需求并提出澄清问题（如需要）
  - 展示理解的需求概览
  - 邀请用户提供更多细节或反馈

#### Scenario: 反馈和修正
- **WHEN** 用户对生成的结果不满意或需要调整
- **THEN** Agent 应该：
  - 接收用户的反馈（可以是自然语言描述）
  - 理解用户的修正意图
  - 基于反馈重新调整或重新生成文档
  - 展示修改内容和差异
  - 再次邀请用户反馈

#### Scenario: 逐步完善
- **WHEN** 用户通过多轮对话逐步完善文档
- **THEN** Agent 应该：
  - 在每一轮中保存中间结果
  - 支持用户查看修改历史
  - 支持用户选择回到之前的版本
  - 支持用户在某个版本基础上继续修改

#### Scenario: 对话结束和输出
- **WHEN** 用户确认文档完成
- **THEN** Agent 应该：
  - 将最终的文档保存为新版本
  - 记录对话过程中的所有修改
  - 提供完整的对话记录和版本历史
  - 清空对话状态或保存对话记录供后续查看

### Requirement: Agent 调用 LLM 的深度思考模式
Agent 应该能够调用 LLM 的高级推理能力（如 Extended Thinking、Chain-of-Thought 等），以充分理解用户的复杂需求。

#### Scenario: 复杂需求的深度理解
- **WHEN** 用户提交复杂或模糊的文档编写需求
- **THEN** Agent 应该：
  1. 调用 LLM 的深度思考模式
  2. 让 LLM 进行多步推理分析用户需求
  3. 分解复杂需求为多个子任务或修改点
  4. 提出具体的澄清问题

#### Scenario: 思考过程透明化
- **WHEN** 用户需要了解 Agent 的决策过程
- **THEN** Agent 应该选择性地展示 LLM 的思考内容：
  - Agent 如何理解用户需求
  - 为什么选择特定的 Skill
  - 可能的修改方案和权衡分析

#### Scenario: 多轮对话中的思考模式
- **WHEN** 用户提供反馈或修正
- **THEN** Agent 应该：
  1. 调用 LLM 深度思考模式理解反馈含义
  2. 分析反馈对现有文档的影响
  3. 生成修改方案和理由
  4. 向用户展示修改建议

#### Scenario: 修改意图的精准理解
- **WHEN** 用户的修改意图不明确或存在歧义
- **THEN** Agent 应该：
  1. 调用 LLM 深度思考分析可能的意图
  2. 列出多个理解的可能性
  3. 向用户逐一确认
  4. 基于确认的意图执行修改

#### Scenario: 高质量建议生成
- **WHEN** Agent 需要为用户提出修改建议或改进建议
- **THEN** Agent 应该：
  1. 调用 LLM 深度思考模式进行分析
  2. 考虑多个改进角度（结构、内容、风格等）
  3. 为每个建议提供理由和示例
  4. 让用户选择是否接受建议

### Requirement: Agent 流式响应携带 Skill 和 token 元数据
Agent 在完成流式响应时 SHALL 在 done chunk 中附带本轮选择的 Skill 信息（含选择推理）和 token 用量数据，供前端展示和持久化使用。

#### Scenario: skill_start chunk 携带选择理由
- **WHEN** Agent 确定要使用某个 Skill，发出 skill_start chunk
- **THEN** skill_start chunk SHALL 包含 reason 字段，值为人类可读的中文选择理由字符串（由匹配信号推导，如"文档类型「design」吻合；关键词「设计」命中能力范围"）

#### Scenario: done chunk 携带完整元数据
- **WHEN** Agent 完成一轮流式响应
- **THEN** 发出的 done chunk SHALL 包含：skill_id（选中的 Skill ID，可为 null）、skill_name（Skill 显示名，可为 null）、skill_reason（选择推理字符串，可为 null）、usage（含 prompt_tokens/completion_tokens/total_tokens 的对象，不可用时为 null）

#### Scenario: 未匹配 Skill 时 done chunk 中字段为 null
- **WHEN** 本轮未匹配到任何 Skill
- **THEN** done chunk 中 skill_id、skill_name 和 skill_reason SHALL 为 null，usage 字段照常填充（若有）

#### Scenario: 选择理由由评分信号推导，无需额外 LLM 调用
- **WHEN** _select_skill() 完成评分并选出最优 Skill
- **THEN** 理由 SHALL 从评分过程中收集的命中信号列表直接生成，不调用 LLM，确保零额外延迟和 token 消耗
