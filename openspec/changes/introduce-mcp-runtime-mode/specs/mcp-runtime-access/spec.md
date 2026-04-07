## ADDED Requirements

### Requirement: MCP 运行时访问采用 namespace 分域模型
系统 SHALL 通过统一的 MCP 运行时访问层暴露上下文来源能力，并按领域划分为 `facts.*`、`skill.*`、`docs.*` 三个 namespace，而不是提供一个万能资源接口。

#### Scenario: MCP 暴露三类基础 namespace
- **WHEN** Agent Runtime 初始化 MCP 运行时访问能力时
- **THEN** 系统 SHALL 至少暴露 `facts.*`、`skill.*`、`docs.*` 三个 namespace，并为每个 namespace 提供明确的用途边界

#### Scenario: namespace 语义不可混淆
- **WHEN** Agent 或 Skill 需要访问运行时资源时
- **THEN** 系统 SHALL 要求项目事实通过 `facts.*` 访问、Skill 本地资源通过 `skill.*` 访问、历史文档通过 `docs.*` 访问，不得将三类资源压平为一个无领域语义的通用资源接口

### Requirement: MCP Server SHALL 按可独立对外暴露的 remote server 设计
系统 SHALL 将本次 MCP server 设计为可独立对外暴露的标准 remote MCP server，而不是仅供当前系统内部 agent 调用的私有适配层。

#### Scenario: 对外部标准 MCP client 可见
- **WHEN** 外部 agent 或标准 MCP client 连接本次 MCP server
- **THEN** 系统 SHALL 通过标准 MCP 协议和标准传输暴露公共工具集，而不要求调用方依赖当前系统内部 agent 框架

#### Scenario: 工具契约不绑定宿主内部对象
- **WHEN** MCP server 定义对外工具 schema
- **THEN** 系统 SHALL 使用宿主无关的参数和返回语义，不得把当前系统内部状态对象名称直接暴露为公共工具契约

#### Scenario: 公共工具不依赖隐式宿主上下文
- **WHEN** MCP server 对外暴露公共工具集
- **THEN** 系统 SHALL 不得要求调用方隐式依赖当前应用内部会话对象、宿主框架状态或仅进程内可见的上下文才能正确调用

#### Scenario: Server 可独立运行但允许打包部署
- **WHEN** 本项目部署 MCP server
- **THEN** 系统 SHALL 允许其与主系统打包运行，但 server 本身 MUST 保持独立启动入口、标准传输实现和理论上的独立部署能力

### Requirement: MCP 运行时第一阶段 SHALL 暴露明确的工具清单
系统 SHALL 在第一阶段为每个 namespace 提供可直接实施的核心工具集合，而不是只定义抽象 namespace 名称。

#### Scenario: `facts.*` 暴露核心事实工具
- **WHEN** MCP runtime 初始化 `facts.*` namespace
- **THEN** 系统 SHALL 至少暴露 `facts.list_modules`、`facts.get_module` 两个工具

#### Scenario: `skill.*` 暴露核心 Skill 资源工具
- **WHEN** MCP runtime 初始化 `skill.*` namespace
- **THEN** 系统 SHALL 至少暴露 `skill.list_resources`、`skill.read_resource`、`skill.run_script` 三个工具

#### Scenario: `docs.*` 暴露核心历史文档工具
- **WHEN** MCP runtime 初始化 `docs.*` namespace
- **THEN** 系统 SHALL 至少暴露 `docs.list_saved`、`docs.load_saved` 两个工具

### Requirement: MCP Server SHALL 区分公共工具集与内部工具集
系统 SHALL 将工具能力划分为可对外暴露的公共工具集和仅供内部受控使用的内部工具集。

#### Scenario: 公共工具集优先暴露只读稳定能力
- **WHEN** MCP server 对外暴露公共工具集
- **THEN** 系统 SHALL 优先暴露低风险、只读、领域语义稳定的工具，至少包括 `facts.*` 与 `docs.*` 核心工具

#### Scenario: 内部工具集保留高风险或强上下文绑定能力
- **WHEN** MCP server 定义内部工具集
- **THEN** 系统 SHALL 将高风险或强依赖当前执行上下文的工具保留为内部工具，至少包括 `skill.run_script`，并 MAY 包括其他 `skill.*` 能力

### Requirement: MCP 运行时访问接口必须保持统一治理
系统 SHALL 对 MCP runtime 的各 namespace 提供统一的调用风格、错误格式、日志记录与权限治理能力。

#### Scenario: MCP 返回统一错误结构
- **WHEN** 任一 namespace 调用失败
- **THEN** 系统 SHALL 返回可诊断的标准错误结果，至少包含失败类型、目标标识和简要原因

#### Scenario: MCP 调用过程可审计
- **WHEN** Agent 或 Skill 调用任一 namespace
- **THEN** 系统 SHALL 记录 namespace、方法名、目标标识、结果状态和必要的错误摘要，供调试和审计使用

### Requirement: `skill.*` namespace 仅绑定当前 Skill 作用域
系统 MUST 将 `skill.*` namespace 的访问范围限制在当前执行中的 Skill 根目录内，不得允许跨 Skill 或跨宿主目录访问。

#### Scenario: 当前 Skill 读取本地资源
- **WHEN** 执行中的 Skill 调用 `skill.read_resource(relative_path)`
- **THEN** 系统 SHALL 仅允许读取当前 Skill 根目录下的相对路径资源

#### Scenario: 拒绝跨 Skill 或越权访问
- **WHEN** `skill.*` namespace 解析出的目标路径超出当前 Skill 根目录
- **THEN** 系统 SHALL 拒绝执行，并返回明确的越权错误

### Requirement: `facts.*` 与 `docs.*` namespace 在第一阶段为只读能力
系统 MUST 在第一阶段将 `facts.*` 和 `docs.*` 设计为只读访问能力，用于按需加载上下文，而不承担写入或修改责任。

#### Scenario: `facts.*` 仅读取项目事实
- **WHEN** Agent 或 Skill 调用 `facts.*` namespace
- **THEN** 系统 SHALL 只允许查询和读取项目事实，不得提供修改或删除能力

#### Scenario: `docs.*` 仅读取历史文档
- **WHEN** Agent 或 Skill 调用 `docs.*` namespace
- **THEN** 系统 SHALL 只允许列出、加载或比较已保存文档版本，不得在该 namespace 中提供正式写入能力
