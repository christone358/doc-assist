## MODIFIED Requirements

### Requirement: 编排层职责收窄为意图判断和 Skill 选择

主 Agent（document_agent）的工具列表 SHALL 仅包含：`execute_skill`、`ask_user`。所有写作相关工具（事实加载、草稿管理、写作 LLM）均迁入 Skill Sub-agent。

#### Scenario: 主 Agent 与 Sub-agent 的 ask_user 职责划分

- **WHEN** 需要向用户提问时
- **THEN** 职责划分 SHALL 为：
  - **主 Agent**：在调用 execute_skill **之前**，对意图层面的模糊（写作对象不明确、Skill 无法判断）调用 ask_user 澄清
  - **Sub-agent**：在执行过程中，对执行层面的问题（事实库中对象有歧义、草稿版本选择、写作细节超出事实库范围）调用 ask_user 澄清
  - 两层的 ask_user 调用使用相同 WebSocket 通道，对用户呈现方式一致

#### Scenario: 文档写作场景编排流程

- **WHEN** 用户发起文档写作请求时
- **THEN** 主 Agent SHALL 执行：
  1. 理解用户消息，提炼结构化写作意图（含写作对象名称、文档类型、写作重点）
  2. 若写作对象或 Skill 不明确，调用 `ask_user` 澄清
  3. 选择匹配的 Skill（skill_id）
  4. 调用 `execute_skill(skill_id, user_intent)`
  5. 不得在调用 execute_skill 之前自行调用任何写作或事实工具

#### Scenario: 主 Agent instruction 不包含写作执行工作流

- **WHEN** 主 Agent 接收到文档写作请求时
- **THEN** 主 Agent SHALL 不自行调用任何事实加载、草稿管理或写作工具；instruction 中不描述事实加载、草稿来源决策等工作流

#### Scenario: user_intent 须包含写作对象名称

- **WHEN** 主 Agent 构造 user_intent 参数时
- **THEN** user_intent SHALL 明确包含写作对象的名称（如模块名、子系统名），以便 Sub-agent 内部定位相关事实；若用户消息中对象不明确，主 Agent SHALL 先调用 `ask_user` 澄清

### Requirement: 两层 Agent 架构

系统 SHALL 采用"主 Agent 路由意图 + Skill Sub-agent 提供专项能力"的两层架构。每个 Skill 对应一个可按需实例化的 Sub-agent，不同 Skill 的 Sub-agent 拥有独立的 instruction（来自各自的 skill.md），但共享相同的工具集和 ConversationContext。

#### Scenario: 架构扩展性

- **WHEN** 新增 Skill 时
- **THEN** 系统 SHALL 自动支持以该 Skill 的 skill.md 为 instruction 的 Sub-agent，无需修改主 Agent 代码；新 Skill 的上下文需求和工具调用方式由其 skill.md 的自然语言描述驱动，Sub-agent 自主推理执行
