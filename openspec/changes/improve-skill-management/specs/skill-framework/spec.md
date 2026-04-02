## MODIFIED Requirements

### Requirement: Skill 目录结构规范
每个 Skill MUST 遵循标准的目录结构，包含必需的描述文件和可选的支持文件。

#### Scenario: 标准目录结构
- **WHEN** Agent 加载 Skill 时
- **THEN** Skill 目录 SHALL 包含必需的 `skill.md`，并 MAY 包含 `scripts/`、`templates/`、`reference/`、`references/` 以及其他辅助文件

#### Scenario: 文件层级
- **WHEN** 查询 Skill 的组织方式时
- **THEN** 系统 SHALL 识别每个 Skill 目录中的必需文件（`skill.md`）和可选资源文件，并将 `scripts`、`templates`、`reference` / `references` 与其他资源分开归类

### Requirement: Skill 元数据和描述文件规范
每个 Skill MUST 包含 `skill.md` 文件，以 Markdown 格式包含结构化元信息和自然语言描述。`skill.md` 的正文描述 SHALL 自然地表达 Skill 需要哪类项目事实信息，供 Agent 推断上下文需求。

#### Scenario: skill.md 结构化元信息
- **WHEN** Skill 被加载时
- **THEN** `skill.md` SHALL 在顶部包含结构化元信息，并将 `name`、`description`、`type` 作为核心字段；可选字段仅限 `version`、`author`、`capabilities`、`constraints`、`input parameters`、`dependencies`、`output format`

#### Scenario: 元信息必需字段
- **WHEN** 解析 Skill 的元数据时
- **THEN** `skill.md` MUST 包含以下字段：
  - `name` 或 `Skill Name` - Skill 的唯一标识名称或显示名称
  - `description` 或 `Description` - 简要描述，说明其主要功能
  - `type` 或 `Type` - 文档类型或 Skill 类型

#### Scenario: 元信息可选字段
- **WHEN** Skill 定义扩展功能时
- **THEN** `skill.md` MAY 包含以下字段：
  - `version` 或 `Version`
  - `author` 或 `Author`
  - `capabilities` 或 `Capabilities`
  - `constraints` 或 `Constraints`
  - `input parameters` 或 `Input Parameters`
  - `dependencies` 或 `Dependencies`
  - `output format` 或 `Output Format`

#### Scenario: Legacy 标签字段被忽略
- **WHEN** `skill.md` 中存在 `tags` 或 `Tags`
- **THEN** 系统 SHALL NOT 将其视为正式元信息，也 SHALL NOT 在 Skill 管理 API 或 Web UI 中暴露该字段

## ADDED Requirements

### Requirement: Skill 资源清单可发现
系统 SHALL 在 Skill 被注册时发现并编目其目录中的辅助资源，供技能管理界面展示。

#### Scenario: 资源文件编目
- **WHEN** 系统发现一个有效 Skill
- **THEN** 系统 SHALL 对该 Skill 目录下除 `skill.md` 外的文件建立资源清单，并记录资源分类、展示名和相对 Skill 根目录的路径

#### Scenario: 资源分类规则
- **WHEN** 系统为 Skill 资源建立分类
- **THEN** `scripts/` 下的文件 SHALL 归类为 `script`，`templates/` 下的文件 SHALL 归类为 `template`，`reference/` 或 `references/` 下的文件 SHALL 归类为 `reference`，其他文件 SHALL 归类为 `other`

#### Scenario: 隐藏文件不进入资源清单
- **WHEN** Skill 目录下存在隐藏文件或隐藏目录中的文件
- **THEN** 系统 SHALL NOT 将这些文件纳入技能管理资源清单
