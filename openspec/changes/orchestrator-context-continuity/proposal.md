## Why

主 Agent（document_orchestrator）在多轮对话中存在上下文断层：

1. **指代词解析失败**：用户说"这个模块"，Agent 不能从上文解析，反而反问用户
2. **澄清循环中意图丢失**：Agent 提问后收到回答，把回答当作全新请求重新分类，忘记原始意图
3. **每轮独立分类**：instruction 是决策树结构，模型每轮做独立的意图分类，不把对话当连续上文

根本原因不是 LLM 能力不足（DeepSeek-V3 能理解对话上下文），而是 instruction 的决策树结构干扰了模型的自然对话理解能力。在 LLM 固定的前提下，通过重写 instruction 可以解决这类问题。

## What Changes

- **重写 document_orchestrator 的 instruction**：从"每轮分类决策树"改为"持续对话 + 高层次原则"基调
- **新增对话连续性指导**：明确告知模型"会话历史是完整上下文，指代词从历史解析，不得重复询问已建立的信息"
- **新增澄清循环闭合规则**：当 Agent 提问并收到用户回答时，将答案合并回原始意图继续执行，不得将回答当作新请求
- **降低决策树密度**：用高层次原则替代 if-else 分支，减少对模型自然推理的干扰

## Capabilities

### New Capabilities

- `orchestrator-context-continuity`：主 Agent 跨轮上下文感知能力——指代词解析、意图持久化、澄清循环闭合

### Modified Capabilities

- `agent-core`：主 Agent instruction 基调从决策树改为对话连续性原则

## Impact

- `backend/agent/adk/document_agent.py`：instruction 重写（核心改动）
- 不涉及工具列表、数据结构、前端改动
