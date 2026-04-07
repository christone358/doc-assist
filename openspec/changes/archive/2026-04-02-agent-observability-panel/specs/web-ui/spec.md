## MODIFIED Requirements

### Requirement: Web UI 提供自然语言输入界面
Web 应用应该提供一个用户友好的界面，让用户用自然语言描述文档编写需求。

#### Scenario: 提交文档需求
- **WHEN** 用户在输入框中输入文档编写需求并点击提交
- **THEN** Web UI 应该将请求发送给 Agent，并显示处理中的状态

#### Scenario: 清空和重置
- **WHEN** 用户需要重新开始新的文档编写任务
- **THEN** Web UI 应该提供"新对话"按钮，点击后创建新对话并清空消息列表

#### Scenario: 左侧导航栏布局
- **WHEN** 用户访问应用
- **THEN** Web UI SHALL 呈现两栏布局：左侧导航栏（含菜单项 + 对话记录列表）+ 右侧主内容区，主内容区宽度在所有 Tab 下保持一致，不再因 ConvSidebar 的显隐而变化

#### Scenario: 导航栏对话记录区
- **WHEN** 用户在左侧导航栏
- **THEN** Web UI SHALL 在菜单项下方显示对话记录列表，列表按日期分组（今天 / 昨天 / 更早），每项显示对话名称，点击可切换对话，当前对话高亮显示

#### Scenario: 导航栏新对话入口
- **WHEN** 用户需要创建新对话
- **THEN** Web UI SHALL 在导航栏对话记录区顶部提供"新对话"按钮，点击后创建新对话并切换到 Chat tab

#### Scenario: 导航栏三区垂直分隔
- **WHEN** 用户查看左侧导航栏
- **THEN** Web UI SHALL 将导航栏在垂直方向明确分为三个区域：
  1. **顶部菜单区**（固定，不随列表滚动）：Logo + 主功能菜单项（对话、Skill、文档、项目事实），`flex-shrink: 0`
  2. **中间对话记录区**（`flex: 1; overflow-y: auto`，独立滚动）：「新对话」按钮 + 按日期分组的对话列表
  3. **底部设置区**（固定在底部，`flex-shrink: 0`）：LLM 配置入口，视觉上通过足够的 padding 间距与中间区域分隔
- 三区之间通过空间（`margin-top: auto` 将底部区推至底部 + 区间 padding）区分，不使用 1px 分割线

#### Scenario: LLM 配置入口移至底部
- **WHEN** 用户访问应用
- **THEN** Web UI SHALL 将 LLM 配置入口从顶部 Tab 菜单移除，放置在导航栏底部设置区，样式与顶部菜单项一致，点击切换到 LLM 配置页面

#### Scenario: Chat 视图支持右侧可观测性面板
- **WHEN** 用户在 Chat 视图且可观测性面板展开
- **THEN** Web UI SHALL 将 Chat 视图内容区与可观测性面板并排显示（flex row），对话区宽度自适应压缩，面板宽度固定约 360px；面板折叠时对话区恢复全宽
