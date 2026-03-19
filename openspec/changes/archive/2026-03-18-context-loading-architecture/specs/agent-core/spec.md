## MODIFIED Requirements

### Requirement: Agent 访问项目事实信息
Agent SHALL 通过结构化的多步骤流程访问项目事实信息，替代原有的关键词扫描方式，实现精确的按模块、按类型加载。

#### Scenario: 上下文需求推断步骤
- **WHEN** Agent 选定 Skill 后，准备加载上下文时
- **THEN** Agent SHALL 执行上下文需求推断（LLM 推断或读取显式声明），得到 required 和 optional 词汇列表，并在日志中记录推断结果

#### Scenario: 模块定位步骤
- **WHEN** Agent 执行上下文推断后
- **THEN** Agent SHALL 从用户消息中提取目标模块名，通过精确匹配、LLM 语义匹配两级策略定位模块 ID，并在 status step 中展示定位结果

#### Scenario: 一次性加载所有推断上下文
- **WHEN** 模块 ID 定位完成后
- **THEN** Agent SHALL 按词汇列表逐项加载，每项按模块 ID 过滤，只加载目标模块相关的条目，并在 status step 中展示加载摘要

#### Scenario: modules.md 始终作为基础上下文
- **WHEN** Agent 执行任何文档生成任务时
- **THEN** modules.md SHALL 始终被加载，无论 required 列表内容如何，因为它提供项目全貌和检索入口

## ADDED Requirements

### Requirement: Agent 上下文加载过程可观测
Agent 的上下文加载决策和执行过程 SHALL 对用户和开发者可见。

#### Scenario: status steps 展示加载行为
- **WHEN** Agent 执行上下文加载时
- **THEN** 以下步骤 SHALL 在 status steps 中展示：
  - "已定位模块: {模块名}（{module-id}）"（定位成功时）
  - "未识别到目标模块"（定位失败时，随后中断并输出引导文字）
  - "加载项目上下文：modules（N个）: {模块名1}、{模块名2}... · {词汇}: {条目名1}、{条目名2} 等N条"

#### Scenario: 上下文加载 status step 展示条目名称
- **WHEN** Agent 完成上下文加载时
- **THEN** "加载项目上下文" status step SHALL 展示各词汇实际加载的条目名称：
  - modules 词汇：展示所有模块名（最多5个，超出显示省略号）
  - usecases / classes / interfaces 词汇：展示前3条条目名称，超出3条显示「等N条」
  - 各词汇之间以「·」分隔

#### Scenario: 日志记录推断和加载详情
- **WHEN** 上下文推断和加载完成时
- **THEN** 系统 SHALL 在日志中记录：推断来源、词汇列表、模块 ID、各词汇实际加载的条目数和文件路径
