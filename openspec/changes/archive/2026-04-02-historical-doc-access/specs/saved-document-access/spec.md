## ADDED Requirements

### Requirement: Agent 通过两步渐进式工具访问历史已保存文档

系统 SHALL 提供两个工具支持历史文档访问，遵循渐进式披露原则：第一步获取元数据清单，第二步按需加载正文；正文不写入 ADK session 历史。

#### Scenario: 列出可用历史文档

- **WHEN** 编排 LLM 需要了解有哪些历史已保存文档可用时
- **THEN** 系统 SHALL 调用 `list_saved_documents(doc_type?)` 工具，返回匹配的文档元数据清单（每项包含 doc_type、doc_name、latest_version、latest_date），整体结果作为字符串写入 ADK session 历史；若无任何文档则返回说明性文字

#### Scenario: 加载历史文档正文（双路输出）

- **WHEN** 编排 LLM 决定以指定历史文档作为写作基础，调用 `load_saved_document(doc_type, doc_name)` 时
- **THEN** 工具 SHALL 执行双路输出：
  1. 向 ADK session 历史返回摘要字符串（如"已加载 [doc_name] v1.0.1 · 2026-03-20，共 N 字，就绪"），不含正文
  2. 将正文完整内容存入 `ctx.loaded_base_draft`（per-round 字段，不写入 session 历史）
- 若文档不存在，则返回说明性文字，`ctx.loaded_base_draft` 不更新

#### Scenario: write_document 自动衔接已加载的历史正文

- **WHEN** `write_document` 被调用且 `context` 参数为空字符串，但 `ctx.loaded_base_draft` 有内容时
- **THEN** 写作 LLM 的上下文 SHALL 使用 `ctx.loaded_base_draft` 作为草稿基础，等同于修改场景；效果与 LLM 显式传入 context 参数相同，但大段文本不出现在 LLM 的函数调用参数中

#### Scenario: 历史文档与对话草稿的优先级

- **WHEN** `write_document` 被调用时，`context` 参数和 `ctx.loaded_base_draft` 同时有内容
- **THEN** 系统 SHALL 优先使用 `context` 参数（对话内中间草稿优先），`ctx.loaded_base_draft` 作为备用
