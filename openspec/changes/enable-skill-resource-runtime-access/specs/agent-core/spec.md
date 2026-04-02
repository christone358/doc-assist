## ADDED Requirements

### Requirement: Agent 在 Skill 执行期间提供 Skill 本地资源工具
系统 SHALL 在 `execute_skill` 创建的 Skill Sub-agent 中提供当前 Skill 作用域下的本地资源访问工具。

#### Scenario: Skill Sub-agent 获得本地资源读取工具
- **WHEN** `execute_skill(skill_id, user_intent)` 创建 Skill Sub-agent 时
- **THEN** Sub-agent 的工具列表 SHALL 包含 `read_skill_resource(relative_path)`，用于读取当前 Skill 根目录内的本地文本资源

#### Scenario: Skill Sub-agent 获得脚本执行工具
- **WHEN** `execute_skill(skill_id, user_intent)` 创建 Skill Sub-agent 时
- **THEN** Sub-agent 的工具列表 SHALL 包含 `run_skill_script(relative_path, payload)`，用于执行当前 Skill 根目录内的 Python 脚本

### Requirement: Agent 将已加载的 Skill 本地资源传递给后续生成步骤
系统 SHALL 将 Skill 执行过程中已读取的本地资源和脚本输出保存在共享上下文中，并传递给后续生成类工具。

#### Scenario: 资源读取结果写入共享上下文
- **WHEN** Skill Sub-agent 成功读取本地资源或执行本地脚本
- **THEN** 系统 SHALL 将结果写入与主 Agent 共享的 `ConversationContext`，并保留资源来源信息

#### Scenario: write_document 消费已加载的 Skill 本地资源
- **WHEN** Skill Sub-agent 在同一轮中调用 `write_document(...)`
- **THEN** `write_document` SHALL 将本轮已加载的 Skill 本地资源与项目事实、已有草稿一起注入最终写作上下文

### Requirement: Agent 对 Skill 本地资源访问过程可观测
系统 SHALL 对 Skill 本地资源的读取和脚本执行过程提供可观测性，便于用户和开发者理解当前 Skill 正在使用哪些资源。

#### Scenario: 资源读取行为写入状态流
- **WHEN** Skill Sub-agent 调用 `read_skill_resource(relative_path)` 成功或失败
- **THEN** 系统 SHALL 在状态流或日志中记录资源路径、结果状态和必要的错误摘要

#### Scenario: 脚本执行行为写入状态流
- **WHEN** Skill Sub-agent 调用 `run_skill_script(relative_path, payload)` 成功或失败
- **THEN** 系统 SHALL 在状态流或日志中记录脚本路径、结果状态和必要的错误摘要
