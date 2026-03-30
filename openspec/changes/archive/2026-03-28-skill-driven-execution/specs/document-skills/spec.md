## MODIFIED Requirements

### Requirement: skill.md 自然语言描述即为执行规范（上下文需求 + 专属工具说明）

每个文档编写 Skill 的 skill.md SHALL 在正文中，以自然语言完整描述：
1. 写作该类型文档需要哪些项目事实信息
2. 该 Skill 提供了哪些专属工具及其用途（若有）

Skill Sub-agent 以 skill.md 为 instruction，自主推理决定加载哪些事实、调用哪些工具，无需任何机器可读字段。

#### Scenario: skill.md 正文充分描述上下文需求和专属工具

- **WHEN** Skill 作者编写 skill.md 时
- **THEN** skill.md 的正文 SHALL 明确说明：写作该类型文档需要哪些项目事实信息；如果 Skill 提供了专属工具，须描述工具名称、用途和调用时机，使 Sub-agent 能够理解何时使用这些工具

#### Scenario: 三个内置 Skill 的上下文描述覆盖情况

- **WHEN** 实现阶段验证内置 Skill 时
- **THEN** 三个内置 Skill 的 skill.md 正文 SHALL 经过检查，确认已包含充分的上下文需求描述；若描述不足，须补充完善：
  - `write-requirements`：应描述写作需求规格时主要依赖用例描述（usecases）
  - `write-design`：应描述写作设计文档时主要依赖类包设计（classes）和接口定义（interfaces）
  - `write-test-plan`：应描述写作测试方案时主要依赖用例描述（usecases）和接口定义（interfaces）

#### Scenario: skill.md 上下文描述不足时终止写作

- **WHEN** Sub-agent 读取 skill.md 后无法推断需要哪些事实上下文时
- **THEN** Sub-agent SHALL 调用 `ask_user` 向用户确认：是否继续（不依据事实信息生成）或提供补充说明；若用户明确要求不依据事实信息生成，Sub-agent SHALL 跳过事实加载直接写作；否则终止写作并提示 Skill 作者完善 skill.md 的上下文需求描述

#### Scenario: SkillInfo 模型不新增结构化字段

- **WHEN** 系统从 skill.md frontmatter 加载 Skill 元数据时
- **THEN** `SkillInfo` 模型 SHALL 不新增机器可读的上下文需求或工具声明字段；所有执行规范均通过 skill.md 自然语言描述传递给 Sub-agent

### Requirement: Skill 专属工具路径在 skill.md 正文中声明

Skill 可在其目录下任意位置提供专属工具文件。工具文件的路径 SHALL 在 skill.md 正文中以自然语言明确描述，系统在创建 Sub-agent 时从 skill.md 中提取路径并按需加载，无目录结构约定。

#### Scenario: skill.md 正文描述专属工具路径和用途

- **WHEN** Skill 作者为 Skill 提供专属工具时
- **THEN** skill.md 正文 SHALL 明确说明：工具文件的相对路径（相对于 skill 目录）、工具用途、以及调用时机；Sub-agent 根据这些描述决定何时调用

示例（skill.md 正文片段）：
```
本 Skill 提供了以下专属工具：
- parsers/excel_parser.py：用于解析用户提供的 Excel 格式的需求表格，在用户上传 Excel 时调用
- generators/diagram_gen.py：用于生成架构图，在需要输出可视化设计时调用
```

#### Scenario: 系统从 skill.md 中提取工具路径并加载

- **WHEN** `execute_skill` 创建 Skill Sub-agent 时
- **THEN** 系统 SHALL 读取 skill.md 正文，通过 LLM 推断提取所有工具文件路径，加载对应 `.py` 模块并注册到 Sub-agent 工具列表；skill.md 中未声明任何工具时，Sub-agent 仅使用通用工具集

#### Scenario: 工具模块约定

- **WHEN** Skill 作者编写工具模块时
- **THEN** 每个工具模块 SHALL 暴露一个与文件同名的可调用函数作为工具入口，函数签名遵循 ADK 工具约定（参数有类型注解，有 docstring 供 LLM 理解用途）

#### Scenario: Sub-agent 根据 skill.md 描述自主决定是否调用专属工具

- **WHEN** Sub-agent 在 ReAct 循环中执行时
- **THEN** Sub-agent SHALL 根据 skill.md 中对专属工具的自然语言描述，自主判断在当前写作任务中是否需要调用这些工具；专属工具的调用时机和方式由 Sub-agent 推理决定，无需硬编码
