## ADDED Requirements

### Requirement: execute_skill 触发 Skill Sub-agent 执行完整写作流程

系统 SHALL 提供 `execute_skill(skill_id, user_intent)` 工具。该工具内部动态创建并运行一个 Skill Sub-agent（LlmAgent），以 skill.md 正文为 instruction，通过自身 ReAct 循环完成事实加载和写作，主 Agent 不参与这些步骤。

#### Scenario: 编排 LLM 传入结构化 user_intent

- **WHEN** 主 Agent 调用 `execute_skill` 时
- **THEN** `user_intent` SHALL 为主 Agent 提炼的结构化自然语言描述，包含写作对象名称、文档类型、写作重点等已理解信息（不得直接透传用户原文）；示例："为认证模块编写需求规格说明书，重点覆盖用户登录和权限验证两个用例"

#### Scenario: Skill Sub-agent 以 skill.md 正文为 instruction

- **WHEN** `execute_skill` 创建 Skill Sub-agent 时
- **THEN** Sub-agent 的 instruction SHALL 由以下两部分组成：
  1. skill.md 正文（包含写作规范、上下文需求描述、格式要求等）
  2. 固定执行规范（工具说明、写作完成条件、不得虚构事实等通用约束）

#### Scenario: Skill Sub-agent 通过 ReAct 自主推理完成全部写作任务

- **WHEN** Skill Sub-agent 开始执行时
- **THEN** Sub-agent SHALL 通过自身 ReAct 循环自主完成以下任务集合（顺序由 Sub-agent 推理决定，无固定执行顺序）：
  - 从 `user_intent` 识别写作对象，在事实库中定位；若无法定位则调用 `ask_user` 澄清或终止
  - 理解 skill.md 中描述的上下文需求；若描述不足以判断需要哪些事实，调用 `ask_user` 向用户确认，除非用户明确要求不依据事实信息生成
  - 决策草稿来源：检查对话内草稿（`get_current_draft`）或历史版本（`list_saved_documents` / `load_saved_document`）
  - 按需调用 `get_fact_detail` 加载具体事实，可多轮、有条件执行
  - 上下文充分后调用 `write_document` 完成写作并返回摘要

#### Scenario: Sub-agent 工具列表

- **WHEN** `execute_skill` 创建 Skill Sub-agent 时
- **THEN** Sub-agent 的工具列表 SHALL 包含：
  - **通用工具**：`get_current_draft`、`list_saved_documents`、`load_saved_document`、`get_fact_overview`、`get_fact_detail`、`write_document`（内部版本）、`ask_user`
  - **Skill 专属工具**：通过 LLM 从 skill.md 正文中提取工具文件路径（相对于 skill 目录），加载对应模块并注册；skill.md 中未声明工具时仅使用通用工具集

#### Scenario: Sub-agent 在执行过程中向用户提问

- **WHEN** Sub-agent 在 ReAct 循环中遇到无法自行决策的情况时（如写作对象在事实库中有多个匹配、历史草稿版本需用户确认、写作细节超出事实库范围）
- **THEN** Sub-agent SHALL 调用 `ask_user` 向用户提问，获得澄清后继续推理；Sub-agent 的 ask_user 调用与主 Agent 的 ask_user 调用使用相同的 WebSocket 通道，对用户呈现方式一致

#### Scenario: Sub-agent 与主 Agent 共享 ConversationContext

- **WHEN** Sub-agent 工具写入事实或读取草稿时
- **THEN** Sub-agent 工具 SHALL 读写与主 Agent 相同的 `ConversationContext`（ctx）实例；`ctx.collected_facts_parts`、`ctx.loaded_base_draft` 等字段在两层 Agent 间共享

#### Scenario: 自动衔接已加载草稿

- **WHEN** Sub-agent 通过 `get_current_draft` 或 `load_saved_document` 加载草稿后调用 `write_document` 时
- **THEN** 写作上下文 SHALL 包含草稿内容（修改场景）；未加载任何草稿时为纯新建场景

#### Scenario: 写作完成后写入 session.state

- **WHEN** Sub-agent 内部写作 LLM 完成流式输出后
- **THEN** 工具 SHALL 将 `draft_content`、`selected_skill_id`、`doc_type`、`module_name` 写入 `tool_context.state`；行为与被替换的 `write_document` 完全一致

#### Scenario: execute_skill 返回摘要给主 Agent

- **WHEN** Skill Sub-agent 完成执行时
- **THEN** `execute_skill` SHALL 将 Sub-agent 返回的摘要字符串写入主 Agent 的 session 历史（如"文档已生成，共 N 字（skill: write-requirements）"）；完整草稿只在 session.state 中
