## MODIFIED Requirements

### Requirement: Agent 访问项目事实信息
Agent SHALL 通过结构化的多步骤流程访问项目事实信息，并根据写作状态决定是否需要重新加载项目事实。

#### Scenario: 首次写作时执行全量上下文加载流程
- **WHEN** 对话不存在 writing_state（首次写作）或意图为 new_module 时
- **THEN** Agent SHALL 执行完整的上下文加载流程：模块识别 → 推断词汇列表 → 加载项目事实 → 生成文档

#### Scenario: 修改轮次跳过项目事实加载
- **WHEN** 意图识别为 modify 且 writing_state.draft_content 存在时
- **THEN** Agent SHALL 跳过模块识别和项目事实加载步骤，直接以 draft_content 全文作为上下文传入 LLM

#### Scenario: 模块定位时检查历史已保存版本
- **WHEN** 全量流程定位到模块后
- **THEN** Agent SHALL 检查该模块对应的文档目录，若存在已保存版本则加载最新版内容作为写作基准，并在 status step 中提示「已找到 {模块名} 的历史版本 v{x.y}，将基于此版本继续编写」

#### Scenario: 修改轮次展示当前写作状态
- **WHEN** 修改轮次开始执行时
- **THEN** Agent SHALL 在第一个 status step 中展示：「当前写作目标：{模块名}（{草稿版本状态}）」
