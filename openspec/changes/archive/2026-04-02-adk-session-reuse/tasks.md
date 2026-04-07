## 1. 前置调研

- [x] 1.1 确认当前安装的 google-adk 版本是否支持 Events Compaction API，记录可用接口
- [x] 1.2 确认 ADK session.state 写入方式（通过 ToolContext 还是直接操作 session 对象），记录正确 API
- [x] 1.3 确认 ADK 工具返回值是否必须写入 session 历史，以及是否可以截断返回值（返回摘要而非全文）

## 2. Session 注册表

- [x] 2.1 在 `runner_adapter.py` 中定义 `SessionEntry` dataclass，持有 `session_service`、`runner`、`session_id`、`agent`、`last_active_at`
- [x] 2.2 创建进程级 `_session_registry: Dict[str, SessionEntry]` 及相关操作函数：`get_or_create_session()`、`remove_session()`、`cleanup_expired_sessions()`
- [x] 2.3 `get_or_create_session()` 首次调用时构建 agent、session_service、runner，生成基于 conversation_id 的固定 session_id（如 `f"session_{conversation_id}"`）
- [x] 2.4 `stream_message()` 改为调用 `get_or_create_session()`，复用已有 session 追加新消息，不再每轮重建
- [x] 2.5 添加基于 TTL 的定期清理逻辑（在每次 `get_or_create_session()` 时懒清理过期 entry）

## 3. DocumentAgent instruction 强化渐进式披露

- [x] 3.1 在 `document_agent.py` 的 instruction 中补充跨轮决策原则：session 历史中已有的事实加载记录不重复调用，已有的用户澄清回答直接引用

## 4. ADK state 写作状态迁移

- [x] 4.1 修改 `write_document_tool.py`：写作完成后将 `draft_content` 和 `selected_skill_id` 写入 session.state；工具返回摘要字符串，不返回完整草稿（依赖 1.2 确认 session.state 写入 API）
- [x] 4.2 修改 `draft_tool.py`（`get_current_draft`）：优先从 session.state["draft_content"] 读取，回退到 ConversationManager（依赖 1.2 确认 session.state 读取 API）
- [x] 4.3 `runner_adapter.py` 中 `done` 事件：skill 信息从 session.state 读取；`draft_content` 从 session.state 读取后写入 done 事件，确保 main.py 能持久化到 ConversationManager（不能省略此字段）。若本轮未调用 write_document，state 中保留上一轮草稿，done 事件仍应携带该值（而非 null）；若 state 中无草稿（首轮纯问答），则 done 事件 draft_content 字段为 None，main.py 不执行写作持久化

## 5. 三层压缩策略

- [x] 5.1 修改 `fact_tools.py` 中 `create_fact_tools()` 的异步包装函数：工具向 ADK 历史返回的内容改为摘要字符串，原始全文仍写入 `ctx.collected_facts_parts`（即时截断，第一层）
- [x] 5.2 在 `runner_adapter.py` 中，每轮 `run_async()` 前检查累计轮次，超过阈值（默认 6 轮，常量 `COMPRESSION_ROUND_THRESHOLD = 6`）时触发压缩或裁剪早期事件（第二层，依赖 1.1 确认 Events Compaction 可用性）
- [x] 5.3 若 ADK 支持原生 Events Compaction（由 1.1 确认），配置保留策略（保留用户消息和澄清，丢弃中间推理）；否则直接裁剪丢弃早期事件
- [x] 5.4 强制裁剪兜底：超过 15 轮时无论如何只保留最近 8 轮完整事件（第三层）

## 6. Conversation 生命周期集成

- [x] 6.1 在 `main.py` 的 conversation 删除接口中，调用 `remove_session(conversation_id)` 清理 ADK session
- [x] 6.2 调研：确认前端在 conversation 列表切换时的行为（是否发送新消息、是否会误触发 session 重建）；记录结论
- [x] 6.3 实现：`get_or_create_session()` 支持 `force_rebuild: bool = False` 参数；conversation 切换（重新加载）时传入 `force_rebuild=True`，强制销毁旧 session entry 并重建，确保新加载的 skills 生效

## 7. 验证与核查

- [x] 7.1 验证 `stream_message()` 每轮创建新的 `ConversationContext`，确保 `collected_facts_parts` 每轮从空列表开始，session 复用不影响此行为；若不满足，则在 `stream_message()` 入口处确保每轮重新初始化 `ConversationContext`
- [x] 7.2 验证 `done` 事件中 `draft_content` 字段的存在性与正确性（有写作时为当轮草稿，无写作时为上一轮草稿或 None），以及 main.py ConversationManager 持久化逻辑在各场景下的行为正确；若不满足则按 task 4.3 的规则修正
