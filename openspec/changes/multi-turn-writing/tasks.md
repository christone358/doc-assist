## 1. 数据模型扩展

- [x] 1.1 在 `backend/agent/models.py` 中新增 `WritingState` Pydantic 模型，包含字段：module_id、module_name、skill_id、doc_type、draft_content、saved_version（可选）、saved_path（可选）
- [x] 1.2 在 `ConversationInfo` 中新增 `writing_state: Optional[WritingState] = None` 字段
- [x] 1.3 验证 ConversationInfo 序列化/反序列化时 writing_state 字段正确持久化到 conversation_log.json

## 2. 写作意图识别

- [x] 2.1 在 `backend/agent/core.py` 中新增 `_identify_writing_intent(message, writing_state) → str` 方法，返回 `modify` / `new_module`
- [x] 2.2 实现 modify 意图识别：当 writing_state 存在且消息为修改/补充类指令时返回 modify
- [x] 2.3 实现 new_module 意图识别：当消息中出现与当前模块不同的模块名或明确要写新文档时返回 new_module
- [x] 2.4 当 writing_state 为 None 时，`_identify_writing_intent` 直接返回 `new_module`（触发全量流程）
- [x] 2.5 「重新写」「从头开始」类指令统一识别为 `new_module`（允许多一次模块重新识别）

## 3. stream_message 流程重构

- [x] 3.1 在 `stream_message()` 开头读取对话的 writing_state
- [x] 3.2 当 writing_state 存在时，调用 `_identify_writing_intent()` 判断意图，并在 status step 中展示「当前写作目标：{模块名}（{草稿状态}）」
- [x] 3.3 实现 modify 轻量流程：跳过模块识别和项目事实加载，以 `writing_state.draft_content` 作为主上下文传入 LLM
- [x] 3.4 实现 new_module 全量流程：清空 writing_state，执行现有完整流程（模块识别 → 加载事实）
- [ ] 3.5 在全量流程定位到模块后，检查该模块是否存在已保存版本，若有则加载最新版作为 draft_content 初始值，并 yield status step 展示提示（可延迟：核心功能不依赖此项）

## 4. 写作状态维护

- [x] 4.1 文档生成完成后（done 事件前），更新 conversation.writing_state.draft_content 为本轮生成内容
- [x] 4.2 首次生成时设置 writing_state 的 module_id、module_name、skill_id、doc_type
- [x] 4.3 new_module 意图时清空 writing_state（设为 None）
- [x] 4.4 writing_state 变更后调用 conversation_manager 保存到磁盘

## 5. 草稿保存接口

- [x] 5.1 在后端新增 `POST /conversations/{id}/save-draft` API 端点
- [x] 5.2 实现保存逻辑：读取 writing_state.draft_content，按 `docs/[doc_type]/[module_name]/[date]/v{x}.md` 规则写入文件，版本号在已保存版本基础上递增
- [x] 5.3 保存成功后更新 writing_state.saved_version 和 writing_state.saved_path，持久化对话

## 6. done 事件扩展

- [x] 6.1 在后端 done 事件中新增 `has_draft: true` 字段，告知前端本轮生成了草稿文档

## 7. 前端快捷操作按钮

- [x] 7.1 在 `Chat.svelte` 的消息渲染中，当 `msg.hasDraft === true` 时在消息末尾渲染「💾 保存为正式版本」按钮
- [x] 7.2 按钮点击时调用 save-draft API，期间按钮显示加载状态
- [x] 7.3 保存成功后按钮更新为「✓ 已保存 v{x.y}」并显示文件路径，变为不可点击状态
- [x] 7.4 按钮与输入框完全独立，按钮操作不影响输入框可用状态
