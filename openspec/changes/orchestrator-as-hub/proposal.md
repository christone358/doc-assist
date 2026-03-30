## Why

当前主 Agent（document_orchestrator）是一个路由器：一次性决策、线性执行、结果黑盒。
这份文档记录了将其演进为"编排中枢"的完整设计思路，作为后续各 change 的蓝本。

## What Changes

- 主 Agent 从路由器升级为规划器 + 状态管理器
- Sub-agent 返回结构化执行结果（取代自由文本摘要）
- Orchestrator 维护对话级任务状态
- Skill 声明能力接口，支持动态发现与组合

## Capabilities

### New Capabilities

- `orchestrator-task-planning`：目标分解与多步任务规划能力
- `orchestrator-state-management`：跨轮任务状态感知与持久化
- `orchestrator-capability-registry`：Skill 能力注册与动态发现
- `orchestrator-failure-recovery`：结构化失败信号与重试策略
- `orchestrator-intent-refinement`：渐进式意图精化（行动优先）

### Modified Capabilities

- `agent-core`：Orchestrator 职责从路由扩展到规划与状态管理
- `skill-execution-workflow`：execute_skill 返回结构化 SkillExecutionResult

## Impact

- `backend/agent/adk/document_agent.py`
- `backend/agent/adk/execute_skill_tool.py`
- `backend/agent/adk/runner_adapter.py`（ConversationContext 扩展）
- `skills/*/skill.md`（能力接口声明）
