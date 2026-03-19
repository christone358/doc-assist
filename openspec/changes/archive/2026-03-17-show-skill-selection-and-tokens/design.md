## Context

当前 Agent 的流式对话流程：`stream_message()` 通过 WebSocket 向前端发送 `status`、`skill_start`、`text`、`skill_end`、`done` 等类型的 chunk。前端接收并渲染文本内容和进度步骤。

两个现状缺口：
1. **Skill 选择不透明**：`skill_start` chunk 已经携带 `skill_id` 和 `content`，前端也已作为 status step 展示，但展示方式与普通状态步骤相同，缺乏视觉区分度，且未显示匹配得分/原因
2. **Token 用量不可见**：`LLMService.complete()` 和 `stream_complete()` 仅返回文本内容，未返回 token 用量；即使后端采集了也没有传到前端

## Goals / Non-Goals

**Goals:**
- LLM 服务调用后采集并返回 token 用量（prompt_tokens、completion_tokens、total_tokens）
- `_select_skill()` 在选择 Skill 时同时生成人类可读的**选择推理字符串**，记录每个命中的匹配信号
- `skill_start` chunk 携带 `reason` 字段，在流式输出开始前实时展示给用户
- `stream_message()` 在 `done` chunk 中附带 `skill_id`、`skill_name`、`skill_reason` 和 token 用量
- 前端在每条 assistant 消息底部展示：Skill 名称 badge + 选择理由文本 + token 统计
- `ConversationRound.llm_info` 中持久化保存 token 数据和 skill_reason（字段已存在）

**Non-Goals:**
- 不展示原始匹配分数数字（对用户无实用价值，仅展示语义化理由）
- 不用 LLM 二次生成推理（零额外 token 消耗，从分数信号直接推导）
- 不累计会话总 token（仅显示每轮）
- 不支持逐 token 统计流式过程（仅最终统计）
- 不修改 LLM 模型切换逻辑

## Decisions

### 1. Token 数据采集位置

**决策**：在 `LLMService` 中采集，通过新的数据结构 `LLMUsage` 返回给调用方。

`complete()` 返回 `(text, usage)`；`stream_complete()` 在 streaming 结束后返回 usage（通过最终 chunk 携带）。

DeepSeek/QWen 使用 OpenAI 兼容接口，`response.usage` 包含 `prompt_tokens`、`completion_tokens`、`total_tokens`。

**备选方案**：在 `agent/core.py` 中解析 API 响应 —— 排除，因为 core 不应直接操作 LLM 响应对象。

### 2. token 数据传递路径

**决策**：`done` chunk 中附带元数据：

```json
{
  "type": "done",
  "skill_id": "write-requirements",
  "skill_name": "需求规格文档编写",
  "skill_reason": "文档类型「requirements」吻合；关键词「需求」命中能力范围",
  "usage": {"prompt_tokens": 1234, "completion_tokens": 567, "total_tokens": 1801}
}
```

`skill_start` chunk 同样携带 `reason` 字段，使进度步骤中即可显示理由：

```json
{
  "type": "skill_start",
  "skill_id": "write-requirements",
  "content": "使用 Skill: 需求规格文档编写",
  "reason": "文档类型「requirements」吻合；关键词「需求」命中能力范围"
}
```

这样前端只需处理 `done` 事件一次，无需维护额外状态。

**备选方案**：发送独立的 `usage` 类型 chunk —— 排除，增加前端状态管理复杂度。

### 3. 流式接口的 token 返回

**决策**：`stream_complete()` 改为 `AsyncIterator[str | dict]`，最后一个元素为 usage dict（`{"usage": {...}}`），其余为文本字符串。`agent/core.py` 的 `_stream_llm_response()` 负责识别并透传。

**备选方案**：流式结束后单独调一次 API 查 usage —— 排除，浪费额外 API 调用。

### 4. 前端展示位置

**决策**：在 assistant 消息气泡内容下方增加 meta bar，仅在 `done` 后渲染（streaming 中不显示）。

格式：
```
[🎯 write-requirements · 需求规格文档编写]
理由：文档类型「requirements」吻合；关键词「需求」命中能力范围
📊 1234 + 567 = 1801 tokens
```

Skill 名称用 badge 样式，理由用小字展示在 badge 下方，token 用灰色小字。

### 5. 选择推理的生成方式

**决策**：在 `_select_skill()` 中将现有的评分信号转换为中文理由列表，无需额外 LLM 调用。

信号来源及对应描述：
- doc_type 精确匹配 → `"文档类型「{doc_type}」与请求吻合"`
- 能力关键词命中 → `"关键词「{cap}」命中能力范围"`
- Skill 名称关键词命中 → `"Skill 名称「{name_part}」与请求相关"`
- 标签命中 → `"标签「{tag}」与请求匹配"`

最终 reason 字符串：`"；".join(命中的理由列表)`，如 `"文档类型「design」吻合；关键词「设计方案」命中能力范围"`。

`_select_skill()` 返回值扩展为 `(skill, reason)`。

**备选方案**：用 LLM 生成自然语言推理 —— 排除，引入额外延迟和 token 消耗，对 MVP 不必要。

**备选方案**：直接显示分数数字（如"得分：15"）—— 排除，对用户不友好，语义不明确。

## Risks / Trade-offs

- **DeepSeek/QWen 流式 usage**：部分 provider 在 stream 模式下不在最后一个 chunk 返回 usage，或返回 `usage: null`。需要在 `stream_complete()` 中兼容处理，若无 usage 则返回 None，前端不显示 token 信息
- **改动 LLMService 接口**：`complete()` 签名变化（返回 tuple），需同步修改 `agent/core.py` 中的调用方

## Migration Plan

1. 修改 `LLMService.complete()` → 返回 `(str, dict | None)`
2. 修改 `LLMService.stream_complete()` → 最后 yield 一个 `{"usage": {...}}` dict
3. 修改 `agent/core.py`：`_select_skill()` 返回 `(skill, reason)` 元组，reason 为中文理由字符串
4. 修改 `agent/core.py`：`stream_message()` 的 `skill_start` chunk 携带 `reason` 字段
5. 修改 `agent/core.py`：`_execute_with_llm()` 解包 tuple，`_stream_llm_response()` 透传 usage
6. 修改 `agent/core.py`：`stream_message()` 在 `done` chunk 中附带 `skill_id`、`skill_name`、`skill_reason`、`usage`
7. 修改 `main.py` WebSocket handler：从 `done` chunk 中提取并写入 `llm_info`（含 skill_reason）
8. 修改 `Chat.svelte`：渲染 meta bar（Skill badge + 理由文本 + token 统计）

无需数据迁移，历史对话仅 `llm_info: null`，前端兼容处理即可。

## Open Questions

- 部分模型在 stream 模式下返回的 `usage` 字段结构可能不同，实现时需查阅具体 SDK 响应格式
