## Why

当前对话界面对 Agent 的内部决策过程完全不透明——用户只能看到最终回复，无法了解 Agent 的思考、工具调用和技能调度过程。增加一个可收缩的可观测性明细面板，让用户在需要时可以查看 Agent 自主运行的完整过程，提升对系统行为的信任感和可调试性。

## What Changes

- 新增右侧滑动面板组件（`ObservabilityPanel`），以时间线形式展示 Agent 每轮运行的明细数据
- 面板展开时压缩对话区域宽度，收起时恢复；通过边缘 chevron 按钮切换
- 面板内容按事件类型分组展示：思考（Thinking）→ 状态/技能调用（Skill Execution）→ 工具调用结果（Tool Result）→ 完成摘要（Done）
- 在 Agent 思考开始时自动展开面板；用户可手动收起
- 对话气泡内的思考区域标题栏增加"打开明细"小按钮，作为二级入口
- 面板底部展示本轮延迟和 token 统计

## Capabilities

### New Capabilities
- `agent-observability-panel`: 右侧可收缩明细面板，展示 Agent 运行时的思考、技能调用、工具执行、完成摘要等分组时间线数据

### Modified Capabilities
- `web-ui`: 对话区域布局需支持右侧面板展开时的压缩响应

## Impact

- **前端**：`Chat.svelte`（接入面板开关逻辑、thinking 事件触发自动展开）、新增 `ObservabilityPanel.svelte` 组件
- **数据**：复用现有 WebSocket 事件流（`thinking`、`status`、`skill_start`、`done`），无需后端改动
- **样式**：遵循 Editorial Light 设计规范，参考 `docs/thinking-info-design/` 视觉稿
