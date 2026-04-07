## Context

当前写作链路在 MCP 改造后分为四类 LLM 成本来源：主 Agent 编排、子 Agent 推理、`write_document` 正文写作、`_generate_context_summary` 摘要生成。现状存在三个核心问题：

1. 观测口径失真：前端和历史 `llm_info` 主要记录 `write_document` 的 usage，无法代表整轮真实总成本。
2. 上下文重复注入：MCP 工具返回的全文既进入子 Agent ReAct 历史，又再次进入 `write_document` 最终 prompt；`docs.load_saved` 等路径还可能出现同一正文双重注入。
3. 上下文缺少预算：事实主档、Skill 参考文件、原型页 JSON、历史文档正文会按“能拿到就全塞”的方式进入 prompt，导致写作 prompt 急剧膨胀。

本次设计需要同时覆盖 backend 执行链、上下文装载链、持久化结构和前端展示，因此属于跨模块的性能与可观测性改造。

## Goals / Non-Goals

**Goals:**
- 建立整轮写作的阶段级 token 观测模型，能够准确区分 orchestrator、subagent、write_document、summary 的成本。
- 明确上下文传递边界：哪些内容进入 ADK 历史，哪些内容只保留在当轮 working context，哪些内容只保留摘要。
- 为写作 prompt 引入可执行的预算、去重和优先级裁剪策略，显著降低 prompt tokens。
- 保持现有主 Agent / 子 Agent / MCP 架构不变，在现有链路上做收敛优化，而不是重做整套执行框架。

**Non-Goals:**
- 不重构 Skill 选择机制或替换 ADK/ReAct 模型。
- 不在本次变更中重新设计所有 Skill 的写作规则正文。
- 不引入新的外部缓存服务或向量检索基础设施。
- 不改变用户可见的写作结果格式，只优化执行过程和元信息展示。

## Decisions

### Decision 1: 将 token 统计从“单次调用 usage”升级为“整轮聚合 + 分阶段明细”

系统内部新增 round-level usage collector，按阶段记录每次 LLM 调用：

- `orchestrator`
- `subagent`
- `write_document`
- `context_summary`

done chunk 与历史 `llm_info` 统一输出：

- `usage`: 整轮聚合值，继续兼容现有前端入口
- `usage_breakdown`: 各阶段 usage 明细
- `usage_meta`: 采集覆盖范围、缺失阶段、provider 是否提供原生 usage

这样做的原因：

- 兼容现有 UI 与持久化入口，避免一次性打破所有消费方
- 用户能继续看到一个总量，同时我们拥有真实诊断数据
- 后续优化能够明确判断“成本涨在编排、取数还是正文写作”

备选方案：

- 直接把 `usage` 改成数组或仅保留 breakdown：表达更完整，但会破坏现有 UI 和历史数据读取逻辑

### Decision 2: MCP 工具写入 ADK 历史只保留摘要，原文只保留在 working context

对于 `facts.*`、`prototypes.*`、`docs.*`、`skill.read_resource`：

- 返回给模型历史的 tool result 仅保留简短摘要或结构化摘要
- 原始正文或大块 JSON 只写入 `loaded_facts_parts` / `loaded_skill_resource_parts` / `loaded_docs_parts`
- `write_document` 只消费 working context，不依赖 tool result 原文

这样做的原因：

- 消除“子 Agent 历史烧一次、write_document 再烧一次”的重复 token
- 延续既有 session reuse 设计中“即时截断优先于事后压缩”的原则
- 仍然保留 enough information 让子 Agent 理解“刚才加载了什么”

备选方案：

- 保留全文返回，只在后续轮次做 session 剪枝：实现简单，但本轮浪费已经发生，收益不足

### Decision 3: `write_document` 引入按来源分层的上下文预算和去重策略

写作上下文统一经过 `context_budget_builder`（名称可实现期确定）收敛，执行以下步骤：

1. 以来源分层收集：facts、skill resources、docs、draft
2. 按路径或逻辑 key 去重，避免同一资源多次注入
3. 对每类来源设置默认预算与优先级
4. 对超预算内容执行摘要化，而非简单截断
5. 产出 `final_context` 与 `context_metrics`

推荐优先级：

- 第一优先级：当前目标模块事实主档、当前修改草稿
- 第二优先级：结构模板与必要写作规则
- 第三优先级：原型页摘要、历史正式版本摘要
- 最低优先级：大体量清单、冗长检查清单全文、全量页面 JSON

这样做的原因：

- 让预算成为明确可调的策略，而不是日志里的事后观察值
- 保留来源语义，便于后续精调不同来源的裁剪规则
- 支持将“摘要化”和“保留全文”做成可诊断的显式决策

备选方案：

- 只设置一个统一字符上限：简单，但无法表达不同来源的重要性

### Decision 4: 历史文档与草稿只保留一个正文注入入口

当前修改场景中，`docs.load_saved` 会同时写入：

- `loaded_docs_parts`
- `loaded_base_draft`

后续 `write_document` 又会把 `effective_context` 追加到 `final_parts`，形成重复注入。新方案要求：

- 历史正式版本正文只保留一个正文注入入口
- 另一条路径仅保留元信息或摘要引用
- `get_current_draft` 与 `docs.load_saved` 统一通过相同的“基线草稿”接口交给 `write_document`

这样做的原因：

- 直接消除确定性的重复 prompt
- 让“正式版本基线”和“当前草稿基线”具备同构行为

备选方案：

- 保留双路写入，再在 `write_document` 临时判重：能止损，但状态模型仍然混乱

### Decision 5: 写作摘要生成改为低成本输入，而不是消费大段正文

`_generate_context_summary` 当前直接消费：

- 文档正文前 4000 字
- 写作完成总结前 2000 字

新方案改为优先消费结构化元信息：

- 当前文档对象
- doc_type
- 使用的事实来源摘要
- `write_document` 输出后的文档结构摘要 / 开头摘要
- 已识别待确认项

仅在结构化信息不足时，才回退到有限正文 excerpt。

这样做的原因：

- 这一步是“为了续写服务的压缩摘要”，不是第二次阅读整篇文档
- 可以在不牺牲续写能力的前提下明显降低额外 token

备选方案：

- 彻底取消摘要生成：成本最低，但会削弱跨轮续写提示质量

## Risks / Trade-offs

- [Risk] 摘要化工具返回后，子 Agent 可能缺少即时细节，影响后续工具选择
  → Mitigation：tool result 保留“已加载什么 + 关键结论 + 待确认项”，确保推理足够；原文仍在 working context 可供 `write_document` 使用

- [Risk] 预算裁剪过度，导致最终正文缺少必要事实
  → Mitigation：按来源设置优先级与最小保留量，并将被裁剪项写入 `context_metrics` 便于诊断

- [Risk] done chunk 和历史 `llm_info` 结构扩展后，旧前端逻辑只读取 `usage`
  → Mitigation：保持 `usage` 为整轮聚合兼容字段，新增 breakdown 字段逐步消费

- [Risk] Skill 参考资料摘要化后，可能削弱某些 Skill 的结构约束
  → Mitigation：优先保留结构模板与关键规则全文；检查清单优先压缩为短版执行提示

- [Risk] 多阶段 usage 聚合依赖不同 provider 的 usage 能力，可能出现缺失
  → Mitigation：允许 breakdown 某阶段为 null，并在 `usage_meta` 标注缺失原因

## Migration Plan

1. 扩展 backend 内部 usage collector，先在不改变 UI 的情况下采集分阶段 usage
2. 收敛 MCP 工具返回内容，让历史只保留摘要，同时保留 working context 原文
3. 引入 `write_document` 上下文预算构建器，落地去重、优先级和摘要化策略
4. 修复历史文档 / 草稿双重注入路径
5. 缩减 `_generate_context_summary` 输入，切换到低成本摘要生成
6. 扩展 done chunk、`llm_info` 和前端 meta bar，展示整轮总量与分阶段明细
7. 通过日志与回归测试验证 token 降幅、写作品质和跨轮续写稳定性

回滚策略：

- 如预算裁剪影响写作品质，可先保留阶段级观测与历史摘要化改造，仅关闭严格预算裁剪开关
- 如前端无法及时消费 breakdown，可继续使用聚合 `usage` 字段，不阻塞 backend 观测落地

## Open Questions

- Skill 参考文件应采用“预编译短提示”还是“运行时摘要缓存”作为长期方案
- 原型页是否需要定义专门的“写作友好摘要字段”，而不是直接复用当前 `llm_summary + fact JSON`
- 聚合 usage 是否需要进一步区分“模型调用成本”和“上下文体量指标”两类可视化
