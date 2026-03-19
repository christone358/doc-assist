## ADDED Requirements

### Requirement: 草稿与正式版本分离
系统 SHALL 将 LLM 生成的文档内容先保存为草稿（内存），仅在用户显式触发保存操作时才将草稿写入文件系统作为正式版本。

#### Scenario: 生成结果作为草稿不自动落盘
- **WHEN** Agent 完成任意一轮文档生成时
- **THEN** 生成内容 SHALL 只更新 writing_state.draft_content，不触发任何文件写入操作

#### Scenario: 用户触发保存时草稿落盘
- **WHEN** 用户点击「保存」按钮，前端调用 save-draft API 时
- **THEN** 系统 SHALL 将 draft_content 写入文件系统，版本号在最新已保存版本基础上递增（v1.0 → v1.1 → v1.2），并更新 writing_state.saved_version 和 writing_state.saved_path

#### Scenario: 多次保存版本号递增
- **WHEN** 同一对话中用户多次点击「保存」时
- **THEN** 每次保存 SHALL 生成新的递增版本号，之前的版本文件保留不覆盖

#### Scenario: 未保存草稿在对话关闭后丢失
- **WHEN** 用户关闭浏览器或结束对话且未点击保存时
- **THEN** 内存中的 draft_content SHALL 被丢弃，不自动写入文件系统
