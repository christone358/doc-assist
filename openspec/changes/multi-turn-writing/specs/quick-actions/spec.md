## ADDED Requirements

### Requirement: 文档生成后展示快捷操作按钮
Agent 完成文档生成后，前端 SHALL 在消息末尾展示快捷操作按钮，供用户触发常用操作，且不阻塞继续对话。

#### Scenario: 生成完成后展示保存按钮
- **WHEN** Agent 完成一轮文档生成，后端发送 done 事件且包含 draft_content 时
- **THEN** 前端 SHALL 在该消息末尾渲染「💾 保存为正式版本」按钮

#### Scenario: 保存按钮不阻塞输入框
- **WHEN** 快捷操作按钮显示时
- **THEN** 输入框和发送按钮 SHALL 保持可用状态，用户可直接输入下一轮指令而无需先点击按钮

#### Scenario: 点击保存触发落盘
- **WHEN** 用户点击「保存」按钮时
- **THEN** 前端 SHALL 调用 save-draft API，成功后将按钮状态更新为「✓ 已保存 v1.x」并显示文件路径

#### Scenario: 已保存后按钮状态更新
- **WHEN** 保存操作成功完成时
- **THEN** 「保存」按钮 SHALL 变更为已保存状态（不可再次点击），展示版本号和文件路径
