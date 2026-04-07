## Context

当前系统已经初步形成“主 Agent + 写作 Skill Sub-agent + 项目事实库 + 历史文档”的分层模型，但运行时访问模式仍然分散：

- 主 Agent 与 Skill Sub-agent 直接持有宿主内置工具函数集合
- 项目事实查询由 `fact_tools` 暴露，历史文档由 `saved_doc_tools` 暴露
- Skill 本地资源访问能力尚未完全接入，现有方案仍停留在局部补齐阶段
- `write_document` 最终只稳定消费 `SKILL.md` 和 facts，上下文来源仍不统一

随着 Skill 资源运行时访问、Orchestrator as Hub、历史文档复用等能力逐步增强，继续沿用“每类资源一个宿主工具集合”的模式会放大几个问题：

- 主 Agent 与 Skill Sub-agent 的能力面不一致
- facts / skill resources / docs 的权限边界和返回结构缺少统一治理
- 资源访问逻辑继续固化在宿主代码中，不利于后续替换 Agent Runtime 或扩展 capability registry
- Skill 中声明的资源和脚本仍然更像“约定”而不是“标准运行时能力”

因此，本变更设计一个统一的 MCP 运行时访问层，把“如何访问资源”从宿主运行时中抽离出来，但不在本阶段改变 Orchestrator 负责编排和 Skill 调度的基本职责。

## Goals / Non-Goals

**Goals:**

- 为主 Agent 和 Skill Sub-agent 提供统一的 MCP 运行时访问协议
- 将 MCP server 设计为可独立对外暴露的标准 remote MCP server，而不是仅供当前系统内部调用的私有适配层
- 将运行时上下文来源划分为 `facts.*`、`skill.*`、`docs.*` 三个 namespace
- 将工具能力划分为“公共工具集”和“内部工具集”，控制对外暴露边界
- 保留 Skill 调度由 Orchestrator / 宿主运行时负责，不强制把 `execute_skill` 改造成 MCP 调用
- 在必要处复用现有实现细节，但不把旧工具或旧行为视为默认正确来源
- 明确不同 namespace 的权限边界、缓存策略、上下文注入方式和观测要求
- 为未来的 capability registry、动态发现和可插拔 Skill Runtime 建立统一协议基础

**Non-Goals:**

- 不在本次变更中实现“一个万能资源工具”来覆盖所有上下文来源
- 不在本次变更中强制将 Skill 调度、Sub-agent 生命周期管理、任务规划全部迁移到 MCP
- 不在本次变更中实现多语言脚本执行器；脚本执行仍以 Python 为第一阶段目标
- 不在本次变更中实现向量检索、远程知识库同步或复杂权限系统
- 不要求一次性删除现有宿主工具实现；允许通过兼容层逐步替换
- 不在本次变更中无差别对外暴露所有能力，尤其不默认公开高风险脚本执行能力
- 不以“保留旧工具/旧行为”为目标；任何不符合新契约的旧内容都不应被长期保留
- 不在本次变更中开发完整的外部 MCP client 产品形态；重点是把 server 做成标准 remote server

## Decisions

### Decision 1: 统一协议使用 MCP，但按 namespace 保留领域边界

运行时访问统一通过 MCP 暴露，但明确分为三个基础 namespace：

- `facts.*`：项目事实访问
- `skill.*`：当前 Skill 私有资源访问
- `docs.*`：历史文档与版本基线访问

基于当前 `project-facts` 的真实管理模式，第一阶段建议直接固化如下工具清单，避免后续实现只停留在 namespace 抽象层，也避免超前暴露当前并不存在稳定支撑的数据粒度：

- `facts.list_modules()`：获取当前项目中的模块清单与基础聚合摘要
- `facts.get_module(module_ref)`：获取某个模块聚合根下的完整事实信息
- `skill.list_resources()`：列出当前 Skill 可用资源及分类
- `skill.read_resource(relative_path)`：读取当前 Skill 根目录内文本资源
- `skill.run_script(relative_path, payload?)`：执行当前 Skill 根目录内 Python 脚本
- `docs.list_saved(doc_type?)`：列出历史已保存文档元数据
- `docs.load_saved(doc_type, doc_name, version?)`：加载历史文档正文和版本元数据

当前这样收敛的原因是：

- 当前人工维护层是 `project-facts/modules/*.md` 的模块档案
- 当前系统派生层主要提供 `generated/views/modules.md`、`generated/views/module-details/*.md` 以及结构化索引 JSON
- 当前真实场景主要是：
  - 查询“有哪些模块”
  - 查询“某个模块聚合根下的全部信息”
- 当前还没有稳定、长期维护的“模块聚合根以下更细事实工具契约”

因此第一阶段不把以下能力上升为 public MCP 工具：

- `facts.resolve_module`
- `facts.get_overview(category)`
- `facts.get_module_sheet`
- `facts.get_detail`

这些如果仍然需要，可以作为 server 内部实现辅助逻辑存在，用于：

- 模块名 / 别名解析
- generated JSON / Markdown 视图复用
- 内部缓存和查找加速

其中：

- `facts.*` 主要映射当前 `fact_tools`
- `docs.*` 主要映射当前 `saved_doc_tools`
- `skill.*` 主要吸收正在规划中的 Skill 资源运行时能力

同时，本次不把所有工具视为同一暴露级别，而是划分为两层工具集：

- 公共工具集（remote public tools）：
  - `facts.list_modules`
  - `facts.get_module`
  - `docs.list_saved`
  - `docs.load_saved`
- 内部工具集（internal/private tools）：
  - `skill.list_resources`
  - `skill.read_resource`
  - `skill.run_script`

第一阶段建议按这个边界建设：

- `facts.*` 与 `docs.*` 按标准 remote MCP server 直接对外暴露
- `skill.*` 先按内部受控能力设计，`skill.run_script` 默认仅内部使用

不采用“一个万能 `read_resource` / `query_anything` 工具”的原因：

- 不同资源域的参数模型不同：facts 当前更适合“模块清单 + 模块聚合根查询”，skill 偏路径查询，docs 偏版本查询
- 不同资源域的安全边界不同：`skill.*` 风险最高，`facts.*` 通常为公共只读
- 不同资源域的返回结构和缓存策略不同
- 清晰的 namespace 能降低模型的工具选择和参数推理成本

备选方案：

- 设计一个统一 `resource.*` 工具：表面更简洁，但会混淆领域语义、权限与返回结构
- 保持每类资源使用独立宿主工具集合：短期简单，但无法形成统一治理和可迁移访问层

### Decision 1.1: 本次 MCP Server 按 remote MCP server 设计，而不是仅做应用内 adapter

本次 MCP Server 的目标形态是：

- 对内：服务当前系统中的主 Agent 与 Skill Sub-agent
- 对外：能够被其他符合标准的 MCP client / agent 通过标准协议调用

因此设计时必须满足：

- 使用标准 MCP SDK 与标准传输
- 工具 schema 不依赖当前宿主内部状态对象命名
- 对外暴露的公共工具保持宿主无关的参数与返回语义
- 预留认证、访问控制与工具分级边界
- server 在理论上可独立部署和运行；当前项目可先与主系统打包部署，但不得依赖“只能进程内调用”的形态假设

不采用“只做应用内 adapter”的原因：

- 会把当前系统内部状态、目录结构和运行时细节固化进工具契约
- 后续若要被其他 agent 调用，需要重新做一轮协议抽象
- 不利于把 facts / docs 能力沉淀成长期复用的标准工程服务

### Decision 1.2: 公共工具契约必须减少隐式宿主上下文依赖

既然本次要按 remote MCP server 方式实现，就不能默认调用方天然处于“当前应用内部”。

因此第一阶段约束如下：

- 公共工具集不得依赖当前宿主内部对象、当前应用框架状态或仅在进程内可见的隐式上下文
- `facts.*` 与 `docs.*` 的 public schema 应使用显式参数表达查询目标
- 强依赖当前执行上下文的能力继续放在内部工具集，如 `skill.*`
- 即使当前项目中 server 与主系统打包运行，也应沿用 remote server 的契约边界，而不是退回宿主内函数调用语义

这样做的原因：

- 解决当前“默认存在当前会话、当前 skill、当前项目”的内部耦合问题
- 避免 remote 化时再做第二次 schema 重构
- 让公共能力从第一天起就能被多个系统稳定复用

备选方案：

- 先按内部隐式上下文实现，后续再改 remote 契约：短期省事，但会把核心耦合重新固化回系统内部

### Decision 2: Phase 1 保持 Skill 调度在宿主运行时内，不强制通过 MCP

本阶段继续保留：

- 主 Agent 判断用户意图
- Orchestrator 选择 Skill
- 宿主运行时调用 `execute_skill(...)`
- Skill Sub-agent 在执行期间通过 MCP 访问资源
- 主 Agent 做最小必要适配，认识新的 MCP 公共工具名与职责边界

这样做的原因：

- Skill 调度属于编排层职责，不是资源访问层职责
- 当前 `execute_skill` 已经承载会话状态转移、摘要生成、draft 状态传递等宿主责任
- 先统一“访问面”，再考虑是否统一“调度面”，迁移风险更可控
- 第一阶段若完全不调整主 Agent 对工具名和职责边界的认知，将无法形成可切换的最小闭环

备选方案：

- 同时引入 `skills.invoke(...)` MCP 接口：架构更纯粹，但会一次性改动 Orchestrator、Session、Sub-agent 生命周期，超出第一阶段承受范围

### Decision 3: MCP Runtime 可以复用现有实现细节，但不以保留旧工具为目标

第一阶段的实现方式是：

- `facts.*` 优先适配现有 `fact_tools` / `context_loader` / `project_fact_modules`
- `docs.*` 优先适配现有 `saved_doc_tools` 和版本解析逻辑
- `skill.*` 基于当前 Skill 资源扫描与资源运行时访问方案实现

这样做的原因：

- 能复用现有实现中有价值的事实解析、文档加载与 Skill 目录边界逻辑
- 能降低“协议切换 + 业务重写”同时发生带来的风险
- 便于在每一层增加统一日志、鉴权、缓存和错误格式

这里的关键约束是：

- 复用的是“实现细节”，不是“旧工具契约”
- 旧工具不被视为默认正确来源
- 若旧行为不符合新的 public MCP 契约或主 Agent 适配逻辑，应直接重写或移除，而不是为了兼容而保留

备选方案：

- 直接重写所有资源访问实现：整洁，但风险高且难以回归验证

### Decision 3.2: MCP Server 技术栈选择 Python 官方 SDK，而不是手写协议层或切换到其他语言

本次 MCP Server 的推荐技术栈为：

- 语言与运行时：`Python 3.11`
- 官方 SDK：Model Context Protocol 官方 `Python SDK`
- Server 开发层级：优先使用 `FastMCP`
- 传输模式：
  - 本地开发与调试使用 `stdio`
  - 项目内正式接入和对外暴露优先使用 `Streamable HTTP`
- 测试方式：`pytest` + MCP Inspector / 标准客户端回归

这样选择的原因：

- 当前后端已基于 Python / FastAPI / Uvicorn 运行，继续沿用 Python 可以最大化复用现有工程、部署和测试体系
- 官方 Python SDK 能减少手写协议层的复杂度和协议漂移风险
- `FastMCP` 适合当前以工具和资源为中心的 server 构建方式，能够更快把 namespace 与工具清单落地
- `Streamable HTTP` 更适合作为可独立对外暴露的标准 MCP 服务形态；`stdio` 则适合本地开发、Inspector 调试和单机集成
- 当前项目可以先将 MCP server 与主系统一并打包、同进程或同部署单元运行，但 server 入口、配置和传输实现应保持可独立启动

备选方案：

- 手写 MCP 协议层：灵活，但会增加协议兼容、升级和调试成本
- 采用 TypeScript SDK 单独实现 server：生态成熟，但与当前 Python 后端割裂，增加跨语言维护成本

### Decision 3.1: 现有宿主工具与 MCP 工具的映射关系应在第一阶段明确

为了让改造任务可执行，第一阶段采用“现有实现能力到 MCP 工具”的显式映射：

- `get_fact_overview("modules")` / generated module index → `facts.list_modules`
- `load_module_fact_sheet` + 模块解析辅助逻辑 → `facts.get_module`
- `list_saved_documents` → `docs.list_saved`
- `load_saved_document` → `docs.load_saved`
- 新增 Skill 资源能力 → `skill.list_resources` / `skill.read_resource` / `skill.run_script`

这里的模块解析、generated JSON 读取和视图选择仍可在 server 内部作为实现细节存在，但不在第一阶段暴露为单独的 public MCP 工具。

这样做的原因：

- 便于按当前已有代码能力切分开发任务
- 便于识别哪些旧实现可以保留为内部细节，哪些必须随着 MCP 契约一起重写
- 便于验证“新 public 契约是否满足真实业务场景”，而不是被旧工具设计反向绑架

这个决策**不表示**：

- 旧工具设计是正确的
- 旧工具名称需要继续保留
- 主 Agent 可以不做同步适配

相反，它表示：

- 旧实现仅作为迁移参考
- public MCP 工具契约以当前业务场景和新架构边界为准
- 主 Agent / Orchestrator 侧必须同步调整适配逻辑；这部分由配套 change 单独推进

### Decision 3.3: `facts.*` 第一阶段围绕模块聚合根设计，而不是围绕更细粒度事实设计

第一阶段的 `facts.*` 应与当前事实库真实形态一致：

- `facts.list_modules()` 返回模块清单、基础归属信息和必要摘要
- `facts.get_module(module_ref)` 返回模块聚合根下的完整事实正文或等价结构化结果

不提前设计更细粒度 public 工具的原因：

- 当前模块档案已经是聚合根，且大多数写作场景基于聚合根即可完成
- 当前 `generated` 层更多是派生索引和缓存视图，不应被过早固化为复杂 public API

备选方案：

- 一次性设计更细的 `facts.get_detail` / `facts.get_relation` / `facts.get_prototype` 等：会让工具契约领先于数据治理现实

### Decision 4: MCP 读取结果采用“两层上下文”传递，而不是主子 Agent 共享同一个资源池

虽然最终写作 prompt 需要统一消费多种上下文来源，但上下文传递必须区分两层：

- 主 Agent 编排上下文：仅保留任务状态、必要摘要和委派给子 Agent 所需的 handoff 信息
- 子 Agent working context：记录当前执行中显式读取的 facts、skill resources、docs 基线内容，并按来源分层缓存

子 Agent working context 内部仍需分层记录：

- facts loaded
- skill resources loaded
- docs base loaded

并保留来源标签，例如：

```text
### [Facts: module-sheet mod-xxx]
...

### [Skill Resource: references/structure/module-manual.md]
...

### [Saved Document: user-manual / 业务系统管理模块 / v1.0.1]
...
```

这样做的原因：

- 保持主 Agent 只持有编排所需的最小信息，而不是膨胀成共享写作上下文
- 让 `write_document` 消费的是子 Agent 当前 working context，而不是混杂的共享大文本块
- 便于控制不同来源的注入顺序和裁剪策略
- 便于日志、调试、缓存命中和后续 prompt 优化

备选方案：

- 只保留一个主子 Agent 共享的 `loaded_resource_parts` 列表：实现简单，但会破坏上下文隔离并放大 prompt 污染风险

### Decision 5: `skill.*` 默认隐含当前 Skill 作用域，不让模型自由指定任意 Skill

`skill.*` namespace 的资源访问必须绑定“当前正在执行的 Skill”：

- `skill.list_resources()`
- `skill.read_resource(relative_path)`
- `skill.run_script(relative_path, payload?)`

这些接口默认以当前 Skill 根目录为边界，不建议让模型显式传入任意 `skill_id`。

这样做的原因：

- 降低跨 Skill 越权风险
- 简化模型的参数选择
- 让 Skill 资源访问语义更接近“当前 Skill 的本地工具箱”

备选方案：

- 允许 `skill.read_resource(skill_id, path)`：更灵活，但会削弱权限边界并增加误用概率

### Decision 5.1: 公共工具集与内部工具集采用不同暴露策略

本次设计明确区分两类工具：

**公共工具集**

- 面向外部 agent / client 可调用
- 优先覆盖低风险、只读、领域语义稳定的能力
- 主要包括 `facts.*` 与 `docs.*`

**内部工具集**

- 面向当前系统内部 orchestrator / sub-agent 使用
- 允许携带更强的上下文绑定和更高风险的执行能力
- 主要包括 `skill.*`，尤其是 `skill.run_script`

这样做的原因：

- 事实查询和历史文档读取更适合作为长期稳定的共享服务能力
- Skill 私有资源天然与当前项目、当前 skill、当前执行上下文绑定更紧
- 脚本执行能力的安全边界远高于纯读取类工具，不适合默认对外开放

备选方案：

- 所有工具无差别对外开放：简单，但会显著放大安全和多租户风险
- 完全不对外开放，只给内部 agent 使用：会失去 remote MCP server 的长期价值

### Decision 6: `facts.*` 与 `docs.*` 默认为只读 namespace

在本阶段：

- `facts.*` 只提供只读查询
- `docs.*` 只提供列表、加载、比较等只读访问
- `skill.*` 中脚本执行也仅限当前 Skill 根目录内受限执行

这样做的原因：

- 与现有项目事实“人工维护、系统只读使用”的原则一致
- 避免 MCP 在第一阶段承担写操作审计与冲突管理复杂度
- 使运行时能力聚焦于“按需加载上下文”

备选方案：

- 允许 MCP 写入 facts 或 docs：未来可能有价值，但本阶段会显著抬高安全与一致性要求

### Decision 6.1: 已保存正式文档与未保存草稿分开建模

本阶段需要明确区分两类文档基线来源：

- 已保存正式文档：来自持久化 `doc output` / 历史版本存储，属于稳定版本语义，走 `docs.*`
- 未保存草稿：来自当前对话或当前写作流程中的 session / writing state，属于会话态 working draft，不纳入第一阶段 public MCP 工具

因此第一阶段建议：

- `docs.list_saved` / `docs.load_saved` 只覆盖“已保存正式文档”
- 当前对话中的未保存草稿继续作为主 Agent / 子 Agent 上下文模型的一部分管理
- 子 Agent 写作时若要延续未保存草稿，应从当前会话态草稿缓存或等价内部状态读取，再注入自己的 working context

这样做的原因：

- 草稿天然带有会话态、未定稿和可覆盖的语义，不适合作为稳定 remote 文档契约直接暴露
- 已保存正式文档具备稳定的 doc_type / doc_name / version 语义，适合走 `docs.*`
- 把草稿继续放在上下文状态层，可以避免把“当前会话临时产物”误建模成跨 agent 共享的公共知识

备选方案：

- 将未保存草稿也纳入 `docs.*`：短期看起来统一，但会混淆“正式版本”与“会话草稿”的边界

## Risks / Trade-offs

- [Risk] 与 `enable-skill-resource-runtime-access` 变更范围重叠，出现重复实现或冲突
  → Mitigation：将该变更视为 `skill.*` namespace 的子阶段实现基础，在任务拆分时明确“局部能力并入统一 MCP 运行时”

- [Risk] 只改 MCP server，不同步调整主 Agent 适配逻辑，会导致新协议落地后仍被旧 prompt / 旧工具假设牵制
  → Mitigation：将 Orchestrator 提示词、工具声明和执行协议适配纳入配套 change，同步推进

- [Risk] 如果 namespace 设计不够清晰，模型会不知道何时调用 `facts.*`、`skill.*`、`docs.*`
  → Mitigation：在 Sub-agent 执行规范中明确工具用途，并保持参数模型稳定、最小化

- [Risk] 统一协议后 prompt 注入内容膨胀
  → Mitigation：按来源分层缓存、按路径去重、限制单文件大小，并对 facts / docs / skill resources 使用不同裁剪策略

- [Risk] `skill.run_script(...)` 带来更高执行风险
  → Mitigation：严格绑定 Skill 根目录、限制 `.py`、设置超时、限制输出大小并记录 stderr 摘要

## Migration Plan

1. 新增 MCP Runtime 抽象层，定义 `facts.*`、`skill.*`、`docs.*` 三个 namespace 的接口、工具清单与返回格式
2. 按“公共工具集 / 内部工具集”划分暴露边界，优先让 `facts.list_modules`、`facts.get_module` 与 `docs.*` 成为标准 remote 工具，并保证公共契约不依赖隐式宿主上下文
3. 为现有 `fact_tools`、`saved_doc_tools` 和 Skill 资源运行时能力分别实现 MCP adapter，并完成“实现能力到新契约”的收敛
4. 调整主 Agent 与子 Agent 的上下文模型：主 Agent 仅保留 handoff 信息，子 Agent 在独立 working context 中按来源记录 facts / skill resources / docs 的已加载内容
5. 调整 `execute_skill` 创建的 Sub-agent 工具集，使 Skill 在执行时优先通过 MCP 访问资源
6. 对主 Agent 做最小必要适配，使其能够基于新的公共 MCP 工具名完成信息查询和委派，不等待完整的 Orchestrator 重构 change 才可切换
7. 调整 `write_document`，统一注入子 Agent 当前 working context 中通过 MCP 显式读取的 facts、skill resources 和 docs 基线内容
8. 完成切换后移除不再符合新契约的旧工具路径和旧假设
9. 保留现有 Skill 调度链路不变，先完成“资源访问统一”，再评估“调度协议统一”
10. 增加自动化测试和端到端回归，覆盖 remote server 连通性、工具分级、namespace 权限、结果注入、历史基线读取、会话草稿延续和 Skill 资源执行

回滚策略：

- 若 MCP Runtime 接入导致行为异常，可保留旧工具实现并切回原宿主工具链
- 由于第一阶段采用 adapter 模式，不涉及持久化格式迁移，回滚主要是切换调用入口

## Open Questions

- MCP Runtime 在第一阶段是以内嵌进程服务、轻量本地 server 还是纯 adapter API 形式存在，哪种最适合当前工程结构
- `facts.*` 是否需要在第一阶段就提供代码 / 原型的细粒度子能力，还是先保留模块主档与概览/详情接口
- `docs.*` 是否需要在第一阶段提供版本 diff 能力，还是先聚焦 list/load 两个读路径
- 后续若引入 `skills.invoke(...)`，应如何与现有 `execute_skill`、session 生命周期和 execution summary 对齐
- MCP Server 在第一阶段是作为后端进程内模块暴露，还是拆为独立 sidecar 进程；两者都应保持同一 Python SDK 实现路径
