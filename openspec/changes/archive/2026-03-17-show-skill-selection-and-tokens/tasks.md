## 1. LLM Service — 返回 token 用量

- [x] 1.1 在 `backend/llm/service.py` 中修改 `complete()` 方法，返回 `(response_text, usage_dict | None)` 元组；usage_dict 格式为 `{"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}`
- [x] 1.2 在 `backend/llm/service.py` 中修改 `stream_complete()` 方法，在所有文本 chunk 输出完毕后，最后 yield 一个 dict `{"usage": {...}}` 表示 token 用量；若 provider 不支持则 yield `{"usage": None}`

## 2. Agent Core — 生成 Skill 选择推理并透传元数据

- [x] 2.1 在 `backend/agent/core.py` 的 `_select_skill()` 中，在评分循环中收集每个命中信号的中文描述（doc_type 匹配 → `"文档类型「{doc_type}」吻合"`；能力关键词命中 → `"关键词「{cap}」命中能力范围"`；Skill 名称命中 → `"Skill 名称「{part}」与请求相关"`；标签命中 → `"标签「{tag}」与请求匹配"`），将理由列表用`"；"`拼接为 reason 字符串；返回值改为 `(skill | None, reason | None)`
- [x] 2.2 在 `backend/agent/core.py` 的 `stream_message()` 中，将 `_select_skill()` 的调用改为解包 `(selected_skill, skill_reason)`；发出 `skill_start` chunk 时附加 `"reason": skill_reason` 字段
- [x] 2.3 在 `backend/agent/core.py` 的 `_execute_with_llm()` 中解包 `complete()` 返回的 `(text, usage)` 元组，将 usage 存入返回值（扩展为 `(text, documents, usage)`）
- [x] 2.4 在 `backend/agent/core.py` 的 `_stream_llm_response()` 中识别最后的 `{"usage": ...}` dict chunk，作为 usage 数据收集，不作为文本 yield 给上层
- [x] 2.5 在 `backend/agent/core.py` 的 `stream_message()` 中，在发出 `done` chunk 时附带 `skill_id`、`skill_name`、`skill_reason`、`usage` 字段

## 3. WebSocket Handler — 写入 llm_info

- [x] 3.1 在 `backend/main.py` 的 WebSocket handler 中，从 `done` chunk 提取 `skill_id`、`skill_name`、`skill_reason`、`usage`，将 usage 和 skill_reason 合并写入 `add_round()` 的 `llm_info` 参数（格式：`{"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ..., "skill_reason": "..."}`）

## 4. 前端 — 渲染 meta bar（含选择理由）

- [x] 4.1 在 `frontend/src/lib/components/Chat.svelte` 的 `handleWSMessage()` 中，处理 `skill_start` chunk 时将 `reason` 附加到 statusSteps 步骤文本中（格式：`"使用 Skill: {name} · {reason}"`）
- [x] 4.2 在 `Chat.svelte` 的 `handleWSMessage()` 中，处理 `done` chunk 时提取 `skill_id`、`skill_name`、`skill_reason`、`usage`，更新 `currentAssistantMsg` 对应字段（`metaSkillId`、`metaSkillName`、`metaSkillReason`、`metaUsage`）
- [x] 4.3 在 `Chat.svelte` 的消息模板中，为 assistant 消息在内容下方增加 meta bar：Skill badge（显示 skill_name）+ 理由文本（显示 skill_reason，灰色小字）+ token 统计（`prompt + completion = total tokens`）；meta bar 仅在 done 后渲染
- [x] 4.4 在 `Chat.svelte` 的 `switchConversation()` 中，将历史轮次的 `skill_invoked`、`llm_info.skill_reason` 和 `llm_info`（token 字段）映射到消息对象对应字段，使历史消息也能渲染完整 meta bar
- [x] 4.5 在 `Chat.svelte` 的 `<style>` 中添加 meta bar 的 CSS 样式：Skill badge（蓝色小背景）、理由文字（`font-size: 11px`、`color: var(--text-muted)`、`font-style: italic`）、token 统计（灰色小字）
