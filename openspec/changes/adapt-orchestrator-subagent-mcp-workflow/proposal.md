## Why

在引入 MCP 作为统一资源访问层之后，当前系统里“主 Agent 负责什么、子 Agent 负责什么、两者如何通信、如何展示执行链路、如何隔离上下文”的协议层还没有同步演进。现在的 Orchestrator 仍然把工具调用逻辑、提示词约束和执行链路理解固化在内部实现中，这会让 MCP 只停留在“资源访问替换”，而不能真正支撑新的主子协作模式。

因此需要单独启动一项变更，重构主 Agent 与 Skill Sub-agent 之间的通信、执行链路和展示协议，让 Orchestrator 从“硬编码工具路由器”演进为适配 MCP 运行时的编排中枢，并保证主子 Agent 上下文隔离仍然成立。

## What Changes

- 定义主 Agent 与 Skill Sub-agent 之间的结构化通信协议，覆盖调用输入、执行结果、失败信息和执行摘要。
- 调整 Orchestrator 的内部实现逻辑，使其不再把资源工具调用路径和 Skill 行为假设硬编码在内部，而是面向新的 MCP 运行时与结构化执行协议决策。
- 重构 Orchestrator 的提示词和工具声明，让主 Agent 与子 Agent 持有不同职责边界、不同工具集合和不同提示词约束。
- 将主 Agent 与 Skill Sub-agent 的 system prompt 从 Python 内联字符串收敛为独立提示词文档模板，并保留少量运行时插槽注入能力。
- 在宿主运行时中引入 MCP client / tool catalog 管理层，由宿主统一发现、筛选和路由 MCP 工具，再分别投影给主 Agent 与子 Agent，而不是让主 Agent 直接接入 MCP server。
- 第一阶段优先实现 host 侧的 `catalog` 与 `tool view` 两层，并与已实现的 MCP server 直接顺接；`registry` 与统一 `tool gateway` 可作为后续演进。
- 保持主子 Agent 上下文隔离：主 Agent 只持有规划、状态和压缩执行结果；子 Agent 保持独立执行上下文，不把完整推理历史泄漏给主 Agent。
- 为执行链路增加可展示的结构化事件模型，用于前端或观测面板展示“规划 -> 调度 -> 取数 -> 写作 -> 完成/失败”的链路。
- 使新的主子 Agent 协作模式与 MCP runtime、公共工具集 / 内部工具集边界兼容。

## Capabilities

### New Capabilities
- `orchestrator-subagent-interop`: 定义主 Agent 与 Skill Sub-agent 的结构化通信协议、执行结果协议和上下文隔离边界。
- `execution-chain-visibility`: 定义主子协作执行链路的结构化事件模型和展示契约。

### Modified Capabilities
- `agent-core`: 调整 Orchestrator 的职责、工具声明、执行决策和主子协作逻辑，使其适配 MCP 模式。
- `conversation-management`: 扩展对主子执行链路、结构化执行结果和上下文快照的记录方式。
- `llm-integration`: 扩展 Orchestrator 与 Skill Sub-agent 的提示词分层和工具声明策略。
- `web-ui`: 扩展执行链路展示能力，使用户可以看到主 Agent 规划、Skill 调度和执行状态的结构化过程。

## Impact

- 影响代码：`backend/agent/adk/document_agent.py`、`backend/agent/adk/execute_skill_tool.py`、`backend/agent/adk/runner_adapter.py`、`backend/agent/adk/llm_adapter.py`、`backend/agent/models.py`，以及与执行状态推送和前端展示相关的模块。
- 影响运行时协议：`execute_skill` 不再只是返回自由文本摘要，而需要返回更稳定的结构化执行结果。
- 影响工具接入方式：MCP 工具不再由主 Agent 直接绑定 server 细节，而是先由宿主统一管理，再按角色生成主 Agent / 子 Agent 的工具视图。
- 影响提示词设计：Orchestrator 和 Skill Sub-agent 的 system prompt、工具清单和执行约束都需要重新分层设计，并迁移到独立提示词文档中管理。
- 影响前端展示：执行链路将从零散 status/text 事件，演进为更清晰的结构化展示流。
