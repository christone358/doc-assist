## Context

当前系统里，主 Agent（document_orchestrator）与 Skill Sub-agent 的协作链路仍然带有明显的“单体内部实现”特征：

- Orchestrator 的提示词中直接写死了可用工具和执行逻辑
- 主 Agent 通过 `execute_skill(...)` 触发子 Agent，但返回值仍然高度依赖自由文本摘要
- 资源访问逻辑、Skill 能力假设和执行链路理解混在 Orchestrator 的内部 prompt 与工具声明中
- 前端看到的执行过程仍然偏 status/text 片段，缺少稳定的“链路展示协议”

在前一个 change 中，MCP runtime 已经被规划为统一的资源访问层。但如果主子 Agent 的执行协议不跟着调整，系统会出现新的错配：

- Orchestrator 仍然按旧工具模型做推理，而不是按 MCP namespace / 工具分级做推理
- 主子 Agent 的职责边界仍然模糊，容易让主 Agent 重复做子 Agent 应做的事实加载
- 子 Agent 的完整执行历史容易泄漏回主 Agent，破坏上下文隔离
- 前端无法稳定展示“计划、调度、执行、结果”的完整链路

因此本变更的重点不是继续增加新工具，而是**重构主子 Agent 的协议层**，让 Orchestrator 真正适配新的 MCP 运行时模式。

## Goals / Non-Goals

**Goals:**

- 定义主 Agent 与 Skill Sub-agent 的结构化通信协议
- 让 Orchestrator 的提示词与工具声明适配 MCP 模式和工具分级
- 保持主 Agent 与子 Agent 的上下文隔离
- 为执行链路建立稳定的结构化展示模型
- 让 `execute_skill` 从“黑盒调用”演进为“结构化执行边界”
- 与公共工具集 / 内部工具集和 MCP runtime 的边界保持一致

**Non-Goals:**

- 不在本次变更中重新设计全部 MCP 工具本身
- 不在本次变更中把 Skill 调度也完全抽象成 remote MCP 能力
- 不要求前端一次实现完整可视化工作流编辑器
- 不暴露原始 chain-of-thought 给主 Agent 或最终用户

## Decisions

### Decision 1: 主子协作采用“薄 handoff + 薄结果 + 独立状态/事件通道”

主子 Agent 分离调用 LLM 的核心原则是：

- 主 Agent 保持调度上下文干净，不被子 Agent 的执行细节污染
- 子 Agent 保持执行上下文自治，自己决定资源读取、基线选择和工具调用路径
- 两者之间只共享继续协作所需的最小信息，而不是共享完整上下文或完整执行历史

因此，本次不把主子协作设计成“一个很厚的 SkillExecutionResult 对象承载一切”，而是拆成三条通道：

1. 委派 handoff（主 Agent → 子 Agent）
2. 执行结果（子 Agent → 主 Agent）
3. 状态补丁与执行事件（子 Agent / runtime → state & UI / log）

其中：

- handoff 只承载调度决定与连续性记忆，不承载大块资源正文
- result 只承载 Orchestrator 做后续决策真正需要的最小结果
- state patch 用于持久化领域状态，如写作型子 Agent 的草稿状态
- execution events 用于可观测性与展示，而不是回灌到主 Agent prompt

这样做的原因：

- 避免把子 Agent 的执行细节重新塞回主 Agent 上下文，破坏上下文隔离
- 保留当前“写作摘要回传 + 草稿状态写入 state”的正确演进方向
- 让未来新增的非写作型子 Agent 也能复用同一协作骨架，而不被写作领域字段绑死

备选方案：

- 继续依赖自由文本摘要：实现简单，但主 Agent 和 UI 仍然要猜文本
- 设计一个很厚的统一执行结果对象：表面结构化，但会把执行细节和领域状态重新耦合回主 Agent

### Decision 2: 主 Agent 只传递调度决定与连续性记忆，不替子 Agent 预判执行路径

主 Agent 是编排层，不是执行层。因此主 Agent 向子 Agent 的 handoff 保持最小化，原则上只包括：

- `skill_id`：调度决定，由主 Agent 负责
- `user_intent`：面向执行的任务说明，由主 Agent 提炼
- `last_round_summary`：上一轮执行留下的压缩摘要，用于跨轮延续
- `clarification_context`：已有澄清记录与已确认约束，避免重复提问

以下信息不应作为主 Agent 显式 handoff 的一部分：

- 当前是否有 draft
- draft 正文或历史文档正文
- 是否已有 saved version
- 本轮应优先加载哪个基线版本
- facts / docs / skill resources 的大块正文内容

这些信息属于执行期自治，应由子 Agent 通过会话状态与 MCP / 内部工具自行获取和判断。

这样做的原因：

- 保持 Orchestrator 以调度决策为中心，而不是替子 Agent 做执行期分支判断
- 避免把“当前恰好是写作型子 Agent 的需求”硬编码成所有未来子 Agent 的通用 handoff
- 让写作型子 Agent 与未来信息查询型子 Agent 共享同一委派骨架

### Decision 3: 主 Agent 与子 Agent 持有不同提示词和工具声明

MCP 模式下，主 Agent 和子 Agent 不能继续共享相似的工具世界观。

主 Agent 的提示词应强调：

- 意图识别
- 任务拆解
- Skill 选择
- 何时直接答复、何时调度 Skill
- 何时读取公共工具集（如 `facts.*` / `docs.*`）

子 Agent 的提示词应强调：

- 如何执行具体写作任务
- 如何在当前 Skill 范围内访问 `skill.*`
- 如何在执行中按需读取 facts / docs
- 如何在完成后返回结构化执行结果

主 Agent 的工具集应以：

- `execute_skill`
- 公共工具集
- 询问用户 / 对话状态工具

为主。

子 Agent 的工具集应以：

- 内部工具集
- 写作工具
- 必要的公共工具集

为主。

这样做的原因：

- 防止 Orchestrator 继续下沉到子 Agent 的执行细节
- 让子 Agent 真正承担专业执行职责
- 让提示词契约和工具契约一致，而不是互相打架

### Decision 3.1: Prompt 模板迁移为独立文档，代码只负责运行时插槽注入

当前主 Agent 和子 Agent 的 system prompt 大段内联在 Python 代码中，已经不只是“实现细节”，而是实际承担：

- 职责边界定义
- 工具分级约束
- 委派与澄清规则
- 主子协作契约说明

随着本次 change 需要频繁重写主子职责边界，如果继续将 prompt 维持为 Python 内联字符串，会带来几个问题：

- 难以与 OpenSpec 设计和需求逐条对照 review
- 提示词改动与运行时代码改动混在一起，降低可维护性
- 不利于后续为主 Agent / 子 Agent 分别维护独立模板，或增加模式化拼装

因此本次设计要求：

- 将主 Agent prompt 抽取为独立文本模板文件
- 将子 Agent 固定执行规范也抽取为独立文本模板文件
- 代码层只负责注入运行时变量，如技能列表、草稿状态提示、少量上下文插槽
- Skill 自身的 `SKILL.md` 正文仍可继续作为子 Agent 指令的一部分，但与系统级执行规范分层拼装

这样做的原因：

- 让提示词作为架构契约而不是代码常量被管理
- 降低主子 prompt 重构时的代码噪音
- 为未来引入更多非写作型子 Agent 复用同一模板管理方式打基础

### Decision 3.2: 宿主统一管理 MCP client 与 tool catalog，再为不同 Agent 生成工具视图

在 MCP 模式下，业界更常见的做法不是“让某个 agent 直接接入 MCP server”，而是：

- 宿主应用作为 MCP host
- 宿主为每个 MCP server 建立 client 连接
- 宿主完成 capability negotiation、tool discovery 和 schema 缓存
- 宿主维护内部 tool catalog
- 宿主再按 agent 角色投影出不同的 tool view

本项目应采用同样的模式：

- MCP runtime / remote server 负责提供标准工具能力
- 宿主运行时负责管理 MCP client 生命周期、工具发现、权限分级、错误归一和调用路由
- 主 Agent 只看到宿主投影出的公共工具视图
- 子 Agent 看到宿主投影出的执行工具视图

这里的关键约束是：

- 主 Agent 不直接绑定某个 MCP server 的 transport、连接状态或 server 细节
- 宿主内部应存在一个统一的 MCP tool catalog / gateway，而不是在每个 agent 构建函数里手写一组分散的 wrapper
- `facts.*`、`docs.*`、`skill.*` 等工具先进入 catalog，再根据角色与策略决定是否暴露给主 Agent 或子 Agent

这样做的原因：

- 与 MCP 的 host/client/server 架构分层一致
- 让工具发现、分级、缓存和审计集中在宿主运行时治理，而不是散落在各 agent 构建逻辑中
- 避免主 Agent 直接耦合到 MCP server 细节，破坏“编排层 vs 资源访问层”的分工
- 更适合未来接入多个 MCP server、多个子 Agent 类型和不同 tool policy

第一阶段的落地范围收敛为：

- 已实现的 MCP server 保持不变，继续提供 `facts.*`、`docs.*`、`skill.*` 能力
- 宿主先实现 `catalog`：把当前已接入的 MCP 工具纳入统一清单
- 宿主再实现 `tool view`：按主 Agent / 子 Agent 角色生成不同可见工具集合
- 暂不要求同步完成外部 `registry` 抽象或完整统一 `tool gateway`

也就是说，当前阶段的最小闭环是：

1. 复用现有 MCP server
2. 在 host 侧收敛工具元数据与可见性策略
3. 用 `catalog` 生成主 Agent / 子 Agent 各自的 `tool view`
4. 逐步替换当前按 agent 手写 wrapper 列表的方式

这样做的原因：

- 可以在不推翻现有 MCP server 的前提下，先把主子工具接入方式标准化
- 将实现范围控制在本次 change 可承受的复杂度内
- 为后续引入 `registry`、统一 `tool gateway` 和更多 MCP server 预留自然演进路径

这也意味着当前 `create_public_mcp_tools()` / `create_internal_skill_mcp_tools()` 这类逻辑，后续应逐步演进为：

- catalog 注册与筛选层
- agent tool view 生成层
- 统一调用网关层

而不是长期停留在“按 agent 手写 wrapper 函数列表”的形态

### Decision 4: 子 Agent 回传给主 Agent 的结果保持最小化，不承载领域状态全文或执行细节清单

上下文隔离原则如下：

- 主 Agent 不读取子 Agent 的完整推理历史
- 主 Agent 只维护编排状态、必要摘要和 handoff 信息
- 子 Agent 使用独立执行上下文与 session
- 子 Agent 完成后只向主 Agent 返回结构化结果和压缩摘要
- 共享的是“状态结论、必要摘要、恢复信号”，而不是完整内部思维链或完整执行日志

对主 Agent 真正必要的结果信息应收敛为：

- `status`：如 `completed / failed / cancelled`
- `summary`：供后续轮次继续协作的压缩摘要
- `failure`：失败原因与失败类型（仅在失败时）
- `retryable`：是否适合由 Orchestrator 发起重试或改走澄清路径（仅在失败时）

这样做的原因：

- 保留当前“独立上下文减少 token 消耗”的优势
- 避免主 Agent 污染或膨胀
- 仍然保证后续轮次可连续

这里的关键边界还包括：

- 子 Agent 在执行中读取到的 facts / docs / skill resources，应留在自己的 working context 中，而不是通过 result 回灌给主 Agent
- 子 Agent 的领域产物（如写作草稿）应通过 state patch / session.state 持久化，而不是作为主 Agent 的结果上下文正文
- `write_document` 等最终执行步骤消费的是子 Agent working context，而不是主 Agent 的完整上下文

### Decision 5: 领域状态与主子协作结果分离；写作型子 Agent 只是特化案例

主子协作协议是通用的，但领域状态协议是按子 Agent 类型特化的。

这意味着：

- 写作型子 Agent 仍然可以像当前实现一样，把草稿内容与文档标识写入 session / writing state
- 信息查询型子 Agent 可以不产生任何持久状态，或只产生轻量查询状态
- 主 Agent 不依赖某类特定领域字段（如 `doc_type`、`doc_name`、`module_id`）才能理解一次委派是否成功

因此，本次不把写作型子 Agent 当前需要的字段直接上升为所有子 Agent 共享的标准结果字段，而是要求：

- 通用协作协议稳定
- 领域状态 patch 可选
- 具体 state shape 由子 Agent 类型决定

这样做的原因：

- 避免用当前写作链路反向定义未来所有子 Agent 的协作边界
- 让主 Agent 保持“调度中枢”角色，而不是隐式耦合到写作领域模型
- 与现有 `writing_state` 的演进方向保持兼容，而不把它误当成通用 subagent state 模型

### Decision 6: 执行链路展示采用结构化事件流，而不是只拼接 status/text

为前端和记录层引入结构化执行链路事件，例如：

- `plan_started`
- `plan_decided`
- `skill_selected`
- `skill_started`
- `resource_loaded`
- `clarification_requested`
- `clarification_answered`
- `document_written`
- `skill_completed`
- `skill_failed`

这些事件不等于原始推理文本，而是**对执行链路的安全抽象表示**。

这样做的原因：

- 前端可以稳定展示“主 Agent 在想什么阶段、子 Agent 执行到哪一步”
- Conversation log 可以按统一结构落盘
- 后续 observability 更容易扩展

### Decision 7: Orchestrator 内部逻辑要从“硬编码工具调用路径”迁移到“协议驱动”

这次必须调整 Orchestrator 的内部实现逻辑。重点包括：

- 不再把事实查询、Skill 行为和写作约束混在同一层 prompt 里
- 不再依赖固定工具清单来表达所有执行路径
- 不再假设 Skill 返回自由文本总结就足够

Orchestrator 需要改成：

- 基于结构化工具分级和 capability 决策
- 基于结构化 SkillExecutionResult 更新状态
- 基于执行结果决定继续、追问、重试或完成

这意味着：

- `document_agent.py` 的 instruction 需要重写
- `execute_skill_tool.py` 的返回协议需要重写
- `runner_adapter.py` 的事件转换与上下文传递需要扩展

### Decision 8: 执行链路展示应区分“可展示执行过程”与“不可展示内部思维”

用户提到“思维和执行链路展示”，这里必须收敛边界：

- 可以展示：规划步骤、调度决策、工具类别、加载资源、完成状态、失败原因、澄清回合
- 不应展示：原始 chain-of-thought、完整内部推理文本、未脱敏的中间提示词

这样做的原因：

- 保护模型内部推理和系统稳定性
- 仍然让用户理解系统为何这么执行
- 让展示层具有一致性和可维护性

## Risks / Trade-offs

- [Risk] Orchestrator prompt 重写后，原有稳定行为可能回归
  → Mitigation：通过对比回归测试覆盖信息查询、写作委派、追问和失败恢复主路径

- [Risk] 结构化执行结果设计过重，导致实现成本高
  → Mitigation：第一阶段只保留对 Orchestrator 决策真正必要的最小结果字段；领域状态与观测细节分别走 state/event 通道

- [Risk] 执行链路展示和内部思维边界不清，可能泄漏过多内部实现细节
  → Mitigation：定义专门的 display event schema，禁止直接透传内部 reasoning 文本

- [Risk] 主子上下文隔离做得太强，导致 Orchestrator 丢失必要延续信息
  → Mitigation：保留结构化摘要和必要状态字段，而不是完全不回传

- [Risk] 直接把写作型子 Agent 的状态字段上升为通用协议，导致未来新增非写作型子 Agent 受限
  → Mitigation：把通用协作协议与领域状态 patch 分离，只让 `writing_state` 作为当前写作型特化方案存在

## Migration Plan

1. 定义最小委派 handoff、最小执行结果、领域状态 patch 与执行事件的边界
2. 重写 Orchestrator 的提示词和工具声明，按 MCP 模式与工具分级适配
3. 调整 `execute_skill`：最小结果回传给主 Agent，领域状态写入 state，执行细节转为事件
4. 扩展 Conversation / event log，区分结果、状态快照和执行事件
5. 扩展前端展示层消费新的事件模型，而不是依赖子 Agent 自由文本
6. 做回归测试，确保上下文隔离、链路展示和委派逻辑都成立

回滚策略：

- 保留旧版自由文本摘要路径作为临时兼容 fallback
- 若结构化执行结果导致不稳定，可先关闭新展示链路，仅保留内部结构化记录

## Open Questions

- 通用 subagent state patch 是否需要一个统一容器，还是先允许写作型 `writing_state` 继续单独存在
- 执行链路展示是否需要前端单独视图，还是先在现有对话流中以事件块展示
- 主 Agent 是否需要在未来支持多 Skill 并发调度；本次先为单 Skill 调度建立协议基础
