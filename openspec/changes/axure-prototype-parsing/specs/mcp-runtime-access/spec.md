## MODIFIED Requirements

### Requirement: MCP 运行时访问采用 namespace 分域模型
系统 SHALL 通过统一的 MCP 运行时访问层暴露上下文来源能力，并按领域划分为 `facts.*`、`prototypes.*`、`skill.*`、`docs.*` 四个 namespace，而不是提供一个万能资源接口。

#### Scenario: MCP 暴露四类基础 namespace
- **WHEN** Agent Runtime 初始化 MCP 运行时访问能力时
- **THEN** 系统 SHALL 至少暴露 `facts.*`、`prototypes.*`、`skill.*`、`docs.*` 四个 namespace，并为每个 namespace 提供明确的用途边界

#### Scenario: namespace 语义不可混淆
- **WHEN** Agent 或 Skill 需要访问运行时资源时
- **THEN** 系统 SHALL 要求项目事实通过 `facts.*` 访问、原型页面与页面结构事实通过 `prototypes.*` 访问、Skill 本地资源通过 `skill.*` 访问、历史文档通过 `docs.*` 访问，不得将四类资源压平为一个无领域语义的通用资源接口

### Requirement: MCP 运行时第一阶段 SHALL 暴露明确的工具清单
系统 SHALL 在第一阶段为每个 namespace 提供可直接实施的核心工具集合，而不是只定义抽象 namespace 名称。

#### Scenario: `facts.*` 暴露核心事实工具
- **WHEN** MCP runtime 初始化 `facts.*` namespace
- **THEN** 系统 SHALL 至少暴露 `facts.list_modules`、`facts.get_module` 两个工具

#### Scenario: `prototypes.*` 暴露核心原型工具
- **WHEN** MCP runtime 初始化 `prototypes.*` namespace
- **THEN** 系统 SHALL 至少暴露 `prototypes.list_pages`、`prototypes.get_page` 两个工具

#### Scenario: `skill.*` 暴露核心 Skill 资源工具
- **WHEN** MCP runtime 初始化 `skill.*` namespace
- **THEN** 系统 SHALL 至少暴露 `skill.list_resources`、`skill.read_resource`、`skill.run_script` 三个工具

#### Scenario: `docs.*` 暴露核心历史文档工具
- **WHEN** MCP runtime 初始化 `docs.*` namespace
- **THEN** 系统 SHALL 至少暴露 `docs.list_saved`、`docs.load_saved` 两个工具

## ADDED Requirements

### Requirement: `prototypes.*` namespace 以只读原型事实访问为职责边界
系统 MUST 将 `prototypes.*` namespace 设计为只读原型访问能力，用于列出模块关联页面、读取单页结构化事实和返回解析证据，不承担原型资源写入或修改责任。

#### Scenario: `prototypes.*` 仅读取原型派生事实
- **WHEN** Agent 或 Skill 调用 `prototypes.*` namespace
- **THEN** 系统 SHALL 只允许读取模块关联页面、页面事实、交互摘要和来源信息，不得提供修改原型包或派生产物的能力

#### Scenario: 原型工具不依赖隐式宿主上下文
- **WHEN** 外部 MCP client 或当前系统内 Agent/Skill 调用 `prototypes.list_pages` 或 `prototypes.get_page`
- **THEN** 系统 SHALL 使用宿主无关的参数和返回结构，不得要求调用方持有仅进程内可见的宿主状态对象才能完成调用

#### Scenario: MCP 原型工具返回可直接注入 LLM 的内容
- **WHEN** Agent 或 Skill 通过 `prototypes.*` 工具读取原型信息
- **THEN** 系统 SHALL 在结构化返回之外提供适合注入模型上下文的可读摘要内容，避免调用方直接拼接原始 HTML 或派生 JSON
