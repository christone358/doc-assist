## Why

当前架构中，编排 LLM 承担了两件本不属于它的事：决定加载哪些事实上下文、以什么顺序调用工具。这让 skill.md 里精心描述的"工作原理"和"上下文需求"成了摆设——编排 LLM 凭自己的通用推理决定加载什么，而不是遵循 Skill 的声明，导致加载决策不稳定、Skill 作者无法通过 skill.md 控制执行行为。

## What Changes

- **新增** `execute_skill(skill_id, module_name, user_intent)` 工具：封装 Skill 完整执行流程——读取 skill.md 的 `requires` 字段、按需加载对应事实上下文、调用写作 LLM 生成文档；原有 `write_document` 工具废弃
- **新增** skill.md frontmatter `requires` 字段：Skill 作者显式声明所需的上下文类型列表（如 `usecases`、`classes`、`interfaces`、`prototypes`），`execute_skill` 据此驱动加载，无需 LLM 推断
- **修改** `document_agent` instruction：大幅简化，编排层只负责三件事——判断意图（新建 vs 修改）、定位模块、选择 Skill；事实加载工作流描述全部移除
- **修改** 修改场景工具链：草稿来源决策（`get_current_draft` / `list_saved_documents` + `load_saved_document`）仍由编排层负责，确定草稿来源后交由 `execute_skill` 执行
- **移除** `get_fact_overview`、`get_fact_detail` 从编排层工具列表（它们成为 `execute_skill` 内部实现细节，不暴露给编排 LLM）
- **更新** 三个内置 skill.md（write-requirements、write-design、write-test-plan）补充 `requires` 字段

## Capabilities

### New Capabilities

- `skill-execution-workflow`：execute_skill 工具的执行协议——读取 skill requires 声明、按序加载事实上下文、衔接草稿（loaded_base_draft）、调用写作 LLM；整个流程由代码驱动，不依赖编排 LLM 的中间推理

### Modified Capabilities

- `agent-core`：编排层职责收窄为「意图判断 + 模块定位 + Skill 选择 + 草稿来源决策」，不再包含事实加载工作流；工具列表移除 get_fact_overview / get_fact_detail，新增 execute_skill
- `document-skills`：skill.md frontmatter 新增 `requires` 字段（上下文类型列表），成为 execute_skill 的执行输入；Skill 作者通过此字段控制上下文加载行为

## Impact

- `backend/agent/adk/execute_skill_tool.py` — 新增，实现 execute_skill 工具
- `backend/agent/adk/write_document_tool.py` — 改造为内部函数（不再作为 ADK 工具注册），由 execute_skill 内部调用
- `backend/agent/adk/fact_tools.py` — 改造为内部函数，由 execute_skill 内部调用，不再注册到编排 agent
- `backend/agent/adk/document_agent.py` — 工具列表和 instruction 大幅简化
- `skills/*/skill.md` — 三个内置 skill 补充 `requires` 字段
- `backend/agent/models.py` — SkillInfo 新增 `requires: List[str]` 字段（skill 加载时从 frontmatter 解析）
