## Why

当前布局将对话记录放在主内容区右侧单独的侧边栏，仅在"对话"tab 下才可见，且占用了额外的宽度。同时，新对话的默认命名采用时间戳格式，缺乏语义信息，用户难以快速识别历史对话内容。将对话记录整合到左侧导航栏，可以减少布局层级、释放内容区宽度，并在所有 Tab 下均可访问。

## What Changes

- 将"对话记录"列表从独立的右侧侧边栏（`ConvSidebar`）移动到左侧导航菜单栏，位于菜单项下方
- 对话记录按日期分组展示
- 将聊天区域顶部的"+ 新对话"按钮文本改为"新对话"（去除加号前缀，使用图标代替）
- 新对话默认命名方式从时间戳格式（"对话 2024-01-15 14:30"）改为 AI 自动摘要命名，由 Agent 在首轮对话结束后根据用户意图生成简短标题
- 移除独立的对话侧边栏（`sidebar-panel` 区域），缩减整体布局层级

## Capabilities

### New Capabilities

- `conversation-auto-naming`: 对话完成首轮交互后，由 Agent/LLM 自动生成简短的语义化标题，替换默认的时间戳命名

### Modified Capabilities

- `web-ui`: 布局结构变更——移除独立 ConvSidebar 区域，对话记录列表嵌入左侧导航栏，按日期分组展示
- `conversation-management`: 新对话的默认命名逻辑变更，接入自动摘要命名能力

## Impact

- **前端**：`+layout.svelte`（移除 sidebar-panel，调整 nav 区域）、`ConvSidebar.svelte`（重构为嵌入式列表）、`Chat.svelte`（触发自动命名逻辑）
- **后端**：`backend/agent/core.py` 或 `backend/main.py` 新增"对话标题自动生成"接口或在 done 事件后调用命名逻辑
- **API**：可能新增 `PATCH /conversations/{id}` 更新对话名称的端点（若尚未存在）
