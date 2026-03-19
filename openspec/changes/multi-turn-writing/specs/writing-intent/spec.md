## ADDED Requirements

### Requirement: 多轮写作意图识别
Agent SHALL 在每轮对话中识别用户的写作意图，区分三种类型并驱动不同的处理流程。

#### Scenario: 识别修改意图走轻量流程
- **WHEN** 用户消息表达对当前文档的修改或补充（如「增加文字量」「调整章节顺序」「补充验收标准」）且 writing_state 存在时
- **THEN** Agent SHALL 识别为 modify 意图，沿用 writing_state 中的 module_id 和 skill_id，以 draft_content 作为主上下文，不重新识别模块，不重新加载项目事实

#### Scenario: 识别新模块意图走全量流程
- **WHEN** 用户消息中明确提到一个与当前 writing_state.module_id 不同的模块、明确表达要写新文档，或包含「重新写」「从头开始」「全部重写」等重写指令时
- **THEN** Agent SHALL 识别为 new_module 意图，清空 writing_state，执行完整的模块识别和项目事实加载流程

#### Scenario: 无 writing_state 时始终走全量流程
- **WHEN** 对话尚未建立 writing_state（首次发送消息）时
- **THEN** Agent SHALL 不执行意图分类，直接执行全量流程（模块识别 + 项目事实加载）
