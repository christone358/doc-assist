## ADDED Requirements

### Requirement: 项目事实信息可通过 `facts.*` MCP namespace 暴露给 Agent Runtime
系统 SHALL 在现有项目事实查询能力之外，通过 `facts.*` namespace 向主 Agent 和 Skill Sub-agent 暴露标准化的运行时事实访问接口。

#### Scenario: 主 Agent 通过 `facts.*` 查询事实
- **WHEN** 主 Agent 需要查看当前有哪些模块，或读取某个模块聚合根下的事实信息
- **THEN** 系统 SHALL 提供 `facts.*` namespace 能力，使其无需直接依赖底层文件结构

#### Scenario: Skill Sub-agent 通过 `facts.*` 查询事实
- **WHEN** Skill Sub-agent 在写作过程中需要查看模块清单或读取某个模块聚合根下的事实信息
- **THEN** 系统 SHALL 提供相同语义的 `facts.*` namespace 能力，供其与主 Agent 复用同一事实访问模式

### Requirement: `facts.*` 工具集合应覆盖当前模块清单和模块聚合根查询主路径
系统 SHALL 让 `facts.*` 工具集合优先覆盖“查询有哪些模块”和“读取某个模块聚合根全文”这两个当前主路径场景。

#### Scenario: 模块清单工具标准化
- **WHEN** Agent Runtime 需要了解当前项目包含哪些模块
- **THEN** 系统 SHALL 提供 `facts.list_modules()` 工具，返回模块清单及必要的基础摘要

#### Scenario: 模块聚合根工具标准化
- **WHEN** Agent Runtime 需要读取某个模块聚合根下的完整事实信息
- **THEN** 系统 SHALL 提供 `facts.get_module(module_ref)` 工具，并允许 server 在内部完成模块引用解析与底层视图选择，而不是要求调用方拼装底层读取逻辑

### Requirement: `facts.*` 第一阶段不提前暴露细粒度详情工具
系统 MUST 让 `facts.*` 第一阶段契约与当前项目事实治理现实保持一致，不得提前把尚无稳定事实形态支撑的细粒度 public 工具固化进协议。

#### Scenario: 细粒度详情能力暂不对外承诺
- **WHEN** 当前项目事实信息仍以模块聚合根为主维护单元，且缺少稳定的聚合根以下细粒度能力模型
- **THEN** 系统 SHALL 不在第一阶段 public `facts.*` 契约中强制暴露额外的细粒度详情工具

### Requirement: `facts.*` namespace 保持只读与标准化查询语义
系统 MUST 将 `facts.*` namespace 设计为只读事实访问接口，并保持查询语义与项目事实域对象一致。

#### Scenario: `facts.*` 仅读取不写入
- **WHEN** Agent Runtime 通过 `facts.*` namespace 操作项目事实信息
- **THEN** 系统 SHALL 仅允许查询和读取，不得提供写入、修改或删除能力

#### Scenario: `facts.*` 返回领域化结果
- **WHEN** Agent Runtime 调用 `facts.*` namespace
- **THEN** 系统 SHALL 返回与模块、概览、详情等事实域对象一致的结果，而不是要求调用方直接处理底层文件路径
