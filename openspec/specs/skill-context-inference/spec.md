## ADDED Requirements

### Requirement: LLM 从 Skill 正文推断上下文需求
Agent SHALL 在选定 Skill 后执行一次轻量 LLM 调用，从 Skill 全文推断该 Skill 所需的上下文类型列表，Agent 将一次性加载列表中的所有类型，无需 Skill 作者显式声明。

#### Scenario: 推断结果为扁平的上下文类型列表
- **WHEN** Agent 对选定的 Skill 执行上下文需求推断时
- **THEN** LLM SHALL 返回结构化推断结果，格式为单行列表：
  ```
  CONTEXT: modules, usecases, prototypes
  ```
  列表包含 Skill 正文中提到的所有需要的上下文类型，无论是必需的还是"可以参考"的，一律纳入

#### Scenario: 推断失败时的兜底策略
- **WHEN** LLM 推断调用失败或返回无法解析的结果时
- **THEN** Agent SHALL 使用默认值：[modules, usecases]，并在日志中记录推断失败原因

#### Scenario: 推断结果写入日志
- **WHEN** 推断完成时
- **THEN** 系统 SHALL 在日志中记录：推断来源（LLM inference）、词汇列表、对应的 Skill ID
