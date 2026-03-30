## 1. Store

- [x] 1.1 `frontend/src/lib/stores.js` 新增 `obsStore`，包含 `panelOpen`、`events`、`openPanel()`、`clearEvents()`、`addEvent(event)` 方法
- [x] 1.2 ObsEvent 数据结构：`{ type: 'thinking'|'skill'|'status'|'question'|'done', content, extra, ts }`

## 2. ObservabilityPanel 组件

- [x] 2.1 新建 `frontend/src/lib/components/ObservabilityPanel.svelte`，360px 右侧面板，含头部、可滚动内容区
- [x] 2.2 左边缘 chevron 折叠/展开按钮，切换 `obsStore.panelOpen`
- [x] 2.3 时间线布局：渐变竖线 + 彩色圆点 + 分组标题 + 内容卡片
- [x] 2.4 思考推理分组：thinking 累积文本，max-height 240px + 内部滚动
- [x] 2.5 技能调用分组：skill 事件渲染卡片（技能名、调用原因）
- [x] 2.6 状态追踪分组：status 事件 checklist 条目（含草稿版本信息）
- [x] 2.7 向用户提问分组：question 事件 warning 色高亮卡片
- [x] 2.8 完成摘要分组：done 事件 token 统计和技能名

## 3. 后端：草稿版本加载 status 事件

- [x] 3.1 `backend/agent/adk/runner_adapter.py` 在有现有草稿时，流开始时 yield status 事件，内容含模块名和版本

## 4. Chat.svelte 接入

- [x] 4.1 `sendMessage()` 开头调用 `obsStore.clearEvents()`
- [x] 4.2 `handleWSMessage` 中对 thinking/status/skill_start/question/done 调用 `obsStore.addEvent()`，首条 thinking 时调用 `obsStore.openPanel()`
- [x] 4.3 `.chat-root` 改为 `display:flex; flex-direction:row`，`.chat-pane` flex:1，右侧挂载 `<ObservabilityPanel>`
- [x] 4.4 思考气泡标题栏加 `analytics` 图标按钮，点击调用 `obsStore.openPanel()`
- [x] 4.5 保留 thinking 折叠逻辑，但简化（内容已迁移至面板）

## 5. 动画与样式

- [x] 5.1 CSS transition `width 0.3s cubic-bezier(0.4,0,0.2,1)`
- [x] 5.2 折叠 width:0，展开 width:360px
- [x] 5.3 颜色映射：thinking → primary，skill → #8b5cf6，status → text-muted，question → warning，done → success
- [x] 5.4 面板背景 lowest，头部 base，卡片 base，无 1px 分割线
