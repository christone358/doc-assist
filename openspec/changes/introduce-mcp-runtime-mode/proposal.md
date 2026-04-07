## Why

当前项目中，主 Agent、Skill Sub-agent、项目事实库、Skill 本地资源和历史文档之间的访问链路是分散实现的：项目事实依赖宿主内置工具，Skill 资源访问能力不完整，历史文档访问与事实访问也采用不同模型。这导致运行时能力面不一致，Skill 中声明的参考资料和脚本难以稳定生效，也让事实加载逻辑继续固化在主 Agent 宿主代码中。

现在需要引入一个统一的 MCP 运行时模式，把“资源访问”从宿主硬编码中抽离出来，形成主 Agent 和 Skill Sub-agent 都可复用的标准访问协议，同时保留 Orchestrator 负责编排和 Skill 调度的职责边界。本次设计还需要明确：该 MCP server 不是仅供当前系统内部 agent 使用的私有适配层，而是按可独立对外暴露的标准 remote MCP server 设计。

## What Changes

- 引入 MCP 运行时访问层，统一暴露项目事实、Skill 本地资源、历史文档三类上下文来源的标准能力接口。
- 将运行时能力按 namespace / capability 划分为 `facts.*`、`skill.*`、`docs.*`，避免将不同领域资源压平成一个万能抽象。
- 明确第一阶段各 namespace 的工具清单，作为开发任务直接落到运行时改造计划中；其中 `facts.*` 按当前项目事实管理现状收敛为最小可用工具集。
- 明确本次 MCP server 按可独立对外暴露的标准 remote MCP server 设计与实现，支持被其他 agent / client 按标准协议调用，而不仅被当前系统内部 agent 使用。
- 将工具能力拆分为“公共工具集”和“内部工具集”，优先对外暴露低风险只读能力，并保留高风险能力的内部受控边界。
- 调整主 Agent 与 Skill Sub-agent 的资源访问方式，使两者都通过同一 MCP 协议访问事实、Skill 资源和历史文档。
- 保持现有 Skill 调度链路由 Orchestrator / 宿主运行时负责，不在本次变更中强制把 `execute_skill` 改造成 MCP 调用。
- 定义 MCP 运行时适配层与缓存/审计边界，包括上下文注入、路径安全、命名空间权限、显式上下文约束和工具调用记录要求。
- 为现有 facts 工具、Skill 资源工具和历史文档工具规划平滑迁移路径，优先通过 adapter 方式接入 MCP，而不是一次性推翻现有运行时。

## Capabilities

### New Capabilities
- `mcp-runtime-access`: 定义统一的 MCP 运行时访问模式，包括 namespace 划分、能力边界、适配层和调用约束。

### Modified Capabilities
- `agent-core`: 调整 Agent/Skill 运行时资源访问方式，使主 Agent 和 Skill Sub-agent 通过统一协议访问 facts、skill resources 和 docs，同时保持 Orchestrator 负责编排与 Skill 调度。
- `skill-framework`: 扩展 Skill 运行契约，明确 Skill 本地资源在运行时通过 `skill.*` namespace 被访问，而不是依赖隐式宿主加载。
- `project-fact-information`: 扩展项目事实信息的查询访问模型，使事实信息除现有内部工具/查询接口外，还可通过 `facts.*` MCP namespace 暴露给 Agent 运行时使用。
- `document-version-management`: 扩展历史文档读取模型，使已保存文档可通过 `docs.*` MCP namespace 作为 Skill 修改场景下的标准基线来源。

## Impact

- 影响代码：`backend/agent/adk/document_agent.py`、`backend/agent/adk/execute_skill_tool.py`、`backend/agent/adk/fact_tools.py`、`backend/agent/adk/saved_doc_tools.py`、`backend/agent/adk/write_document_tool.py`、`backend/agent/adk/runner_adapter.py`，以及新增的 MCP runtime adapter / server 相关模块。
- 影响运行时契约：主 Agent 和 Skill Sub-agent 的资源访问能力将从宿主内置工具集合，演进为通过统一 namespace 暴露的 MCP 能力面。
- 影响服务形态：MCP runtime 将按 remote MCP server 设计和实现，需要具备标准对外暴露能力与独立运行能力；在当前项目中可先与主系统打包部署，但不应退化为仅能在应用内运行的 adapter。
- 影响 facts 契约：`facts.*` 第一阶段优先围绕“列出模块清单”和“读取模块聚合根全文”两类真实场景设计，而不提前暴露当前尚无稳定数据支撑的细粒度详情工具。
- 影响 Skill 契约：Skill 目录内 `references/`、`templates/`、`scripts/` 等资源不再只是可扫描元数据，而是可在执行期通过 `skill.*` namespace 被显式访问。
- 影响后续演进：为未来的 capability registry、动态发现、更强的资源治理和跨运行时适配打下统一协议基础。
