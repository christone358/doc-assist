## Context

当前 `runner_adapter.stream_message()` 在每一轮（每条用户消息）中执行如下流程：
1. `InMemorySessionService()` — 构造新的内存 session 服务
2. `build_document_agent(ctx, skills, has_draft)` — 重建 `LlmAgent` 实例
3. `Runner(agent, session_service)` — 构造新的 runner
4. `session_service.create_session(session_id=uuid...)` — 创建随机 session
5. `runner.run_async(new_message=...)` — 单轮运行，完成后所有状态丢弃

ADK `InMemorySessionService` 将 session 历史（events）保存在 Python 进程内存中，同一 session_id 在多次 `run_async` 调用间共享历史。现有问题是每轮都生成新的 `session_id`，因此历史无法跨轮复用。

**关于两个 LLM**：当前架构存在两个独立的 LLM 调用：
- **编排 LLM**：ADK `LlmAgent` 内部的 ReAct 循环，负责意图理解、工具调度、事实加载决策，运行在 ADK session 内
- **写作 LLM**：`write_document` 工具内部通过 `litellm.acompletion()` 发起的独立调用，负责生成文档正文，不在 ADK session 内，ADK 历史对它不可见

两个 LLM 的上下文管理策略必须独立设计。

## Goals / Non-Goals

**Goals:**
- 同一 conversation 的多轮消息复用同一 ADK session，使编排 LLM 能看到跨轮的事件历史
- 编排 LLM 通过 session 历史感知已加载的事实，实现跨轮渐进式披露（不重复加载已有数据）
- 写作 LLM 仍基于当轮收集的事实 + 当前草稿构建上下文，保持每轮写作上下文干净
- 启用三层压缩策略：以事实加载即时截断为核心，轮次触发压缩为补充，强制裁剪为兜底，防止编排 LLM context 超限
- conversation 删除时同步清理对应 ADK session，避免内存泄漏

**Non-Goals:**
- 跨进程/跨实例共享 session（不引入 Redis 或外部 session store）
- 修改 `ConversationManager` 的数据库持久化逻辑
- 修改前端 WebSocket 协议

## Decisions

### 决策 1：Session 注册表替换 per-round 构建

**方案**：在 `runner_adapter.py` 中维护进程级 `_session_registry: Dict[str, SessionEntry]`，key 为 `conversation_id`，value 为 `SessionEntry(session_service, runner, session_id, agent)`。

`stream_message()` 首次调用时创建并注册；后续调用时直接复用，仅向已有 session 追加新消息。

**备选**：每轮重建 agent 但共享 session_service。
**否决原因**：`Runner` 绑定了 `agent` 引用，如果 agent 重建则 runner 也需重建。session_service 单独共享会导致 runner/agent/session_service 三者生命周期不一致，增加管理复杂度。

### 决策 2：两个 LLM 的上下文管理分离

**编排 LLM（ADK session）**：
- 跨轮上下文通过 ADK session 历史自然传递
- session 历史中已有 `get_fact_overview`/`get_fact_detail` 的调用记录和结果，编排 LLM 在后续轮次能直接感知，无需重新加载
- DocumentAgent instruction 中明确：历史中已加载过的数据不重复请求，这是渐进式披露在跨轮场景的体现
- 历史过长时通过 Events Compaction 压缩

**写作 LLM（write_document 内部）**：
- context 由四部分构成：**skill 写作规范**（system prompt，从 skill.md 读取）、**用户意图**（`user_intent`，编排 LLM 传入）、**当轮事实**（`collected_facts_parts`，新建场景）、**当前草稿**（`context` 参数，修改场景）
- 新建场景：`collected_facts_parts` 有内容，`context` 为空
- 修改场景：`collected_facts_parts` 可能为空，`context` 为草稿全文，是写作的主要输入
- `collected_facts_parts` 保持 per-round 语义，每轮开始时清空，只积累当轮工具调用的结果
- 草稿通过 session.state 持久化，`get_current_draft` 工具读取后以 `context` 参数形式传入

**关键原则**：写作 LLM 的 context 只包含当轮相关信息，不因 session 复用而叠加历史数据。

### 决策 3：`collected_facts_parts` 保持 per-round，不迁移至 session.state

`collected_facts_parts` 是写作 LLM 的当轮工作区，语义为"本轮 write_document 调用需要注入的事实"。

若迁移至 session.state 跨轮累积，写作 LLM 每轮都会注入所有历史轮次的原始事实，context 无限膨胀，违背上下文干净的目标。

跨轮的事实感知由编排 LLM 通过 session 历史获得，不需要再次向写作 LLM 注入。

`collected_facts_parts` 继续保留在 per-round 的 `ConversationContext` 中，不做迁移。

### 决策 4：session.state 存储草稿和 skill 选择

写作完成后将草稿内容和 skill 选择写入 session.state：
```python
tool_context.state["draft_content"] = full_text
tool_context.state["selected_skill_id"] = skill_id
```
`get_current_draft` 优先从 session.state 读取，回退到 ConversationManager。

`write_document` 工具的 ADK 返回值为摘要字符串（如"文档已生成，共 N 字"），完整草稿只写入 session.state，不进入 session 历史，避免历史因草稿全文迅速膨胀。`done` 事件需从 session.state 读取 `draft_content` 传给 main.py 用于 ConversationManager 持久化。

### 决策 5：三层压缩策略，以即时截断为核心

单一 token 阈值触发压缩存在根本缺陷：到触发时历史中已积累大量原始事实文本，每轮都重复传给编排 LLM，token 浪费早已发生。更有效的方式是在内容写入历史时就控制大小，而非事后压缩。

**第一层：即时截断（最重要）**
事实加载工具（`get_fact_overview`、`get_fact_detail`）写入 ADK session 历史的内容只保留摘要（如"已加载模块清单：A、B、C 等5个模块"）。原始全文只进 `collected_facts_parts`，供当轮写作 LLM 使用，不进历史。事实加载是 token 消耗的最大来源，在源头截断后后续轮次的 context 自然干净。

**第二层：轮次触发压缩（5-8 轮）**
每轮 `run_async()` 前检查累计轮次，超过 5-8 轮时对早期轮次事件进行摘要压缩，保留决策结论和用户澄清，丢弃中间推理细节。经过第一层截断后历史内容已精简，token 波动小，轮次是更稳定的触发指标。

**第三层：强制裁剪兜底（15 轮）**
超过 15 轮时无论如何只保留最近 8 轮完整事件，防止极端情况下历史无限增长。

若 ADK 原生不支持压缩，第二层降级为直接裁剪（丢弃早期事件），第三层不变。

## Risks / Trade-offs

**[风险] write_document 返回值写入 session 历史导致 context 膨胀**：ADK 默认将工具返回值作为事件写入历史，草稿全文会撑大 context。
→ **已在决策 4 解决**：`write_document` 返回摘要字符串，完整草稿只写入 session.state。

**[风险] 内存增长**：session 长期驻留内存，多对话并发时内存压力上升。
→ 缓解：设置 session TTL（最后活跃时间 + 4 小时自动清理），conversation 关闭时主动清理。

**[风险] ADK Events Compaction API 不稳定**：当前 ADK 为早期版本，compaction 接口可能变更。
→ 缓解：将压缩逻辑封装为独立函数，隔离 ADK 版本依赖；提供手动裁剪降级路径，确保 ADK 不支持时仍可运行。

**[风险] 进程重启导致 session 丢失**：InMemorySessionService 重启后清空，用户感知到"遗忘"。
→ 接受：本方案目标是进程内多轮记忆，跨进程持久化属于 Non-Goal，可在后续引入 DatabaseSessionService。

**[Trade-off] DocumentAgent 实例长期持有**：agent 对象不再每轮重建，skills_map 在 agent 构建时快照。skills 目录变更（热重载）后已有 session 的 agent 不会自动更新。
→ 缓解：conversation 重新加载（切换对话）时强制重建 session（`get_or_create_session()` 支持 `force_rebuild` 参数）。此逻辑需在实现阶段补充对应任务。

## Migration Plan

1. 新代码上线后，已有 conversation 的第一轮消息触发新 session 创建，行为与现有一致
2. 后续轮次复用 session，自动获得跨轮记忆能力
3. 无需数据迁移，无前端协议变更
4. 回滚：删除 `_session_registry` 逻辑，恢复 per-round 构建，行为退回现状

## Open Questions

- ADK 当前版本（已安装）是否已支持 Events Compaction？需要在实现阶段确认 API。
- `session.state` 写入是否需要通过 ADK `ToolContext`，还是可以直接操作 `session` 对象？需要查阅 ADK 文档确认。
