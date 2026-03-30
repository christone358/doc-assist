## ADDED Requirements

### Requirement: 支持按 Agent 角色独立配置 LLM 模型

系统 SHALL 允许用户为 Orchestrator Agent 和 Worker Agent 分别指定 LLM 模型，以实现"强推理模型用于路由决策，标准模型用于写作执行"的分层策略。

#### Scenario: Orchestrator 使用专用模型

- **WHEN** 系统启动一轮对话时
- **THEN** document_orchestrator SHALL 优先使用 `role="orchestrator"` 的 LLM 配置；若无此角色配置，回退到 `role="default"` 的配置

#### Scenario: Worker 使用专用模型

- **WHEN** execute_skill 创建 Skill Sub-agent 时
- **THEN** doc_worker_* Sub-agent SHALL 优先使用 `role="worker"` 的 LLM 配置；若无此角色配置，回退到 `role="default"` 的配置

#### Scenario: 未配置角色模型时静默回退

- **WHEN** 用户未配置 orchestrator 或 worker 专用模型时
- **THEN** 系统 SHALL 静默回退到 default 模型，行为与升级前完全一致，无需用户干预

#### Scenario: 前端展示角色标签

- **WHEN** 用户在 LLM 配置界面管理模型时
- **THEN** 每个配置项 SHALL 显示其角色标签（Orchestrator / Worker / Default），用户可在添加或编辑时指定角色
