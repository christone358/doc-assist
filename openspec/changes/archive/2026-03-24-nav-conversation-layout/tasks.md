## 1. 后端：新增对话名称更新接口

- [x] 1.1 在 `backend/main.py` 中新增 `PATCH /api/v1/conversations/{conversation_id}` 端点，接受 `{"name": "<new_name>"}` 请求体并更新对话名称
- [x] 1.2 在 `backend/main.py` 中新增 `POST /api/v1/conversations/{conversation_id}/auto-name` 端点，使用首轮 user_input + agent_response 调用 LLM（温度 0.3，max_tokens 50）生成标题，返回并保存

## 2. 前端：重构布局——移除独立 ConvSidebar，实现三区导航

- [x] 2.1 修改 `+layout.svelte`：移除 `sidebar-panel` aside 元素及其条件渲染逻辑，扩展导航栏宽度至 240px
- [x] 2.2 修改 `+layout.svelte`：导航栏改为 `display: flex; flex-direction: column`，分三个子区域——顶部菜单区（`flex-shrink: 0`）、中间对话记录区（`flex: 1; overflow-y: auto`）、底部设置区（`flex-shrink: 0; margin-top: auto`）
- [x] 2.3 将 LLM 配置从顶部 `tabs` 数组移除，在底部设置区单独渲染 LLM 配置菜单项
- [x] 2.4 修改 `+layout.svelte`：在中间区域顶部放置「新对话」按钮，下方展示对话列表（通过 store 读取 convList）
- [x] 2.5 修改 `+layout.svelte`：引入 `convList`、`activeConvId`、`convRefresh` store，在 onMount 时加载对话列表，监听 convRefresh 刷新

## 3. 前端：实现按日期分组的对话列表

- [x] 3.1 在 `+layout.svelte` 的 script 中实现日期分组函数，将 convList 按 updated_at 分为「今天」「昨天」「更早」三组
- [x] 3.2 在导航栏内渲染分组标题和对话列表，当前对话高亮，点击切换对话并跳转到 Chat tab
- [x] 3.3 为对话列表区设置 `max-height` 和 `overflow-y: auto`，使菜单项固定、列表可滚动
- [x] 3.4 为每个对话项添加删除按钮（hover 显示），删除后刷新列表

## 4. 前端：调整 Chat 组件

- [x] 4.1 移除 `Chat.svelte` 中已不再使用的顶部"新对话"按钮（或将其样式降级为次要按钮），保持与导航栏"新对话"按钮功能一致
- [x] 4.2 在 `Chat.svelte` 中监听 `done` 事件：若对话名称仍为默认格式（以"对话 "开头），异步调用 `/api/v1/conversations/{id}/auto-name`，成功后触发 convRefresh 刷新导航栏列表

## 5. 前端：ConvSidebar 组件清理

- [x] 5.1 将 `ConvSidebar.svelte` 标记为废弃或删除（其功能已迁移至 `+layout.svelte`），确认无其他引用后移除

## 6. 收尾

- [x] 6.1 构建前端，确认无编译错误（`npm run build`）
