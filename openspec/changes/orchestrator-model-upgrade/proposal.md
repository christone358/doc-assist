## Why

主 Agent（document_orchestrator）使用标准 LLM（如 DeepSeek-V3），以复杂 instruction 决策树补偿推理能力不足，导致工具误用、意图误判频发——如把"有没有用户手册"误判为写作请求、缺少工具时误用相近工具、有草稿时仍询问多余问题。根本原因不是 instruction 不够细，而是标准 LLM 的 token 预测机制无法真正验证推理结果；打补丁只能延缓问题，不能消除。

## What Changes

- **主 Agent 支持独立模型配置**：document_orchestrator 可配置使用与 Sub-agent 不同的 LLM（如思考型模型 DeepSeek-R1、Qwen-QwQ），Sub-agent 继续使用标准模型
- **主 Agent instruction 大幅简化**：移除大量 if-else 决策规则，改为高层次职责描述；将推理判断的责任还给模型本身
- **LLM 配置体系扩展**：现有配置仅支持一个默认模型；新增支持按角色（orchestrator / worker）指定不同模型
- **运行时模型选择**：build_document_agent 和 _build_skill_subagent 分别从配置中读取对应角色的模型

## Capabilities

### New Capabilities

- `orchestrator-model-config`：支持为 Orchestrator Agent 独立配置 LLM 模型，与 Worker Agent 解耦

### Modified Capabilities

- `llm-integration`：LLM 配置体系从单一默认模型扩展为支持多角色模型配置（orchestrator / worker）
- `agent-core`：主 Agent instruction 随模型能力提升而简化，减少决策树依赖

## Impact

- `backend/llm/service.py`：新增角色维度的模型查询接口
- `backend/agent/adk/document_agent.py`：读取 orchestrator 角色模型配置
- `backend/agent/adk/execute_skill_tool.py`：读取 worker 角色模型配置
- 前端 LLM 配置界面：新增角色选择（orchestrator / worker / default）
- 现有单模型配置自动回退为两个角色共用 default 模型，**不破坏现有配置**
