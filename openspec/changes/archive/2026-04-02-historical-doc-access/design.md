## Context

Agent 的修改场景目前分两个路径：对话内中间草稿（`session.state["draft_content"]`）和对话持久化草稿（`conv.writing_state.draft_content`）。两者都是当前对话范围内的数据，无法访问用户通过"保存"动作显式存档的历史版本（存储于 `doc_version_service`，路径为 `docs/[doc_type]/[doc_name]/[date]/vX.Y.Z.md`）。

当前 `done` 事件的 `writing_state_data` 中 `module_name` 和 `doc_type` 字段为空字符串，导致每次保存文档时 `module_name=""` 被当作文档名写入磁盘，查询时也无法用真实模块名找到对应文件。这是历史版本访问的前置 bug。

已有渐进式披露设计基础：事实工具（`get_fact_overview` / `get_fact_detail`）采用双路输出——摘要进 ADK 历史，原始内容进 `collected_facts_parts`。历史文档访问应遵循相同模式。

## Goals / Non-Goals

**Goals:**
- Agent 能发现并列出历史已保存的文档版本（元数据，不加载正文）
- Agent 能按需加载指定文档的最新版本正文，正文不写入 ADK session 历史
- 写作 LLM 能以历史版本正文作为草稿基础，上下文干净
- 修复 `writing_state_data` 中 `module_name` / `doc_type` 为空的 bug
- Instruction 明确区分两种草稿来源，引导 LLM 正确决策

**Non-Goals:**
- 加载指定版本号（只加载最新版，特定版本加载留后续）
- 跨文档类型的版本比较或差异展示
- 修改 `doc_version_service` 的存储结构

## Decisions

### 决策 1：两个独立工具，不扩展 get_current_draft

`get_current_draft` 是"当前对话的工作草稿"，零参数，隐含当前 conversation_id 语义。历史版本访问需要 `doc_type` + `doc_name` 参数，属于跨对话查询，职责不同。

拆分为两个工具：
- `list_saved_documents(doc_type?)` — 发现层，返回元数据清单
- `load_saved_document(doc_type, doc_name)` — 加载层，双路输出

**备选：** 单一工具合并两步。**否决原因：** LLM 需要先看到清单确认文档存在，再决定是否加载，两步决策对应两次工具调用，拆开更符合 ReAct 的推理模式，也更易在 observability 面板中追踪。

### 决策 2：正文存入 ctx.loaded_base_draft，不进 ADK 历史

与 `collected_facts_parts` 的处理逻辑对称：大段内容不进 ADK session 历史，只通过进程内字段传递给写作 LLM。

`ctx.loaded_base_draft: Optional[str]` 是 per-round 字段，每轮 `stream_message` 创建新 `ConversationContext` 时自动清零，不需要跨轮持久化。

### 决策 3：write_document 自动衔接，context 参数传空字符串

LLM 调用 `write_document` 时 `context=""` 即可，不需要把大段文本塞进函数调用参数（那会进入 ADK 历史）。`write_document` 内部读取优先级：

```
context 有内容 → 使用 context（对话内中间草稿，由 LLM 从 get_current_draft 获取后传入）
context 为空 + ctx.loaded_base_draft 有内容 → 使用 loaded_base_draft（历史版本）
两者都空 → 纯新建场景
```

### 决策 4：module_name 和 doc_type 由 write_document 工具提供

`write_document` 已接收 `skill_id`，从 `skills_map[skill_id]` 可取 `skill.type` 作为 `doc_type`。`module_name` 需新增为 `write_document` 的参数，由编排 LLM 传入（LLM 已从 `get_fact_overview` 知道模块名）。

这两个字段通过 `tool_context.state` 传递给 `done` 事件，修复 `writing_state_data` 中为空的 bug。

## Risks / Trade-offs

**[风险] doc_name 命名不一致**：`list_saved_documents` 返回的 `doc_name` 是磁盘上的目录名，来自历史写作时 `module_name` 的值。若用户历史写作时 `module_name` 为空（bug 修复前的数据），旧文件无法被新工具找到。
→ 接受：bug 修复后新增的保存才能被查询到；历史存档的孤立文件不处理。

**[Trade-off] module_name 参数增加 LLM 调用复杂度**：LLM 调用 `write_document` 时需同时传 `skill_id`、`module_name`、`context`、`user_intent` 四个参数。
→ 可接受：`module_name` 对 LLM 而言是已知信息（来自 `get_fact_overview`）；instruction 中明确说明。

**[风险] loaded_base_draft 在同一轮被覆盖**：若 LLM 在一轮中多次调用 `load_saved_document`，后一次会覆盖前一次的 `loaded_base_draft`。
→ 接受：正常使用场景中一轮只需加载一份历史文档；instruction 中说明只调用一次。

## Migration Plan

1. 修复 `writing_state_data` bug（先行），确保新保存的文档有正确 `doc_name`
2. 新增工具并更新 instruction，不影响现有对话的运行
3. 无数据迁移，无前端协议变更
4. 回滚：删除两个新工具，恢复 `write_document` 的 `context` 优先逻辑，删除 `loaded_base_draft` 字段

## Open Questions

- `list_saved_documents` 返回的文档列表是否需要按 doc_type 分组展示，还是平铺？（当前设计：LLM 传 `doc_type` 过滤，平铺返回）
- `module_name` 参数是否应改为可选参数（`write_document` 无模块名的纯对话场景）？（当前设计：可选，为空时不写入 writing_state）
