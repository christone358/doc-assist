## Context

当前 Agent 在处理用户文档请求时，通过 `_recommend_facts()` 扫描 `project-facts/` 目录，对所有 `.md` 文件做关键词匹配，将命中文件全量注入 system prompt。这种方式在项目规模小时勉强可用，但存在两个根本缺陷：一是粒度不可控（用户要写"登录模块"却带入所有模块的信息），二是 Skill 无法表达自己需要哪类上下文，Agent 只能猜测。

参考设计文档：`openspec/design/context-loading-architecture.md`

## Goals / Non-Goals

**Goals:**
- 重构 project-facts 存储结构为星形模型，modules.md 作为枢纽和检索入口
- Agent 能精确定位目标模块并只加载该模块相关的上下文
- Skill 通过自然语言正文表达上下文需求，Agent 用 LLM 推断 required/optional
- 上下文加载过程在 status steps 中对用户可见
- 支持两轮生成：第一轮生成后 LLM 可触发加载可选上下文，执行第二轮

**Non-Goals:**
- 不实现管理 UI（project-facts 文件仍由用户手动维护）
- 不实现向量检索或语义搜索
- 不处理多模块并行文档生成场景
- 不迁移现有 project-facts 示例数据（格式变更由用户自行更新）

## Decisions

### 决策一：星形存储结构而非三层目录

**选择**：`project-facts/` 下使用扁平清单文件（modules.md / usecases.md / classes.md / interfaces.md）+ prototypes 目录，以模块 ID 作为关联键。

**放弃**：保留 layer1/layer2/layer3 目录，在目录内按模块细分子目录。

**原因**：分层目录的"层"是概念层，不是检索层——Agent 仍然需要知道哪个层的哪个文件包含目标模块信息。星形模型将"分层"改为"条目内信息密度分层"（摘要 vs 详情），Agent 的检索逻辑变为单一操作：按模块 ID 过滤指定清单文件。维护成本更低，新增模块只需在各清单文件添加一条带模块标签的条目。

### 决策二：系统词汇表作为 Agent-Skill 契约

**选择**：定义 6 个标准词汇（modules / usecases / classes / interfaces / prototypes / source），存放在 `project-facts/README.md`，同时作为用户的维护规范和 Agent 的映射表。

**放弃**：让 Skill 自由描述需要的文件路径，或由 Agent 自行解析 Skill 正文中的任意文件引用。

**原因**：路径耦合破坏 Skill 的可移植性；完全自由的语义解析不可靠且难以排查。词汇表是轻度约定，Skill 作者只需从有限列表中选择，Agent 的映射逻辑确定，错误可预期。

### 决策三：LLM 推断 + 可覆盖

**选择**：Agent 用一次轻量 LLM 调用从 Skill 正文推断 required/optional；Skill 可在 YAML front matter 中用 `context_needs` 字段显式覆盖，显式优先。

**放弃**：纯结构化 YAML 声明（出错不易发现）；纯 LLM 推断（Skill 作者无法精确控制）。

**原因**：推断的好处是 Skill 作者只需写自然语言，零额外负担；覆盖机制是安全阀，当推断结果不准确时 Skill 作者可以精确干预。两者结合，出错时排查路径清晰：先看 YAML 覆盖是否存在，再看 LLM 推断日志。

### 决策四：两轮生成而非 Function Calling

**选择**：LLM 第一轮生成时通过内嵌标记 `<!--needs: prototypes-->` 触发可选上下文加载，Agent 检测到标记后加载对应内容，执行第二轮生成。

**放弃**：基于 Function Calling 的实时工具调用（LLM 生成中途暂停调用工具）。

**原因**：Function Calling 需要模型支持，增加复杂性，且在流式输出场景中用户体验不好（生成中途中断）。两轮生成对现有流式架构改动最小，用户看到"补充上下文"的 status step 后继续看到新的生成内容，体验直观。

### 决策五：模块定位用 LLM 语义匹配

**选择**：先对 modules.md 做精确字符串匹配，失败时用 LLM 从模块列表中选最匹配的。

**放弃**：只用精确匹配（用户语言多变，"登录功能"和"登录模块"是同一个）；全部用 LLM（每次都消耗额外的 LLM 调用）。

**原因**：精确匹配成本低，命中率在模块名使用一致时足够高；LLM 语义匹配作为兜底，牺牲一点延迟换取准确性。modules.md 支持在模块条目写别名字段，可提升精确匹配命中率。

## Risks / Trade-offs

**[风险] entity 提取错误**
→ 用户说"帮我写认证模块的文档"，Agent 提取到的模块 ID 与 modules.md 中的实际 ID 不匹配，导致加载空上下文，LLM 生成内容与预期无关。
→ 缓解：status step 展示"已定位模块: {模块名}"，用户可立刻发现错误；支持 modules.md 别名字段提升匹配率；LLM 语义匹配兜底。

**[风险] LLM 推断 context_needs 不准确**
→ Skill 正文描述模糊，推断结果偏离实际需求，导致文档生成质量下降。
→ 缓解：推断结果写入日志，开发者可检查；Skill 作者可用 `context_needs` YAML 字段显式覆盖。

**[风险] 两轮生成增加延迟**
→ 触发可选上下文加载时，用户需等待两次 LLM 响应。
→ 缓解：可选上下文加载是非强制路径，多数情况单轮生成即可完成；第二轮开始前显示"补充上下文"step，用户知道正在发生什么。

**[Trade-off] 词汇表是轻度耦合**
→ Skill 作者需要了解 6 个系统词汇才能写出准确的上下文描述（或 YAML 覆盖）。
→ 接受：6 个词汇有限且语义直观；`project-facts/README.md` 作为参考文档，降低学习成本；LLM 推断降低了必须了解词汇表的紧迫性。

**[Trade-off] project-facts 结构迁移**
→ 现有 layer1/layer2/layer3 目录结构需要用户手动重组为星形结构，现有示例数据需要更新格式。
→ 接受：这是一次性迁移成本，新结构的长期维护成本更低；提供格式规范文档和示例供用户参考。

## Migration Plan

1. 更新 `project-facts/README.md`，写入新的格式规范和词汇表
2. 重构 `project-facts/` 目录，将现有层级内容迁移到星形结构（modules.md + 各清单文件）
3. 修改 `backend/agent/core.py`，重构 `_recommend_facts()` 为新的多步骤加载流程
4. 更新 `stream_message()` 中的 status steps，新增上下文相关步骤
5. 更新现有 skills 的 skill.md（可选，推断方式向后兼容无需强制更新）

回滚策略：重构前保留 layer1/layer2/layer3 目录备份；Agent 代码修改独立提交，可单独回滚。

## Open Questions

- **多模块场景**：用户要求写跨模块文档时（如"认证子系统的整体设计"），模块定位和上下文加载策略如何扩展？暂时不在本次范围内，但存储结构设计需要不阻碍未来扩展。
- **大文件过滤**：usecases.md 条目数量超过 50 条时，过滤后仍可能有多条，context 长度如何控制？是否需要摘要截断策略？
- **source 词汇的边界**：源代码文件可能很大，加载时应该加载整个文件还是只加载声明的源码目录里的特定文件？需要在实现时明确截断规则。
