## ADDED Requirements

### Requirement: 对话维护写作状态
系统 SHALL 在对话生命周期内维护一个写作状态对象（WritingState），记录当前正在编写的目标模块、使用的 Skill、草稿内容和已保存版本信息。

#### Scenario: 首次生成文档后建立写作状态
- **WHEN** Agent 完成首次文档生成时
- **THEN** 系统 SHALL 在 ConversationInfo 中创建 writing_state，记录 module_id、module_name、skill_id、doc_type 和 draft_content

#### Scenario: 修改轮次更新草稿内容
- **WHEN** Agent 完成一次修改生成时
- **THEN** 系统 SHALL 更新 writing_state.draft_content 为最新生成内容，其他字段保持不变

#### Scenario: 切换新模块时重置写作状态
- **WHEN** 用户意图被识别为 new_module 时（包括「重新写」「从头开始」等指令）
- **THEN** 系统 SHALL 清空 writing_state，进入全量流程重新建立新的写作状态

#### Scenario: writing_state 随对话持久化
- **WHEN** 对话被保存到磁盘时
- **THEN** writing_state SHALL 作为 ConversationInfo 的字段一同序列化保存

#### Scenario: 在 status step 中展示当前写作状态
- **WHEN** 修改轮次开始处理时
- **THEN** Agent SHALL 在 status step 中展示当前写作状态，例如「当前写作目标：LLM 集成模块（草稿 v1.1）」，使用户可验证状态是否正确
