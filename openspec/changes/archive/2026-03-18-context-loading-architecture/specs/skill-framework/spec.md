## MODIFIED Requirements

### Requirement: Skill 元数据和描述文件规范
每个 Skill MUST 包含 skill.md 文件，以 Markdown 格式包含结构化元信息和自然语言描述。skill.md 的正文描述 SHALL 自然地表达 Skill 需要哪类项目事实信息，供 Agent 推断上下文需求。

#### Scenario: skill.md 结构化元信息
- **WHEN** Skill 被加载时
- **THEN** skill.md 应在顶部包含以下结构化元信息（使用标准 Markdown 格式）：
  ```markdown
  # Skill Name: requirements-spec-skill
  - **Description**: 用于编写和修改软件需求规格文档的Skill
  - **Type**: requirements
  - **Version**: 1.0.0
  - **Author**: Doc Assistant Team
  - **Tags**: requirements, specification
  - **Capabilities**: 新增编写需求规格, 精准修改需求内容
  - **Constraints**: 需要项目上下文信息, 支持中文文档
  ```

#### Scenario: 元信息必需字段
- **WHEN** 解析 Skill 的元数据时
- **THEN** skill.md 必须包含以下字段：
  - `Skill Name` - Skill的唯一标识名称（kebab-case格式，如 requirements-spec-skill）
  - `Description` - 简要描述，说明其主要功能
  - `Type` - 文档类型（如 requirements、design、test 或其他可扩展类型）

#### Scenario: 元信息可选字段
- **WHEN** Skill 定义扩展功能时
- **THEN** skill.md 可包含以下字段：
  - `Version` - 语义版本号（如 1.0.0）
  - `Author` - Skill 的作者或维护团队
  - `Tags` - Skill 的标签，便于分类和搜索
  - `Capabilities` - Skill 的能力列表，描述其可以执行的操作
  - `Constraints` - Skill 的约束条件，说明使用限制
  - `Input Parameters` - Skill 需要的输入参数定义
  - `Dependencies` - Skill 依赖的其他 skill 或工具

#### Scenario: 描述文件详细内容
- **WHEN** 需要理解 Skill 的详细信息时
- **THEN** skill.md 在元信息之后应包含以下内容部分：
  - **概述** - Skill 的整体介绍和主要功能
  - **能力范围** - Skill 能够执行的具体功能列表
  - **输入要求** - Skill 需要的输入数据格式和必需信息
  - **输出规范** - Skill 生成的输出格式和内容结构
  - **使用示例** - 典型的使用场景和示例
  - **限制和注意事项** - Skill 的使用限制和重要事项

#### Scenario: 格式和可读性
- **WHEN** Agent 加载 Skill 时
- **THEN** skill.md 应使用清晰的 Markdown 格式，便于 LLM 理解和 Agent 解析

## ADDED Requirements

### Requirement: Skill 正文供 LLM 推断上下文需求
Agent SHALL 通过读取 Skill 的 skill.md 全文，结合系统词汇表，由 LLM 自动推断该 Skill 所需的上下文类型。Skill 作者无需遵循特定格式，只需自然地描述 Skill 的工作原理和能力范围，LLM 负责从中提取上下文需求。

#### Scenario: LLM 从 Skill 正文推断上下文需求
- **WHEN** Agent 选定 Skill 后执行上下文推断时
- **THEN** Agent SHALL 将 Skill 全文和系统词汇表一起输入 LLM，由 LLM 返回需要加载的词汇列表，Skill 作者不需要为此做任何额外工作

#### Scenario: 自然描述的 Skill 正文足以支撑推断
- **WHEN** Skill 正文包含对工作原理的自然语言描述时（例如"需要了解模块的用例"、"可参考原型界面"）
- **THEN** LLM SHALL 能够从这些描述中推断出对应的词汇类型，无需 Skill 作者使用特定关键词或格式
