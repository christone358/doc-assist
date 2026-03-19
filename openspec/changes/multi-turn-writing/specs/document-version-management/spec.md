## MODIFIED Requirements

### Requirement: 文档版本写入时机
文档 SHALL 仅在用户显式触发保存操作时写入文件系统，不在 LLM 生成完成时自动落盘。

#### Scenario: 文档内容生成后不自动写入文件
- **WHEN** LLM 完成文档内容生成时
- **THEN** 系统 SHALL 不执行任何文件写入操作，生成内容仅更新内存中的 writing_state.draft_content

#### Scenario: 用户调用 save-draft 接口时写入文件
- **WHEN** 后端收到 POST /conversations/{id}/save-draft 请求时
- **THEN** 系统 SHALL 将 draft_content 按现有版本目录结构写入文件系统，版本号在上一保存版本基础上递增
