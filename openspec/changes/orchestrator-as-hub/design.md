# Orchestrator as Hub — 架构设计蓝本

> 本文档记录主 Agent 演进为"编排中枢"的完整设计思路。
> 当前状态：设计探索阶段，尚未实施。各维度可独立推进为独立 change。

---

## 现状与目标

### 当前模型：路由器

```
用户输入 ──→ 分类 ──→ 选 Skill ──→ execute_skill ──→ 摘要字符串 ──→ 完成
```

- 单任务映射：一次输入对应一次 execute_skill
- 结果黑盒：Orchestrator 只看到文字摘要
- 规则驱动：instruction 里的 if-else 决策树替代推理
- 静态工具：工具列表编译时固定

### 目标模型：编排中枢

```
用户输入
    │
    ▼
  规划层（Plan）
    → 目标分解：单任务 or 多步任务？
    → 依赖分析：串行 / 并行 / 条件？
    │
    ▼
  执行层（Execute）
    → 调度 Sub-agent（doc_worker_*）
    → 实时感知执行状态
    │
    ▼
  感知层（Observe）
    → 读取结构化执行结果
    → 更新任务状态图
    → 决定下一步：继续 / 澄清 / 重试 / 完成
```

---

## 维度一：目标分解能力

### 问题

当前 Orchestrator 思维模型是单任务映射，面对复杂意图（如"把认证模块的文档全套做了"）会崩溃——要么选一个 Skill 忽略其他，要么陷入询问循环。

### 任务依赖关系分类

```
用户目标
   │
   ├── 可单次完成？ → 直接 execute_skill
   │
   └── 需要分解？
         │
         ├── 串行依赖：A 的输出是 B 的输入
         │     示例：需求规格 → 设计方案
         │
         ├── 并行独立：A 和 B 互不依赖
         │     示例：为三个模块分别写用户手册
         │
         └── 条件依赖：B 是否执行取决于 A 的结果
               示例：需求规格里有接口定义 → 再写接口文档
```

### 三种设计思路

**思路 A：规划后执行（Plan-then-Execute）**

Orchestrator 先生成执行计划，用户确认后顺序执行：

```
用户: "把认证模块的文档全套做了"

Orchestrator 规划:
  Step 1: write-requirements（需求规格）
  Step 2: write-design（设计方案，依赖 Step 1）
  Step 3: write-test-plan（测试方案，依赖 Step 1）

→ 向用户展示计划 → 确认后逐步执行
→ 后续步骤的 user_intent 注入前步摘要
```

计划是**动态生成**的，不是硬编码。Orchestrator 根据用户意图 + Skill 能力图推导出计划。

**思路 B：增量式分解（Iterative Decomposition）**

不提前规划全部，每次执行完后重新评估：

```
round 1 → execute_skill(write-requirements)
round 2 → Orchestrator: 还需要 write-design？→ 询问用户
round 3 → execute_skill(write-design, 基于上轮需求规格)
```

更贴近对话节奏，适合用户意图本身也在演化的场景。

**思路 C：目标图（Goal Graph）**

Orchestrator 维护目标节点图，执行后更新节点状态：

```
Goal: 完整文档套件
  ├── [done] 需求规格 ✓
  ├── [pending] 设计方案（依赖: 需求规格）
  └── [pending] 测试方案（依赖: 需求规格）
```

最强大但最复杂，适合长期多文档项目场景。

### 推荐实施路径

短期：思路 A（规划后执行），不需要改变底层架构，只需扩展 Orchestrator instruction 和 context。
长期：思路 C（目标图），结合结构化 Sub-agent 返回值实现。

---

## 维度二：任务状态感知

### 问题

Orchestrator 对 Sub-agent 执行过程完全不知情，只拿到一个不稳定的自由文本摘要。多轮对话中，Orchestrator 的"记忆"极其稀薄。

### 状态感知的两个层次

```
层次 1：执行结果状态
  → 写了什么文档？字数？哪个版本？
  → 用了哪个草稿作为基础？

层次 2：执行过程状态
  → 加载了哪些事实？（影响下次是否需要重新加载）
  → 遇到了什么问题？（影响 Orchestrator 是否需要介入）
  → 用户在执行中做了哪些澄清？（影响后续轮次的上下文）
```

### 设计：结构化执行结果

将 `ctx.last_skill_execution_summary: str` 升级为：

```python
@dataclass
class SkillExecutionResult:
    skill_id: str
    status: Literal[
        "completed",
        "failed_technical",
        "failed_no_target",
        "failed_no_facts",
        "aborted_by_user",
        "completed_partial",
    ]

    # 写作结果
    doc_type: str
    doc_name: str
    word_count: int
    draft_version: str          # "new" | "from_cache" | "from_saved_v1.0"

    # 事实加载记录
    facts_loaded: List[str]     # ["modules:mod-auth", "usecases:uc-login"]

    # 执行中的澄清记录
    clarifications: List[dict]  # [{"question": "...", "answer": "..."}]

    # 失败信息
    failure_reason: Optional[str]
    retry_hint: Optional[str]

    # 自然语言摘要（供向用户汇报）
    summary: str
```

### 设计：执行历史持久化

```python
# ConversationContext 扩展
execution_history: List[SkillExecutionResult] = field(default_factory=list)
```

每次 execute_skill 完成后追加，跨轮传递。Orchestrator 在决策时能访问完整历史。

### 衍生优化：事实复用

若 Orchestrator 知道"上次写需求规格时已加载了 mod-auth 的 usecases 和 classes"，下次写设计文档时可告知 Sub-agent"上次事实仍有效，可直接使用"，避免重复加载。

---

## 维度三：动态工具发现

### 问题

工具列表在构建时固定，用户能做什么完全取决于开发者预先想到了什么。用户提出没有对应工具的需求时，系统必然失败。

### 工具发现的两个层面

```
层面 1：Skill 即工具（当前已有雏形）
  → 每个 Skill 是可调用的 Sub-agent
  → 新增 Skill = 自动扩展 Orchestrator 能力
  → ✅ 当前架构已支持

层面 2：能力组合（尚未支持）
  → 多个 Skill 组合成更大的能力
  → Skill 之间的协议（输出作为另一个的输入）
  → ❌ 当前不支持
```

### 设计：能力注册协议

扩展 skill.md frontmatter，声明能力接口：

```yaml
---
id: write-requirements
name: 需求规格文档编写
type: requirements
capability:
  triggers:
    - 用户要求编写需求规格
    - 用户提到功能需求、用户故事、验收标准
  requires:
    - 写作目标模块名
  produces:
    - requirements 类型文档
  enables:
    - write-design（基于需求规格）
    - write-test-plan（基于需求规格）
---
```

Orchestrator 不只知道"有哪些 Skill"，还知道它们之间的关系——这是实现目标分解（维度一）的基础数据结构。

### 设计：Skill 自注册（长期目标）

Orchestrator 在每轮决策时动态查询可用能力，而不依赖编译时固定的工具列表：

```
Orchestrator 决策循环:
  1. 读取用户意图
  2. 查询 SkillRegistry（动态，可热加载）
  3. 匹配能力
  4. 执行
```

新增 Skill 后 Orchestrator 无需重启即可感知——真正的插件化架构。

---

## 维度四：失败重试与策略切换

### 问题

当前错误处理：`except Exception: return f"Skill 执行出错：{e}"` —— 没有重试，没有降级，没有策略切换。更隐蔽的是语义失败（未抛异常但结果不对），系统完全无法感知。

### 失败类型分类与对应策略

```
失败类型
│
├── 技术失败（明确的错误）
│     ├── LLM API 超时 / 限流     → 自动重试 1 次，静默处理
│     ├── 工具调用异常             → 降级后重试
│     └── Session 异常             → 重建 session 后重试
│
├── 语义失败（执行了但结果不对）
│     ├── 无法定位写作目标         → 上报 Orchestrator，重新澄清后重试
│     ├── 事实库信息不足           → 告知用户，询问是否继续
│     └── 用户拒绝回答 ask_user   → 终止，告知原因
│
└── 策略失败（选错了工具 / Skill）
      ├── Orchestrator 选了不合适的 Skill → 用户反馈 + 重新选择
      └── 用户说"这不是我想要的"          → 重新理解意图
```

### 设计：Orchestrator 失败响应矩阵

| 失败状态 | Orchestrator 行为 |
|---|---|
| `failed_technical`（API 超时） | 自动重试 1 次；仍失败则告知用户稍后再试 |
| `failed_no_target`（无法定位目标） | 向用户澄清写作目标，用新 user_intent 重试 |
| `failed_no_facts`（事实库不足） | 告知用户缺少什么信息，询问是否无事实直接写 |
| `aborted_by_user` | 告知用户已中止，询问下一步 |
| `completed_partial` | 向用户展示完成了什么，询问是否继续 |

### 设计：策略切换

```
用户反馈 → Orchestrator 分析
  │
  ├── "写得太简单了"
  │     → 同一 Skill，enriched user_intent，重试
  │
  ├── "方向不对，我要的是 X"
  │     → 重新理解意图，可能换 Skill
  │
  └── "这个模块不对"
        → 修正写作目标，重试
```

把"对话中的错误修正"纳入 Orchestrator 编排逻辑，而不是当作全新对话处理。

---

## 维度五：用户意图的动态澄清

### 问题

当前模型是预执行阻塞式：执行前把所有歧义问完，导致要么过度澄清（频繁打断）要么过度自信（带错误假设执行）。

### 意图不清晰的两种类型

```
类型 A：执行前就能判断的模糊
  → "帮我写文档"（不知道写什么模块）
  → 必须在执行前澄清，否则无法开始
  → 当前处理正确

类型 B：执行过程中才能判断的模糊
  → "把认证模块的文档完善一下"
     → 执行前看似清晰
     → 但"完善"的含义取决于当前文档状态
     → 只有 Sub-agent 加载后才知道
  → 当前处理方式：Sub-agent 自行决定（可能错误）
```

还有第三类：**意图在对话中演化**——用户通过看到结果才知道自己真正想要什么。

### 设计：两阶段澄清模型

```
阶段 1：Orchestrator 层澄清（执行前）
  → 只澄清"不澄清就无法选 Skill 或确定写作目标"的歧义
  → 标准：影响执行方向的，才需要执行前问

阶段 2：Sub-agent 层澄清（执行中）
  → 澄清执行细节中的歧义
  → 找到多个匹配的模块 → 问用户选哪个
  → 历史草稿存在 → 询问是否以此为基础

原则：阶段 1 不做阶段 2 的事
```

### 设计：渐进式意图精化

行动优先，通过结果反馈精化意图，而非全在执行前问完：

```
用户: "帮我写认证模块的文档"

Orchestrator:
  → 意图 = 写文档，目标 = 认证模块，类型 = 未知
  → 不问类型，默认选 write-requirements（最常见起点）
  → 执行，生成需求规格草稿

用户: "这个很好，但我更需要设计方案"

Orchestrator:
  → 理解: 用户想要 write-design
  → 不重新问目标，直接执行（目标已知）
```

### 设计：意图状态对象

把用户意图建模为带确认状态的结构体：

```python
@dataclass
class IntentState:
    target_module: Optional[str]     # None = 未知
    doc_type: Optional[str]          # None = 未知，已知但未确认用 Optional
    modification_base: Optional[str] # "cache" | "saved" | "new" | None
    scope: Optional[str]             # 写作范围说明

    # 确认状态
    confirmed_fields: Set[str]       # 已被用户确认的字段
    assumed_fields: Set[str]         # Orchestrator 假设的字段（待确认）
```

Orchestrator 带着"部分确认的意图状态"执行，Sub-agent 在执行中补全未知字段，完成后将完整状态回传，成为下一轮的起点。

---

## 综合：三件基础工作

实现上述五个维度，最终需要三件事：

```
1. 结构化的 Sub-agent 返回值
   → SkillExecutionResult 替代自由文本摘要
   → 使 Orchestrator 能真正"感知"执行结果

2. Orchestrator 维护对话级任务状态
   → IntentState + execution_history + goal_graph
   → 使 Orchestrator 能跨轮推理，而非每轮从零开始

3. 更强的基础模型
   → 思考型模型（DeepSeek-R1、QwQ 等）
   → 使 Orchestrator 能真正推理，而非靠规则约束
   → 由 orchestrator-model-upgrade change 实现
```

前两件通过代码演进，第三件通过模型升级。三者缺一不可，但可以独立推进——即使模型没有升级，结构化返回值和状态管理也能提升系统的可靠性和可观测性。

---

## 实施优先级建议

| 优先级 | 维度 | 关键 change | 前置条件 |
|---|---|---|---|
| P0 | 模型升级 | orchestrator-model-upgrade | 无 |
| P1 | 结构化执行结果 | skill-execution-result | 无 |
| P1 | 失败重试策略 | orchestrator-failure-recovery | skill-execution-result |
| P2 | 两阶段澄清模型 | orchestrator-intent-refinement | 模型升级 |
| P2 | 目标分解（规划后执行） | orchestrator-task-planning | 模型升级 + 结构化结果 |
| P3 | 能力注册协议 | skill-capability-registry | orchestrator-task-planning |
| P3 | 意图状态对象 | orchestrator-intent-state | 两阶段澄清 + 结构化结果 |
