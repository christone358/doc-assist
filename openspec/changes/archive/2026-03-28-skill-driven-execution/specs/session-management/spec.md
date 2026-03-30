## ADDED Requirements

### Requirement: Sub-agent 使用独立临时 session，与主 Agent session 隔离

Skill Sub-agent 在每次 `execute_skill` 调用中使用独立的 ADK session，其 ReAct 历史仅存活于本次调用，执行完毕后销毁，不写入主 Agent session。

#### Scenario: Sub-agent session 与主 Agent session 隔离

- **WHEN** Sub-agent 运行 ReAct 循环时
- **THEN** Sub-agent 使用独立的临时 session_id（不同于主 Agent session），其内部工具调用历史、事实加载返回值不进入主 Agent session；执行完毕后主 Agent session 只追加一条 execute_skill 工具返回摘要

---

### Requirement: Sub-agent 创建时注入跨轮上下文

每次 `execute_skill` 创建 Sub-agent 时，SHALL 将当前 ctx 状态和主 Agent 相关历史摘要注入 Sub-agent，使其了解本次任务的历史背景。

#### Scenario: 注入 ctx 状态摘要

- **WHEN** `execute_skill` 构造 Sub-agent 的初始输入时
- **THEN** 若 `ctx.loaded_base_draft` 有内容，SHALL 在 Sub-agent 初始消息中注明"当前已有草稿（N 字），可调用 get_current_draft 获取"；若 `ctx.last_skill_execution_summary` 非空，SHALL 注明上次写作执行的摘要供参考

#### Scenario: 注入主 Agent 会话摘要

- **WHEN** `execute_skill` 构造 Sub-agent 的初始输入时
- **THEN** 系统 SHALL 从主 Agent session 历史中提取与本次写作任务相关的上下文（如用户在之前轮次提出的修改要求、澄清信息），以简短摘要形式作为 Sub-agent 初始消息的前缀；历史为空或无相关内容时跳过

---

### Requirement: Sub-agent 执行摘要写入 ctx 跨轮传递

#### Scenario: Sub-agent 执行结果写入 ctx 持久化

- **WHEN** Sub-agent 完成写作后
- **THEN** Sub-agent SHALL 将本次执行摘要（加载了哪些事实、基于哪个草稿版本、生成了多少字）写入 `ctx.last_skill_execution_summary`，供后续轮次 Sub-agent 在注入上下文时参考
