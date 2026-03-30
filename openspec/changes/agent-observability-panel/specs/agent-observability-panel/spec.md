## ADDED Requirements

### Requirement: Agent 可观测性明细面板
Web UI SHALL 提供一个可收缩的右侧滑动面板，以时间线形式展示当前轮次 Agent 运行的完整过程明细，包括思考推理、技能调用、状态追踪和完成摘要。

#### Scenario: 面板展开时压缩对话区域
- **WHEN** 用户展开可观测性面板
- **THEN** Web UI SHALL 将对话区域宽度压缩（面板与对话区并排），面板宽度约 360px，通过 CSS transition 平滑过渡，不使用覆盖层

#### Scenario: 面板折叠恢复对话区域
- **WHEN** 用户点击面板左边缘的 chevron 收起按钮
- **THEN** Web UI SHALL 将面板宽度动画收缩至 0，对话区域恢复全宽

#### Scenario: 接收到思考事件时自动展开
- **WHEN** Agent 开始思考（WebSocket 接收到第一条 `thinking` 类型事件）
- **THEN** Web UI SHALL 自动展开可观测性面板

#### Scenario: 时间线分组展示
- **WHEN** 可观测性面板处于展开状态
- **THEN** Web UI SHALL 按到达时序将事件分为以下分组，以垂直时间线形式呈现：
  1. **思考推理**（thinking 事件）：展示 LLM 完整思考文本，可内部滚动
  2. **技能调用**（skill_start 事件）：每次调用展示为独立卡片，包含技能名称和调用原因
  3. **状态追踪**（status 事件）：按顺序列出各状态步骤，包含草稿版本加载信息（如"已加载草稿：需求文档 v1.2.0"）
  4. **向用户提问**（question 事件）：Agent 提出的澄清问题，以高亮卡片（warning 色）展示问题内容
  5. **完成摘要**（done 事件）：展示本轮 token 用量和技能名称

#### Scenario: 每轮开始时清空明细
- **WHEN** 用户发送新消息（新一轮对话开始）
- **THEN** Web UI SHALL 清空面板中上一轮的事件数据，重新开始收集本轮事件

#### Scenario: 时间线视觉样式
- **WHEN** 面板展示时间线内容
- **THEN** Web UI SHALL 遵循 Editorial Light 设计规范：
  - 每个分组左侧有从颜色到透明的渐变竖线
  - 分组标题左侧有彩色圆点（thinking 用 primary 色，skill 用 secondary 色，status 用 tertiary 色，done 用 success 色）
  - 分组标题为小号全大写加粗文字
  - 内容卡片使用 `var(--high)` 或 `var(--base)` 背景，无 1px 分割线

#### Scenario: 思考推理内容高度限制
- **WHEN** thinking 内容超过一定高度
- **THEN** Web UI SHALL 限制思考区最大高度并支持内部滚动，避免面板被单个 thinking 块撑满

#### Scenario: 二级入口：从思考气泡打开面板
- **WHEN** 对话气泡中存在思考内容（thinking block）
- **THEN** Web UI SHALL 在思考区标题栏显示一个小图标按钮，点击后展开可观测性面板
