## ADDED Requirements

### Requirement: Session 注册表管理 ADK Session 生命周期
系统 SHALL 维护进程级 session 注册表，以 conversation_id 为 key，持有 ADK session_service、runner、session_id 和 agent 实例，在一个 conversation 生命周期内保持不变。

#### Scenario: 首次消息创建 session
- **WHEN** conversation 收到第一条用户消息，注册表中不存在对应 session
- **THEN** 系统 SHALL 创建 InMemorySessionService、构建 DocumentAgent、创建 Runner，生成固定 session_id（基于 conversation_id 派生，非随机），注册到表中

#### Scenario: 后续消息复用 session
- **WHEN** conversation 收到后续用户消息，注册表中已存在对应 session
- **THEN** 系统 SHALL 复用已有的 runner 和 session_id，直接调用 run_async() 追加新消息，编排 LLM 可见完整的历史事件

#### Scenario: conversation 删除时清理 session
- **WHEN** conversation 被用户删除
- **THEN** 系统 SHALL 从注册表中移除对应 session entry，释放内存

#### Scenario: Session TTL 过期自动清理
- **WHEN** session 最后活跃时间超过配置的 TTL（默认 4 小时）
- **THEN** 系统 SHALL 自动从注册表中清理该 session，下次消息到来时重建

### Requirement: 编排 LLM 通过 session 历史实现跨轮渐进式披露
编排 LLM SHALL 通过 ADK session 历史感知已加载的事实和已完成的操作，在后续轮次中不重复请求已有数据。

#### Scenario: 跨轮不重复加载事实
- **WHEN** 编排 LLM 在新一轮收到用户消息，session 历史中已存在 get_fact_overview 或 get_fact_detail 的调用记录
- **THEN** 编排 LLM SHALL 识别已有数据，直接使用历史中的信息，不再重复调用相同的事实加载工具

#### Scenario: 跨轮引用用户澄清信息
- **WHEN** 上一轮通过 ask_user 工具收集了用户的澄清回答
- **THEN** 编排 LLM SHALL 在后续轮次中可见该回答，无需再次询问相同问题

### Requirement: ADK state 承载草稿和 skill 选择
系统 SHALL 使用 ADK session.state 存储跨轮写作状态，包括生成的草稿内容和已选 skill 信息。

#### Scenario: write_document 写入草稿到 session state
- **WHEN** write_document 工具生成完整草稿后
- **THEN** 工具 SHALL 将草稿内容写入 session.state["draft_content"]，将 skill_id 写入 session.state["selected_skill_id"]；工具返回值为摘要字符串（如"文档已生成，共 N 字"），不含完整草稿，避免历史膨胀

#### Scenario: get_current_draft 从 session state 优先读取
- **WHEN** get_current_draft 工具被调用
- **THEN** 工具 SHALL 优先从 session.state["draft_content"] 读取草稿，若不存在则回退到 ConversationManager 中的 writing_state.draft_content

### Requirement: 写作 LLM 每轮上下文保持干净
write_document 工具内部的写作 LLM 调用 SHALL 仅使用当轮相关信息构建上下文，不注入历史轮次的原始事实数据。

#### Scenario: 新建场景——collected_facts_parts 提供当轮事实
- **WHEN** write_document 在新建文档场景构建写作上下文时（session.state 中无已有草稿）
- **THEN** 注入的事实内容 SHALL 仅为本轮 get_fact_overview / get_fact_detail 调用所积累的 collected_facts_parts，不包含历史轮次的事实数据；context 参数为空字符串

#### Scenario: 修改场景——context 草稿为主要输入
- **WHEN** write_document 在修改文档场景构建写作上下文时（session.state 中已有草稿）
- **THEN** 写作 LLM 的主要输入 SHALL 为 context 参数（当前草稿全文）和 user_intent（用户修改意图）；collected_facts_parts 可能为空，不影响写作执行

### Requirement: 三层压缩策略保持编排 LLM context 干净
系统 SHALL 通过三层递进策略控制 ADK session 历史规模，以即时截断为核心，轮次触发为补充，强制裁剪为兜底。

#### Scenario: 第一层——事实加载工具即时截断
- **WHEN** get_fact_overview 或 get_fact_detail 工具执行完成时
- **THEN** 工具 SHALL 执行双路输出：
  1. 向 ADK session 历史返回摘要字符串（如"已加载模块清单：A、B、C 等5个模块"），不含原始全文
  2. 将原始全文 append 到 `collected_facts_parts`，供当轮写作 LLM 使用
  - 两路输出的内容不同：历史侧只留摘要，写作侧保留全文

#### Scenario: 第二层——轮次触发压缩（5-8 轮）
- **WHEN** 每轮 run_async() 前检测到累计轮次超过配置阈值（默认 5-8 轮）
- **THEN** 系统 SHALL 对早期轮次事件进行摘要压缩，保留用户消息、决策结论和澄清信息，丢弃中间推理步骤；若 ADK 不支持原生压缩则直接裁剪丢弃早期事件

#### Scenario: 第三层——强制裁剪兜底（15 轮）
- **WHEN** 累计轮次超过 15 轮
- **THEN** 系统 SHALL 无论压缩结果如何，只保留最近 8 轮完整事件，防止极端情况下历史无限增长
