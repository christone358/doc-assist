## Why

MCP 模式改造后，一次写作的 token 消耗已经从原先约 5000 到 8000 上升到约 19000 到 20000，且前端当前展示的 usage 仍不是整轮真实总成本。当前链路同时存在上下文全文注入、跨阶段重复注入和阶段级用量不可见的问题，已经影响写作成本、响应稳定性和后续优化判断，因此需要系统梳理上下文传递路径并建立可控的 token 预算机制。

## What Changes

- 梳理主 Agent、子 Agent、MCP 工具、`write_document`、写作摘要生成之间的上下文传递路径，明确哪些内容进入历史、哪些内容只进入当轮写作上下文。
- 为写作链路新增 token 足迹控制能力，包括来源分层、内容去重、预算裁剪、摘要化回传和重复注入消除。
- 为整轮执行补充阶段级 token 观测，区分 orchestrator、subagent、write_document、summary 等调用成本，并输出聚合总量。
- 调整前端与持久化模型，使展示和历史恢复使用“整轮总 token + 分阶段明细”，而不是仅展示单次正文写作调用。
- 收敛 Skill 参考资料、原型页面和历史文档的注入策略，避免在 ADK 历史与最终写作 prompt 中重复消耗同一份大文本。

## Capabilities

### New Capabilities
- `writing-token-footprint-control`: 定义写作链路的上下文传递边界、预算裁剪、来源去重、摘要化回传和阶段级 token 观测要求。

### Modified Capabilities
- `agent-core`: 调整 done chunk 与执行链元数据，使其能够返回整轮聚合 token、分阶段 token 明细和上下文体量指标。
- `llm-integration`: 扩展 LLM 调用结果模型，支持记录多次调用的阶段级 usage，并提供整轮聚合统计。
- `token-usage-display`: 将 UI 展示从单次调用 token 统计升级为整轮总量与分阶段明细展示。
- `structured-context-loading`: 调整上下文加载行为，使写作上下文遵循预算、去重和摘要化注入策略，不再默认把大块原文重复写入历史与最终 prompt。

## Impact

- Affected code:
  - `backend/agent/adk/runner_adapter.py`
  - `backend/agent/adk/execute_skill_tool.py`
  - `backend/agent/adk/write_document_tool.py`
  - `backend/agent/adk/mcp_tools.py`
  - `backend/main.py`
  - 前端消息元信息展示与历史恢复相关代码
- Affected systems:
  - 主 Agent / 子 Agent 执行链路
  - MCP 上下文装载链路
  - 对话持久化模型与 Web UI token 展示
- No external API breaking change is intended, but done chunk、历史 `llm_info` 和内部执行观测结构会扩展字段。
