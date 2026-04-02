## MODIFIED Requirements

### Requirement: Agent 通过两步渐进式工具访问历史已保存文档
系统 SHALL 提供两个工具支持历史文档访问，遵循渐进式披露原则：第一步获取元数据清单，第二步按需加载正文；正文不写入 ADK session 历史。

#### Scenario: 列出可用历史文档
- **WHEN** 编排 LLM 需要了解有哪些历史已保存文档可用时
- **THEN** 系统 SHALL 调用 `list_saved_documents(doc_type?)` 工具，并且仅返回 `doc_output/` 中管理的正式文档元数据清单

#### Scenario: 加载历史文档正文（双路输出）
- **WHEN** 编排 LLM 决定以指定历史文档作为写作基础，调用 `load_saved_document(doc_type, doc_name)` 时
- **THEN** 工具 SHALL 仅从 `doc_output/` 中加载匹配的正式版本正文，并保持摘要进历史、正文进 `ctx.loaded_base_draft` 的双路输出模式

#### Scenario: legacy 输出不再纳入历史文档工具结果
- **WHEN** `backend/docs/` 中仍存在 legacy 输出文档
- **THEN** `list_saved_documents` 与 `load_saved_document` SHALL NOT 将这些 legacy 输出文档纳入结果或读取来源
