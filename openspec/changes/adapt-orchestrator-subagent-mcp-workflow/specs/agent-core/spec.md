## ADDED Requirements

### Requirement: Orchestrator SHALL 适配 MCP 模式下的提示词与工具声明分层
系统 SHALL 重构 Orchestrator 的提示词和工具声明，使主 Agent 与 Skill Sub-agent 持有不同职责边界、不同工具集合和不同执行约束。

#### Scenario: 主 Agent 使用编排型提示词
- **WHEN** 系统构建主 Agent
- **THEN** 主 Agent 的提示词 SHALL 强调意图识别、任务拆解、Skill 选择、状态管理和何时调用公共工具集，而不是下沉到子 Agent 的具体执行细节

#### Scenario: 子 Agent 使用执行型提示词
- **WHEN** 系统构建 Skill Sub-agent
- **THEN** 子 Agent 的提示词 SHALL 强调具体任务执行、资源访问和结果返回，而不是重复承担主 Agent 的编排职责

### Requirement: MCP 工具 SHALL 先由宿主运行时统一管理，再按 Agent 角色投影
系统 SHALL 由宿主运行时统一管理 MCP client 连接、工具发现与工具目录，并按主 Agent / 子 Agent 的职责边界生成不同的工具视图。

#### Scenario: 第一阶段先落地 catalog 与 tool view
- **WHEN** 系统进入本次 change 的第一阶段实现
- **THEN** 系统 SHALL 至少实现宿主级 `catalog` 与按角色生成的 `tool view`，并允许继续复用已实现的 MCP server；不要求本阶段同时完成独立 `registry` 或完整统一 `tool gateway`

#### Scenario: 主 Agent 消费宿主投影出的公共工具视图
- **WHEN** 系统构建主 Agent 的工具集合
- **THEN** 主 Agent SHALL 消费宿主投影出的公共工具视图，而不是直接绑定 MCP server 的连接细节或完整工具全集

#### Scenario: 子 Agent 消费宿主投影出的执行工具视图
- **WHEN** 系统构建 Skill Sub-agent 的工具集合
- **THEN** 子 Agent SHALL 消费宿主投影出的执行工具视图，其中可包含内部工具与必要公共工具，但仍由宿主统一治理和路由

### Requirement: Host SHALL 以发现结果驱动 MCP catalog 初始化，而不是依赖手写工具清单
系统 SHALL 让宿主侧 `catalog` 基于 MCP runtime / MCP client 返回的工具发现结果初始化，并仅通过角色策略、可见性策略和少量宿主补充元数据生成不同 Agent 的 `tool view`，而不是继续维护按 Agent 分散编写的工具枚举列表。

#### Scenario: 宿主基于发现结果构建 catalog
- **WHEN** 宿主初始化当前可用 MCP 工具目录
- **THEN** 系统 SHALL 通过 `list_tools` 或等价发现接口读取工具标识、schema 与可见性信息，并据此生成宿主级 `catalog`，而不是要求开发者在 host 代码中重复手写同一批工具名

#### Scenario: 新增公共 MCP 工具后可自动进入主 Agent 工具视图
- **WHEN** 某个新的 public MCP 工具已在 runtime / server 侧注册，且其角色策略允许暴露给主 Agent
- **THEN** 宿主 SHALL 能在不新增按-tool wrapper 列表或不修改主 Agent 固定工具枚举的前提下，将该工具纳入主 Agent 的 `tool view`

#### Scenario: 角色策略仍可过滤动态发现到的工具
- **WHEN** 宿主发现到的工具包含 internal-only 能力或不属于当前 Agent 职责边界的能力
- **THEN** 系统 SHALL 继续通过角色策略与可见性策略过滤这些工具，确保“动态发现”不会破坏主 Agent / 子 Agent 的工具隔离

### Requirement: Orchestrator SHALL 基于结构化执行结果决策下一步动作
系统 SHALL 让 Orchestrator 基于结构化 Skill 执行结果，而不是仅凭自由文本摘要，决定继续、澄清、重试或完成。

#### Scenario: 结构化成功结果驱动后续决策
- **WHEN** Skill 返回结构化成功结果
- **THEN** Orchestrator SHALL 基于其中的执行状态、压缩摘要和必要恢复信号更新当前状态并决定后续动作，而不是依赖子 Agent 的领域状态全文或执行细节清单

#### Scenario: 结构化失败结果驱动恢复逻辑
- **WHEN** Skill 返回结构化失败结果
- **THEN** Orchestrator SHALL 基于失败类型和可重试信息选择追问用户、重新调度或结束本轮
