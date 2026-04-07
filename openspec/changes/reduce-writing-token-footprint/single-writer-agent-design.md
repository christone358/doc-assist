# Single Writer-Agent Design

## 背景

当前链路把“找资料”和“正式写作”拆成两个 LLM 阶段，带来的主要问题不是职责划分本身，而是同一份 Skill 内容、同一份事实资料、同一份历史正文会被重复读取。为降低 token 消耗，同时保留渐进式披露和工具调用能力，可以把写作执行收敛为一个统一的写作子 Agent。

这个统一子 Agent 的职责是：

- 接收主 Agent 的写作委托
- 在内部选择合适的写作 Skill
- 逐步调用工具加载事实、原型、历史文档和参考资源
- 在资料充分后直接完成正式写作
- 输出结构化结果，供主 Agent 和其他 Agent 消费

## 关键设计判断

### 1. 可以是一个逻辑 Agent，但不应死守一条无限增长的消息历史

“一个 Agent”指的是一个统一的写作执行器、一个清晰的输入输出契约、一个共享运行状态。

它不等于：

- 所有工具结果都直接塞进同一条历史
- 从 Skill 选择到最终成文都保留完整原始消息
- 最后一轮写作必须继承前面所有思考和工具轨迹

如果严格要求整个过程都共用同一条不断增长的 LLM 历史，那么即使去掉独立 `write_document` 调用，最终成文时仍会把前期的思考、摘要、工具轨迹一起带进去，上下文窗口仍然会持续膨胀。

因此，本设计采用：

- **单一逻辑 Agent**
- **共享运行状态**
- **分层上下文**
- **阶段性压缩与切换**

也就是说，系统层面只有一个写作子 Agent，但这个 Agent 的“决策上下文”和“成文上下文”必须严格隔离。

## 目标

- 保留一个统一的写作子 Agent，避免“找资料”和“写作”两段重复读取上下文
- 支持一个子 Agent 内部管理多个 writing skill
- 让子 Agent 的输入输出具备明确契约，便于与主 Agent、其他 Agent 交互
- 控制整个执行过程中 LLM 可见上下文的体量，避免随着工具调用轮次失控
- 在最终写作阶段只消费一份干净、预算可控、按优先级筛选过的写作上下文包

## 非目标

- 不要求把整个写作过程压缩成一次 completion
- 不要求所有工具都返回完整正文给 LLM 历史
- 不保留“思考过程可直接成为写作素材”的隐式行为

## 总体结构

```text
主 Agent
  -> 委托给 Writer Agent

Writer Agent
  -> Phase A: 选择 Skill
  -> Phase B: 渐进式取数与判断
  -> Phase C: 组装 final_write_packet
  -> Phase D: 基于 final_write_packet 输出正式正文

共享状态 WriterRunState
  - 保存原始资料
  - 保存轻量摘要
  - 保存预算信息
  - 保存最终写作包
```

## 输入输出契约

### 输入

写作子 Agent 接收来自主 Agent 的标准化输入：

| 字段 | 说明 |
|---|---|
| `user_intent` | 用户本轮写作目标 |
| `doc_target` | 当前文档对象、模块、子系统、已有 doc_name/doc_id 等 |
| `conversation_summary` | 当前对话的轻量摘要，不含长正文 |
| `baseline_doc_ref` | 可选，指向当前已存在的历史文档或草稿 |
| `available_skills` | 当前写作子 Agent 可用的 writing skill 集合 |
| `execution_limits` | 本轮可用的步数、预算、最大加载来源数等 |

### 输出

写作子 Agent 向主 Agent 返回结构化结果：

| 字段 | 说明 |
|---|---|
| `status` | `completed` / `needs_clarification` / `failed` |
| `selected_skill_id` | 本轮实际使用的 writing skill |
| `doc_type` | 文档类型 |
| `final_draft` | 正式正文 |
| `execution_summary` | 供主 Agent 续轮理解的短摘要 |
| `pending_questions` | 若需要补充信息，列出待澄清问题 |
| `usage_breakdown` | 各阶段 token 明细 |
| `context_metrics` | 加载来源数、裁剪数、最终写作包大小等 |

## 内部状态模型

新增统一运行态 `WriterRunState`，作为写作子 Agent 的唯一真相源。

### 核心字段

| 字段 | 作用 |
|---|---|
| `run_id` | 本轮写作执行 id |
| `phase` | `skill_select` / `context_gather` / `compose` / `complete` |
| `user_intent` | 用户写作目标 |
| `doc_target` | 当前文档对象 |
| `selected_skill_id` | 已选择的 skill |
| `compiled_skill_rules` | 预处理后的 skill 写作规则 |
| `baseline_draft` | 当前唯一基线草稿 |
| `source_store` | 原始资料仓库，保存全文或结构化详情 |
| `source_briefs` | 每个来源给 Agent 决策看的轻量摘要 |
| `selected_source_ids` | 已被确认与本次写作相关的来源 |
| `context_metrics` | 当前体量指标与裁剪指标 |
| `final_write_packet` | 最终成文使用的上下文包 |

### 状态设计原则

- 原始资料进入 `source_store`，不直接进入 LLM 历史
- Agent 决策时只看 `source_briefs`
- 历史正文只保留一个入口，统一写入 `baseline_draft`
- 最终写作只读取 `final_write_packet`

## 单 Agent 的上下文分层

为了控制整体窗口，必须把上下文拆成三层：

### 1. 指令层

这一层只包含：

- Writer Agent 的固定执行规则
- 当前选中的 skill 规则
- 工具说明

要求：

- Skill 只在本轮加载一次
- 最终写作阶段不再重复注入 skill 正文全文
- 对长 Skill 资源做预编译，只保留结构模板和关键约束

### 2. 决策层

这一层服务于 Agent 的工具选择和流程判断，只包含：

- 当前已加载哪些来源
- 每个来源的短摘要
- 当前缺什么信息
- 是否满足进入写作阶段的条件

禁止内容：

- 大段事实全文
- 页面全量 JSON
- 整篇历史正文
- LLM 的长链路思考文本

### 3. 成文层

这一层只在进入 `compose` 阶段时生成，只包含：

- 编译后的 skill 写作规则
- 最终保留的事实内容
- 必要的原型摘要
- 必要的参考资料
- 唯一基线草稿
- 当前文档对象元信息

禁止内容：

- Agent 的中间思考
- 工具调用日志
- 无关来源
- 已被裁剪掉但未入选的原始全文

## 工具契约设计

所有工具改成“双轨输出”：

### 返回给 Agent 历史的内容

- 来源标识
- 资源类型
- 100 到 300 字的摘要
- 关键结论
- 待确认项

### 写入 `WriterRunState` 的内容

- 原始正文
- 原始 JSON
- 结构化字段
- 来源路径与元数据

### 示例

| 工具 | 历史返回 | 状态写入 |
|---|---|---|
| `facts.get_module` | 模块简介、边界、关键结论、`source_id` | 模块事实全文 |
| `prototypes.get_page` | 页面用途、关键操作、主要字段、`source_id` | 页面详情 JSON / 结构化摘要 |
| `docs.load_saved` | 已加载文档名、版本、长度、`source_id` | 历史正文，写入 `baseline_draft` |
| `skill.read_resource` | 模板/规则/检查清单的用途和关键约束 | 参考资源全文 |

## 上下文体量控制机制

这是本设计最关键的部分。

### 机制 1: 预算前置，而不是事后观察

系统需要维护明确预算：

| 预算项 | 建议含义 |
|---|---|
| `max_decision_brief_chars` | 决策层累计摘要上限 |
| `max_selected_sources` | 最多允许保留多少个入选来源 |
| `max_compose_chars` | 最终成文包总字符上限 |
| `per_source_soft_limit` | 单个来源的软上限 |
| `per_source_hard_limit` | 单个来源的硬上限 |

当预算接近阈值时，系统优先：

- 去重
- 丢弃低优先级来源
- 把长文本转成更短摘要
- 把历史正式版降级成摘要，而非全文

### 机制 2: 决策层滚动压缩

即使只返回摘要，随着工具调用次数增加，决策层历史仍然会变胖。

因此需要每隔固定步数做一次压缩：

- 保留最新 2 到 4 条关键决策消息
- 其余来源摘要合并成一条 `progress_snapshot`
- 删除或替换旧的零散摘要消息

压缩后的 `progress_snapshot` 只保留：

- 当前文档对象
- 已确认使用的来源
- 明显缺口
- 为什么可以进入下一阶段

### 机制 3: 阶段屏障

从 `context_gather` 进入 `compose` 时，必须设置一个明确的阶段屏障。

进入条件：

- skill 已选定
- baseline 已确定
- 至少有最小必要事实来源
- 没有未解决的关键歧义

进入 `compose` 后：

- 决策层不再继续追加来源摘要
- 由 `prepare_final_context` 一次性构造 `final_write_packet`
- 最终写作只消费 `final_write_packet`

### 机制 4: 同一逻辑 Agent，允许物理上下文切换

为了真正控制窗口，建议区分：

- **逻辑上的同一个 Writer Agent**
- **物理上的不同消息窗口阶段**

具体做法：

- `skill_select` 和 `context_gather` 运行在探索窗口
- 进入 `compose` 时，创建一个干净的成文窗口
- 成文窗口只继承：
  - `compiled_skill_rules`
  - `doc_target`
  - `final_write_packet`
  - 必要的极短执行摘要

不继承：

- 详细工具轨迹
- 历史推理文本
- 过期来源摘要

这不意味着引入第二个写作 Agent，而是同一个 Writer Agent 进入了一个新的成文阶段窗口。

这是控制单 Agent 全流程上下文的最有效手段。

## Skill 选择机制

子 Agent 内部支持多个 writing skill。

### 流程

1. 读取主 Agent 传来的 `user_intent` 和 `doc_target`
2. 在有限 skill 集合中判断最匹配的 skill
3. 将 skill 编译为两部分：
   - `skill_decision_brief`
   - `compiled_skill_rules`
4. 决策阶段只使用 `skill_decision_brief`
5. 最终成文阶段只使用 `compiled_skill_rules`

### 设计原因

- 避免整个 Skill 正文从头到尾都占据 LLM 窗口
- 把“如何判断该查什么”和“最终如何写”拆成两种更短的表示

## 最终写作包 `final_write_packet`

`prepare_final_context` 负责从 `WriterRunState` 构建最终写作包。

### 输入

- `compiled_skill_rules`
- `baseline_draft`
- `selected_source_ids`
- `source_store`
- `doc_target`
- 当前预算参数

### 处理步骤

1. 按来源类型分组
2. 依据路径和逻辑 key 去重
3. 按优先级筛选
4. 对超预算内容做摘要化
5. 生成结构化写作包和 `context_metrics`

### 推荐优先级

| 优先级 | 来源 |
|---|---|
| P0 | `baseline_draft`、当前目标模块事实主档 |
| P1 | 结构模板、关键写作规则 |
| P2 | 当前相关页面摘要、当前功能事实补充 |
| P3 | 历史正式版摘要、检查清单短版 |
| P4 | 大清单、全量页面 JSON、低相关附属资料 |

### 输出

`final_write_packet` 至少包含：

- 文档对象信息
- 文档类型
- 写作规则
- 必要事实
- 当前基线草稿
- 被引用来源列表
- `context_metrics`

## 观测与诊断

必须新增可观测字段，不然无法判断窗口是否真的被控制住：

| 指标 | 说明 |
|---|---|
| `decision_brief_chars` | 决策层当前摘要体量 |
| `source_store_count` | 已加载原始来源数 |
| `selected_source_count` | 最终入选来源数 |
| `compose_packet_chars` | 最终写作包大小 |
| `trimmed_source_count` | 被裁剪来源数 |
| `usage_breakdown` | skill 选择、取数、成文、摘要各阶段 token |

## 推荐落地步骤

### Phase 1

- 保留现有主 Agent 委托方式
- 把工具改成“摘要进历史、原文进状态”
- 新增 `WriterRunState`

### Phase 2

- 子 Agent 内部支持多个 writing skill
- 新增 `compiled_skill_rules`
- 建立 `prepare_final_context`

### Phase 3

- 去掉独立 `write_document` 二次 LLM 调用
- 改为同一 Writer Agent 的 `compose` 阶段直接输出正文
- 引入阶段屏障和成文窗口切换

### Phase 4

- 加入预算开关、回归测试和前端 usage breakdown 展示

## 风险与应对

### 风险 1

如果 `skill_decision_brief` 过短，Agent 可能不会正确调用工具。

应对：

- 对每个 skill 预定义“最小决策规则集”
- 保留关键工具映射和禁忌规则

### 风险 2

如果 `final_write_packet` 裁剪过度，写作品质会下降。

应对：

- 为 P0/P1 来源设置最小保留量
- 输出 `context_metrics` 便于回看

### 风险 3

如果强制共用单一物理消息窗口，最终写作仍会把探索过程一起带入。

应对：

- 保持“单一逻辑 Agent”
- 允许在 `compose` 阶段切换到干净窗口

## 结论

这套方案的关键不是“把两个执行阶段粗暴合并”，而是把写作系统重构为：

- 一个统一的 Writer Agent
- 一套共享运行状态
- 两类严格隔离的上下文
- 一个预算可控的最终写作包

如果设计正确，系统可以同时获得：

- 渐进式披露的灵活性
- 单 Agent 执行的一致性
- 干净写作上下文带来的质量稳定性
- 明显低于现状的 token 消耗
