## ADDED Requirements

### Requirement: Agent 与 Skill 执行链路通过统一 MCP namespace 访问运行时资源
系统 SHALL 让主 Agent 与通过 `execute_skill` 创建的 Skill Sub-agent 通过统一的 MCP namespace 访问项目事实、Skill 本地资源和历史文档。

#### Scenario: 主 Agent 通过 MCP 访问项目事实与历史文档
- **WHEN** 主 Agent 在信息查询、目标定位或写作前判断阶段需要访问项目事实或历史文档
- **THEN** 系统 SHALL 通过 MCP 的 `facts.*` 与 `docs.*` namespace 提供相应能力，而不是要求主 Agent 直接依赖底层存储实现

#### Scenario: Skill Sub-agent 通过 MCP 访问运行时资源
- **WHEN** Skill Sub-agent 在执行中需要访问项目事实、Skill 本地资源或历史文档
- **THEN** 系统 SHALL 通过 MCP 的 `facts.*`、`skill.*`、`docs.*` namespace 为其提供统一访问能力

### Requirement: Agent 在第一阶段保持 Skill 调度与资源访问分层
系统 SHALL 在第一阶段保留 Orchestrator / 宿主运行时负责编排与 Skill 调度，而将 MCP 聚焦为资源访问层。

#### Scenario: Skill 调度仍由宿主运行时负责
- **WHEN** 主 Agent 判定需要调用某个 Skill
- **THEN** 系统 SHALL 继续由 Orchestrator / 宿主运行时触发 Skill 执行，不要求该调度动作必须通过 MCP 完成

#### Scenario: Skill 执行后续资源访问走 MCP
- **WHEN** Skill 被成功调度并进入执行阶段
- **THEN** Skill 在后续事实读取、资源读取、基线稿加载等动作中 SHALL 优先使用 MCP namespace，而不是依赖零散宿主工具集合

### Requirement: Agent SHALL 将通过 MCP 显式读取的资源纳入分层上下文传递链路
系统 SHALL 将 Agent 或 Skill 通过 MCP 显式读取的 facts、skill resources、docs 基线内容纳入分层上下文传递链路：主 Agent 仅保留必要 handoff 信息，Skill Sub-agent 在独立执行上下文中维护本轮写作 working context。

#### Scenario: 主 Agent 读取内容作为 handoff 信息
- **WHEN** 主 Agent 在当前轮次中通过 MCP 成功读取 facts 或 docs
- **THEN** 系统 SHALL 仅将后续委派所需的必要信息保留在主 Agent 编排上下文中，用于传递给 Skill Sub-agent，而不是将其当作与子 Agent 共享的完整写作上下文

#### Scenario: 子 Agent 维护独立写作上下文
- **WHEN** Skill Sub-agent 在执行过程中通过 MCP 成功读取 facts、skill resources 或 docs
- **THEN** 系统 SHALL 将这些内容按来源记录到子 Agent 的独立 working context 中，并保留来源标签

#### Scenario: 写作步骤消费子 Agent working context
- **WHEN** Skill 在同一轮中调用最终写作工具
- **THEN** 系统 SHALL 将当前子 Agent working context 中已显式读取的 facts、skill resources 和 docs 基线内容注入写作上下文，而不是直接复用主 Agent 的完整上下文
