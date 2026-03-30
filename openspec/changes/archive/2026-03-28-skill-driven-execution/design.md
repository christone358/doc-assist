## Context

当前 `document_agent.py` 是一个单层 ReAct 循环：编排 LLM 同时负责意图理解、Skill 选择、事实加载决策、工具调用编排和最终写作触发。`write_document` 工具只是"调用写作 LLM 的薄层"，Skill 在其中仅提供写作格式规范，不参与上下文加载。

skill.md 的"工作原理"章节用自然语言描述了 Skill 需要哪些上下文，但编排 LLM 看不到这段描述（正文在 `write_document` 被调用时才从磁盘读取，只传给写作 LLM）。加载决策完全依赖编排 LLM 的通用推理，与 Skill 的实际声明脱节。

本 change 引入两层 Agent 架构：主 Agent 负责意图路由，Skill Sub-agent 负责执行能力——读取 skill.md 作为自己的 instruction，自主推理决定加载哪些事实，完成写作。

## Goals / Non-Goals

**Goals:**
- 主 Agent（document_agent）只做意图判断和 Skill 选择，工具列表缩减为 `execute_skill` 和 `ask_user`
- 引入 Skill Sub-agent：以 skill.md 正文为 instruction，通过自身 ReAct 循环完成草稿来源决策、事实加载、写作
- 草稿来源决策（get_current_draft / list_saved_documents / load_saved_document）迁入 Sub-agent，与事实加载决策统一为完整的写作推理链
- 主 Agent 将编排 LLM 已理解的写作意图提炼为 `user_intent` 传给 Sub-agent，Sub-agent 自行完成所有后续推理
- skill.md 自然语言描述即为 Sub-agent 的执行规范，无需额外的机器可读字段
- 形成"主 Agent 路由意图 + 多个 Skill Sub-agent 提供专项能力"的可扩展模式

**Non-Goals:**
- 不改变写作 LLM 的调用方式（litellm 流式输出不变）
- 不改变文档保存、版本管理、WebSocket 协议
- 不在 skill.md 中新增任何结构化字段

## Decisions

### 决策 1：Skill Sub-agent 以 skill.md 正文为 instruction，运行独立 ReAct 循环

`execute_skill` 工具内部动态创建一个 `LlmAgent`（Skill Sub-agent）：

- **instruction**：skill.md 正文 + 固定执行规范（工具说明、写作完成条件、session.state 写入要求）
- **工具列表**：`get_fact_overview`、`get_fact_detail`、`write_document`（内部版本）
- **输入**：`user_intent`（由主 Agent 提炼，含写作对象名称和写作意图）
- **共享状态**：与主 Agent 共用同一个 `ConversationContext`（ctx），Sub-agent 工具可读写 `ctx.collected_facts_parts`、`ctx.loaded_base_draft` 等字段

Sub-agent 通过 ReAct 自主推理：
1. 读取 skill.md instruction，理解写作该类型文档需要哪些事实
2. 从 `user_intent` 识别写作对象，调用 `get_fact_overview` 定位
3. 决策草稿来源：调用 `get_current_draft` 检查对话内草稿；若无则调用 `list_saved_documents` 查询历史版本，按需调用 `load_saved_document` 加载
4. 按需调用 `get_fact_detail` 加载具体事实（可多轮、有条件）
5. 判断上下文充分后调用 `write_document` 完成写作
6. 返回摘要字符串给主 Agent

### 决策 2：`execute_skill` 签名为 (skill_id, user_intent)，user_intent 由主 Agent 提炼

主 Agent 在调用 `execute_skill` 前，将其已理解的写作对象、文档类型、写作重点提炼为结构化自然语言赋给 `user_intent`，例如：

> "为认证模块编写需求规格说明书，重点覆盖用户登录和权限验证两个用例"

不设独立的 `subject`、`module_name` 参数。Sub-agent 内部从 `user_intent` 识别写作对象，适配不同粒度的写作场景（模块/子系统/功能集合）。

### 决策 3：`get_fact_overview`、`get_fact_detail`、草稿相关工具全部迁入 Sub-agent

`get_fact_overview`、`get_fact_detail`、`get_current_draft`、`list_saved_documents`、`load_saved_document` 均从主 Agent 工具列表移除，成为 Skill Sub-agent 的专属工具。草稿来源决策与事实加载决策属于同一推理链，统一由 Sub-agent 负责。

主 Agent 工具列表缩减为：`execute_skill`、`ask_user`。

**备选：** 保留草稿相关工具在主 Agent，仅移除事实加载工具。**否决原因：** 草稿来源决策（"是否基于历史版本修改"）是写作前的上下文准备，与"加载哪些事实"是同一类推理，都属于 Sub-agent 的写作推理职责；主 Agent 承担草稿决策会导致职责边界不一致，且 Sub-agent 已有完整工具集，无需主 Agent 介入。

### 决策 4：Skill 专属工具路径在 skill.md 正文中声明，创建 Sub-agent 时按需加载

Skill 工具文件可放置于 skill 目录下任意位置，无目录结构约定。`execute_skill` 在创建 Sub-agent 时，读取 skill.md 正文，通过 LLM 推断提取所有工具文件路径（相对于 skill 目录），动态 import 对应模块，将暴露的工具函数追加到 Sub-agent 工具列表。skill.md 中未声明工具时，Sub-agent 仅使用通用工具集。

工具文件路径提取与上下文需求推断复用同一次 LLM 调用（合并 prompt），避免额外延迟。

**备选：** 约定固定目录名（如 `tools/`），自动扫描。**否决原因：** 固定目录名是不必要的约束，Skill 作者可能有自己的组织方式；路径在 skill.md 中声明与整体"自然语言驱动"设计原则一致，且扫描发现无法知道哪些文件是工具、哪些是辅助模块。

### 决策 5：`write_document` 在 Sub-agent 中作为内部工具，不再作为主 Agent 工具注册

将现有 `write_document_tool.py` 核心逻辑保留，作为 Sub-agent 专属工具注册。主 Agent 不再持有 `write_document`、`get_current_draft`、`list_saved_documents`、`load_saved_document` 等任何写作相关工具。

## Risks / Trade-offs

**[风险] Sub-agent ReAct 步数不可控**：Sub-agent 可能做出冗余的工具调用。
→ skill.md instruction 中明确写作完成条件和工具使用原则，限制不必要的重复调用。

**[风险] 写作对象提取失败**：user_intent 描述不清晰时，Sub-agent 可能无法定位写作对象。
→ Sub-agent 定位失败时返回说明性文字并终止；主 Agent instruction 要求 user_intent 必须包含写作对象名称，不明确时先调用 ask_user 澄清。

**[风险] Sub-agent 调用增加延迟**：Sub-agent 初始化和多轮 ReAct 引入额外延迟。
→ Sub-agent 动态创建开销极小（LlmAgent 是轻量对象）；ReAct 步数通常 2-4 步，整体延迟与原方案相当甚至更少（消除了冗余的推断调用）。

**[风险] 多轮对话上下文断裂**：Sub-agent 每次都是全新实例，不知道之前轮次的写作历史。
→ execute_skill 创建 Sub-agent 时注入两类上下文：ctx 状态摘要（已加载事实、已有草稿）+ 主 Agent 相关历史摘要；ConversationContext 作为跨轮持久状态载体，保证事实和草稿数据在轮次间连续。

**[风险] 长对话 token 超限**：主 Agent session 历史或 Sub-agent ReAct 历史过长导致超出模型上下文窗口。
→ 主 Agent session 设置 token 阈值，超限时对最早轮次做 LLM 摘要压缩；Sub-agent ReAct 超过步数阈值时对已完成步骤做内联压缩。

**[Trade-off] Sub-agent 行为对主 Agent 不透明**：
→ Sub-agent 内部向 WebSocket 发送 status 子事件，用户侧可观测性不变；主 Agent 收到 Sub-agent 返回的摘要字符串写入 session 历史。

## Session 架构决策

### 决策 S1：ConversationContext 是跨轮、跨 Agent 的唯一共享状态载体

主 Agent 和所有 Sub-agent 实例共享同一个 ctx 实例。ctx 持有的事实数据（collected_facts_parts）、草稿（loaded_base_draft）、文档名（loaded_base_doc_name）、上次执行摘要（last_skill_execution_summary）在轮次之间持久保留。每轮开始时清空 collected_facts_parts，避免上轮事实污染本轮。

### 决策 S2：Sub-agent 使用独立临时 session，创建时注入上下文

Sub-agent 每次创建时使用独立 session_id，ReAct 历史仅存活于本次 execute_skill 调用，执行完销毁。为弥补上下文断层，execute_skill 在构造 Sub-agent 初始输入时注入：ctx 状态摘要 + 主 Agent session 中与本次任务相关的历史摘要。

**备选：** Sub-agent 复用主 Agent session，追加 ReAct 历史。**否决原因：** Sub-agent 的工具调用历史（大量事实加载返回）会极大膨胀主 Agent session，造成主 Agent 后续轮次 token 压力；独立 session + 摘要注入是更清洁的隔离方案。

### 决策 S3：两层压缩策略

- **主 Agent session**：token 超阈值时对最早若干轮做 LLM 摘要压缩，近期轮次保持完整
- **Sub-agent ReAct**：步数超阈值时对已完成步骤做内联压缩（工具调用+返回对 → 一行摘要），正在进行的步骤和最近步骤保持完整

## Migration Plan

1. 新增 `execute_skill_tool.py`：实现 Sub-agent 创建逻辑，内部复用现有 fact_tools 和 write_document 写作逻辑
2. 更新 `document_agent.py`：替换工具列表，简化 instruction
3. 将 `write_document` 从主 Agent 工具降级为 Sub-agent 专属工具
4. 回滚方案：恢复旧工具列表，`write_document` 重新注册为主 Agent 工具，删除 `execute_skill_tool.py`
