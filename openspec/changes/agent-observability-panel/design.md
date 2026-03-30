## Context

当前 Chat.svelte 已通过 WebSocket 接收 Agent 的实时事件流（`thinking`、`status`、`skill_start`、`done` 等），但这些中间过程数据仅被轻量展示在对话气泡内（thinking 折叠块、status steps）。设计稿（`docs/thinking-info-design/`）展示了一种右侧滑动面板，将 Agent 的推理链按时间线分组呈现，视觉层次清晰、信息密度合理。

本变更纯前端实现，复用现有 WS 事件流，无需后端修改。

## Goals / Non-Goals

**Goals:**
- 新增 `ObservabilityPanel.svelte` 组件，以时间线卡片形式展示当前轮次的 Agent 运行明细
- Panel 可通过边缘 chevron 按钮折叠/展开，展开时压缩对话区域（CSS flex transition）
- 接收到 `thinking` 事件时自动展开面板
- 对话气泡内 thinking 标题栏添加"打开明细"小按钮（二级入口）
- 遵循 Editorial Light 设计规范（渐变时间线、colored dots、卡片背景层次）

**Non-Goals:**
- 不持久化每轮可观测数据（仅保存当前活跃轮次，刷新即重置）
- 不在历史对话中回放可观测明细（仅对当前实时流程有效）
- 不新增后端 API 或数据模型

## Decisions

### 1. 数据存储：Svelte store

新增 `obsStore` store（`$lib/stores.js`），包含：
- `panelOpen: boolean`
- `events: ObsEvent[]` — 当前轮次事件列表，每轮开始时清空

ObsEvent 结构：
```js
{ type: 'thinking'|'skill'|'status'|'done', content, extra, ts }
```

**替代方案**：props down from Chat.svelte → 避免，因为 ObservabilityPanel 需要跨层访问，store 更简洁。

### 2. 布局：flex 同层并排

Chat.svelte 的 `.chat-root` 改为 `display:flex; flex-direction:row`：
- 左侧 `.chat-pane`：`flex:1; min-width:0; overflow:hidden`
- 右侧 `<ObservabilityPanel>`：`width: 360px`（展开）/ `width: 0`（折叠），`transition: width 0.3s`

**替代方案**：`position:fixed` 覆盖层 → 不选，因为设计要求压缩对话区，而非覆盖。

### 3. 时间线分组逻辑

按事件类型映射到 4 个视觉分组（参考设计稿的4步时间线）：

| WS 事件 | 面板分组 | 颜色 |
|---|---|---|
| `thinking` | 思考推理 | `--primary` (#6366F1) |
| `skill_start` | 技能调用 | secondary purple |
| `status` | 执行状态 | tertiary rose |
| `done` | 完成摘要 | success green |

每组只保留同类最新内容（thinking 累积文本，skill/status 追加卡片）。

### 4. 自动展开触发

在 Chat.svelte 的 `handleWSMessage` 中，当 `data.type === 'thinking'` 且为第一条 thinking 事件时，调用 `obsStore.open()`。

### 5. 轮次清空

在 `sendMessage()` 开始处调用 `obsStore.clearEvents()`，确保每轮开始前清空上轮数据，面板展示始终对应当前轮次。

## Risks / Trade-offs

- **面板宽度占用**：360px 在小屏幕（< 900px）可能导致对话区过窄。缓解：面板默认折叠，由 thinking 事件触发自动展开，用户可立即折叠。
- **thinking 内容量大**：深度思考模型的 thinking 可能很长。缓解：面板内思考区最大高度限制 + 内部滚动。
- **事件顺序**：同一轮内 `status`/`skill_start` 可能交错出现。缓解：按到达顺序 append，不做重排，保持真实时序。
