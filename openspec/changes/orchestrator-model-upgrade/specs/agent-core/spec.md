## MODIFIED Requirements

### Requirement: 主 Agent 使用 Orchestrator 专用模型

document_orchestrator 的模型配置 SHALL 独立于 Sub-agent，支持配置更强推理能力的模型。

#### Scenario: 主 Agent 读取 orchestrator 角色配置

- **WHEN** `build_document_agent` 初始化主 Agent 时
- **THEN** 主 Agent SHALL 调用 `get_litellm_model_config(role="orchestrator")` 获取模型；无 orchestrator 专用配置时回退到 default

#### Scenario: Sub-agent 读取 worker 角色配置

- **WHEN** `_build_skill_subagent` 初始化 doc_worker_* 时
- **THEN** Sub-agent SHALL 调用 `get_litellm_model_config(role="worker")` 获取模型；无 worker 专用配置时回退到 default

### Requirement: 主 Agent instruction 随模型能力动态简化（可选优化）

当 Orchestrator 配置为思考型模型时，instruction 可适当精简。

#### Scenario: 思考型模型下减少硬编码决策规则

- **WHEN** Orchestrator 使用思考型模型（如 DeepSeek-R1、QwQ）时
- **THEN** instruction 的负向约束（"不得做 X"、"禁止调用 Y"）可逐步移除，改为高层次职责描述；草稿状态 hint 等上下文注入保留不变
