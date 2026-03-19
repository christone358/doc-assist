## ADDED Requirements

### Requirement: Web UI 提供 LLM 模型配置管理界面
Web 应用应该提供一个界面让用户配置和管理 LLM 模型，支持 DeepSeek 和 QWen。

#### Scenario: LLM 模型配置页面
- **WHEN** 用户访问系统的 LLM 配置管理页面
- **THEN** Web UI 应该显示：
  1. 已配置的 LLM 模型列表（显示模型名称、提供商、配置名称、状态）
  2. 添加新配置的按钮
  3. 编辑已有配置的选项
  4. 删除配置的选项
  5. 设置默认使用模型的选项

#### Scenario: 添加新 LLM 配置
- **WHEN** 用户点击"添加配置"
- **THEN** Web UI 应该显示配置表单，包含：
  1. **配置名称** - 此配置的标识（如"生产环境 DeepSeek"）
  2. **模型提供商** - 下拉选择（DeepSeek / QWen）
  3. **模型名称** - 输入框，可输入具体模型版本
  4. **API 地址** - 输入 LLM 服务的 API 端点
  5. **API 令牌** - 密码输入框，输入 API Key（显示为掩码）
  6. **高级参数**（可折叠）：
     - 温度（Temperature）- 滑块或数字输入（0-2）
     - 最大令牌数（Max Tokens）- 数字输入
     - Top-P - 数字输入（0-1）
     - 其他参数 - 可选的自定义参数

#### Scenario: 配置验证
- **WHEN** 用户填完配置表单并点击"保存"
- **THEN** Web UI 应该：
  1. 验证必填字段
  2. 提供"测试连接"按钮，验证 API 是否可用
  3. 如验证失败，显示清晰的错误提示
  4. 保存配置并返回配置列表

#### Scenario: 编辑已有配置
- **WHEN** 用户点击配置列表中的"编辑"
- **THEN** Web UI 应该：
  1. 加载当前配置信息到表单
  2. API 令牌显示为掩码（出于安全考虑）
  3. 允许用户修改配置
  4. 保存后刷新列表

#### Scenario: 删除配置
- **WHEN** 用户点击配置列表中的"删除"
- **THEN** Web UI 应该：
  1. 显示确认对话框（"确定要删除该配置吗？"）
  2. 提示如果该配置是默认配置的警告
  3. 确认后删除配置

#### Scenario: 设置默认模型
- **WHEN** 用户在配置列表中选择一个配置作为默认
- **THEN** Web UI 应该：
  1. 标记该配置为"默认"
  2. Agent 后续使用该默认配置调用 LLM
  3. 用户可随时切换默认配置

#### Scenario: 模型配置的安全提示
- **WHEN** 用户在 LLM 配置页面
- **THEN** Web UI 应该：
  1. 显示安全提示（"API 令牌不会被发送到外部服务器"、"令牌仅存储在本地"等）
  2. 提示用户定期更新令牌
  3. 不在任何地方显示完整的令牌内容

### Requirement: Web UI 提供自然语言输入界面
Web 应用应该提供一个用户友好的界面，让用户用自然语言描述文档编写需求。

#### Scenario: 提交文档需求
- **WHEN** 用户在输入框中输入文档编写需求并点击提交
- **THEN** Web UI 应该将请求发送给 Agent，并显示处理中的状态

#### Scenario: 清空和重置
- **WHEN** 用户需要重新开始新的文档编写任务
- **THEN** Web UI 应该提供清空输入框和历史记录的选项

### Requirement: Web UI 显示可用 Skill 列表
Web 应用应该向用户显示当前系统中可用的 Skill，让用户了解系统的能力。

#### Scenario: 显示 Skill 列表
- **WHEN** 用户访问 Web UI 的 Skill 管理页面
- **THEN** 系统应该显示所有可用 Skill 的列表，包括名称、描述、支持的文档类型

#### Scenario: 查看 Skill 详情
- **WHEN** 用户点击 Skill 列表中的某个 Skill
- **THEN** Web UI 应该显示该 Skill 的详细信息（参数要求、输入格式等）

### Requirement: Web UI 实时反馈执行进度
Web 应用应该实时显示文档生成过程的进度和状态。

#### Scenario: 实时状态更新
- **WHEN** Agent 执行文档生成任务
- **THEN** Web UI 应该实时显示进度（如"正在调度 Skill"、"Skill 执行中"、"文档生成完成"）

#### Scenario: 错误提示
- **WHEN** 文档生成过程中发生错误
- **THEN** Web UI 应该清晰地显示错误信息和可能的解决方案

### Requirement: Web UI 展示文档生成结果
文档生成完成后，Web UI 应该显示生成文档的文件路径和文件名，用户可以在本地打开查看。

#### Scenario: 显示文档保存位置
- **WHEN** 文档生成完成
- **THEN** Web UI 应该显示：
  1. 文档的完整保存路径（相对于 docs/ 目录）
  2. 文件名（包含版本号）
  3. 生成时间
  4. 文件大小（可选）

#### Scenario: 快速定位文档
- **WHEN** 用户查看生成结果
- **THEN** Web UI 应该提供：
  1. 复制文件路径按钮（便于在文件系统中快速定位）
  2. 打开文件夹按钮（可选，打开包含该文档的目录）
  3. 对话记录中的关联链接（点击可快速找到该文档）

#### Scenario: 多个文档生成
- **WHEN** 一次对话中生成多个文档
- **THEN** Web UI 应该：
  1. 列出所有生成的文档及其路径
  2. 按文档类型分组显示（可选）
  3. 标记每个文档的版本号和生成时间

### Requirement: Web UI 支持多轮对话交互
Web UI 应该提供多轮对话界面，让用户与 Agent 进行交互式的需求描述、反馈和修正。

#### Scenario: 对话界面设计
- **WHEN** 用户启动文档编写任务
- **THEN** Web UI 应该：
  1. 提供类似聊天应用的对话界面
  2. 显示用户消息和 Agent 响应的对话历史
  3. 在界面底部提供输入框用于持续交互
  4. 支持清晰的消息区分（用户、Agent、系统提示）

#### Scenario: 对话流程
- **WHEN** 用户进行多轮对话
- **THEN** Web UI 应该支持以下对话流程：
  1. **初始请求**：用户描述文档编写需求
  2. **Agent 理解**：Agent 展示理解的需求并提出澄清问题
  3. **用户反馈**：用户提供更多信息或确认选择
  4. **Agent 执行**：Agent 调度 Skill 生成文档
  5. **结果展示**：显示生成的文档文件名和保存路径
  6. **用户评价**：用户提供反馈："这不对，请修改..."
  7. **迭代修改**：返回第3-5步，支持多次迭代

#### Scenario: 对话上下文显示
- **WHEN** 用户在对话中
- **THEN** Web UI 应该展示当前上下文：
  - 正在编写的文档类型和名称
  - 已确认的关键需求点
  - 当前迭代的修改焦点

#### Scenario: 中间结果保存
- **WHEN** 用户在对话过程中
- **THEN** Web UI 应该：
  1. 在每一轮生成后保存中间结果
  2. 显示当前的最新版本
  3. 标记哪些版本是已确认的、哪些是草稿
  4. 支持用户快速查看和切换版本

#### Scenario: 对话管理
- **WHEN** 用户进行对话
- **THEN** Web UI 应该提供：
  - **保存会话**：保存当前对话和所有中间结果
  - **开新对话**：清空当前对话，开始新的文档编写任务
  - **查看历史对话**：查看之前的对话记录和生成结果

### Requirement: Web UI 展示 LLM 思考摘要（可选）
Web UI 可以选择性地展示 LLM 的思考过程摘要，帮助用户理解 Agent 的决策。

#### Scenario: 思考过程透明化
- **WHEN** Agent 使用深度思考模式进行分析
- **THEN** Web UI 应该支持选项性地展示：
  - LLM 如何理解用户的需求
  - 选择特定 Skill 的原因
  - 生成的修改方案的理由

#### Scenario: 思考摘要折叠/展开
- **WHEN** 用户查看 Agent 的响应
- **THEN** Web UI 应该：
  1. 默认显示简洁的结论
  2. 提供"显示思考过程"按钮
  3. 允许用户展开查看详细的思考摘要
  4. 支持用户反复折叠/展开


### Requirement: Web UI 反馈和建议展示
Agent 应该主动向用户提供反馈和建议，Web UI 需要清晰地展示这些内容。

#### Scenario: Agent 提出澄清问题
- **WHEN** Agent 对用户需求有疑问
- **THEN** Web UI 应该：
  1. 清晰地展示 Agent 提出的问题
  2. 如果有多个选项，提供选项列表或按钮供用户快速选择
  3. 允许用户输入自由文本回答

#### Scenario: Agent 提供修改建议
- **WHEN** Agent 分析出可能的改进方向
- **THEN** Web UI 应该：
  1. 展示建议内容和理由
  2. 提供"接受"、"拒绝"或"修改建议"等按钮
  3. 如用户接受，直接应用到文档中

### Requirement: 消息气泡底部展示 Skill 与 token 元信息栏
Web UI SHALL 在每条 assistant 消息气泡底部渲染一个 meta bar，展示本轮调用的 Skill 标签和 token 统计。

#### Scenario: 流式完成后渲染 meta bar
- **WHEN** WebSocket 接收到 done chunk 且其中包含 skill 或 usage 数据
- **THEN** Web UI SHALL 在当前 assistant 消息气泡下方渲染 meta bar

#### Scenario: meta bar 仅在 done 后显示
- **WHEN** 流式输出进行中（done chunk 尚未到达）
- **THEN** Web UI SHALL 不显示 meta bar，避免数据不完整时闪烁

#### Scenario: 历史消息中展示 meta bar
- **WHEN** 用户打开历史对话，某轮消息的 skill_invoked 或 llm_info 字段有数据
- **THEN** Web UI SHALL 为该轮消息渲染对应的 meta bar
