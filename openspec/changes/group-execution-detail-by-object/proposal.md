## Why

当前右侧“过程明细”仍以线性时间线和零散状态事件为主，`thinking`、`skill_start`、`status(tool_call/detail)`、`execution_event` 被混合展示，用户很难围绕“谁在执行、执行了什么、输入输出是什么”建立稳定心智模型。

尤其是工具和 Skill 链路仍缺少“对象级”展示契约：工具调用没有稳定的输入/输出视图，Skill 只是开始标记而不是执行容器，思考展示也没有明确区分“可展示的详细思考记录”和“不可直接暴露的内部 raw reasoning”。现在需要把右侧面板重构为按执行对象分组的过程视图，并同步收敛后端事件模型。

## What Changes

- 将右侧“过程明细”从混合时间线调整为按执行对象分组的展示模型，一级对象至少覆盖 `LLM 思考`、`工具调用`、`Skill 调用`、`用户提问`、`系统状态`
- 为工具调用定义稳定的展示契约：每次调用展示工具名称、执行状态、来源类型，并区分输入、输出摘要和可折叠详情
- 将 Skill 调用升级为父级执行容器，展示选择原因、交接摘要，以及其下属的思考与工具调用过程
- 新增结构化执行对象事件契约，为每个可展示对象提供稳定标识、父子关系、状态、输入输出和详情字段，而不是仅靠时间顺序和文本启发式拼接
- 明确思考展示边界：右侧展示“可展示的详细思考记录”，但不得直接透传 provider/raw chain-of-thought 或内部不可控 reasoning 文本
- 明确问题节点、系统状态节点与 Skill 容器的归属规则，以及右侧对象的稳定排序规则，避免双显和顺序歧义
- 明确历史对话回放兼容策略、工具详情体积控制和状态节点生成规则，避免上线后出现历史轮次不可用、消息体过大和状态重复展示
- 更新相关前端归并逻辑、后端事件发射逻辑和验证用例，确保旧链路可回退或兼容过渡

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `execution-chain-visibility`: 将现有执行链路能力从线性事件展示扩展为按执行对象分组的过程明细模型，并补充思考、工具、Skill、提问和系统状态对象的展示契约
- `agent-core`: 流式事件需要携带稳定的对象标识、父子关系，以及工具输入/输出等结构化观测信息
- `web-ui`: 对话页右侧过程明细需要从线性时间线改为对象化分组视图，并支持折叠查看详细信息

## Impact

- `backend/agent/models.py`
- `backend/agent/adk/runner_adapter.py`
- `backend/agent/adk/execute_skill_tool.py`
- `backend/agent/adk/fact_tools.py`
- `backend/agent/adk/mcp_tools.py`
- 其他发出工具调用与执行事件的 ADK 工具模块
- `backend/main.py` WebSocket 流式消息转发
- `frontend/src/lib/stores.js`
- `frontend/src/lib/components/Chat.svelte`
- `frontend/src/lib/components/ObservabilityPanel.svelte`
- 与执行链路、前端归并逻辑相关的后端/前端测试
