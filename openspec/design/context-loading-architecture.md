# 项目事实信息分层加载架构设计

**版本**: 1.0.0
**日期**: 2026-03-17
**状态**: 设计完成，待实现

---

## 一、问题背景

### 当前的问题

系统目前存在两个相互关联的设计缺陷：

**问题一：上下文加载策略粗糙**

当前实现是文件扫描器：Agent 扫描 `project-facts/` 目录下的所有 `.md` 文件，用用户消息中的关键词做模糊匹配，将命中文件全部塞入 system prompt，由 LLM 自行从中查找所需内容。

这违背了设计初衷：
- 信息按层划分（layer1/layer2/layer3）的价值被绕过
- 一个模块的信息请求可能带入所有模块的信息
- Context 随项目规模线性增长，无法控制

**问题二：Skill 没有表达上下文需求的机制**

Skill 是独立可插拔的写作技能模块，每种文档类型对上下文的需求不同：
- 需求规格文档需要用例信息、功能模块描述
- 设计文档需要类包结构、接口清单、源代码
- 测试方案需要用例信息、功能描述

但 Skill 目前没有任何机制声明自己的上下文需求，Agent 无法知道某个 Skill 需要什么信息，只能全量加载。

### 核心设计目标

1. **分层披露**：从粗粒度到细粒度，从摘要到详情，按需逐步加载，避免 Context 过长
2. **模块精确定位**：给定"登录模块"，只加载登录模块的信息，不带入其他模块
3. **Skill 独立性**：Skill 声明上下文需求时不依赖具体路径和层级编号，在不同 Agent 中可复用
4. **低成本维护**：项目事实信息的维护方式对用户友好，不需要额外维护索引或目录文件
5. **决策可观测**：LLM 的每一步推断和加载决策对用户和开发者可见

---

## 二、项目事实信息的数据模型

### 六类知识要素及其特征

| 知识要素 | 数量规模 | 内容形态 | 与模块的关系 |
|---------|---------|---------|------------|
| 功能模块清单 | 中（20-100） | 树形层级描述 | 本身是树的节点，是其他要素的枢纽 |
| 用例清单 | 中（20-50） | 结构化文本 | 多对多（用例可跨模块） |
| 类包清单 | 大（50-200+） | 类和方法描述 | 每个类归属某模块 |
| 接口清单 | 大（50-300+） | 参数/响应规范 | 每个接口归属某模块 |
| 原型界面 | 中（按屏幕数） | HTML / 图片文件 | 每个页面对应某模块 |
| 源代码 | 极大 | 代码文件 | 代码库已有自己的目录结构 |

### 星形数据模型

功能模块是所有知识要素的**枢纽节点**：

```
           用例清单
              ▲
              │  属于
类包清单 ──▶ 模块 ◀── 接口清单
              │
              ▼
        原型界面 / 源代码
```

所有知识要素通过模块 ID 建立关联，不需要在条目之间维护交叉引用。

---

## 三、存储结构设计

### 目录结构

```
project-facts/
  modules.md          ← 模块树（主干 + 关联索引）
  usecases.md         ← 所有用例（含模块标签）
  classes.md          ← 所有类包（含模块标签）
  interfaces.md       ← 所有接口（含模块标签）
  prototypes/
    auth-login.html   ← 文件名 = 模块 ID
    payment-checkout.html
  README.md           ← 系统词汇表 + 格式规范
```

### modules.md 格式（主干文件）

modules.md 承担双重职责：对 LLM 提供项目全貌，对 Agent 作为检索入口。

```markdown
## 认证子系统 {#auth}

### 登录模块 {#auth-login}
负责用户认证和会话管理，支持密码登录和 OAuth。

关联资源:
- 用例: UC-001, UC-002
- 核心类: AuthService, PasswordValidator, SessionManager
- 接口: POST /api/auth/login, POST /api/auth/logout
- 原型: prototypes/auth-login.html
- 源码目录: src/auth/login/
```

每个模块条目声明它拥有哪些关联资源，是跨要素检索的唯一入口。**关系只在模块条目里维护一次，其他文件的条目只需写自身内容。**

### usecases.md / classes.md / interfaces.md 格式（清单文件）

每条条目包含：自身详细内容 + 模块归属标签。

```markdown
## UC-001 用户密码登录
- 模块: auth-login
- 参与者: 注册用户
- 摘要: 用户通过用户名和密码完成身份验证，获取会话 token

详细流程:
  主流程: 输入凭据 → 验证 → 返回 token
  异常: 密码错误三次锁定账户；账户未激活提示激活
```

条目内部采用**摘要 + 详情**两个层次，支持 Agent 选择性读取深度。

### 分层披露在文件内部体现

原始三层目录结构（layer1/layer2/layer3）被整合为：

| 原始层级 | 对应到新结构 | Agent 读取策略 |
|---------|------------|--------------|
| Layer 1 清单 | modules.md 的条目头部 + 摘要行 | 始终加载，全量 |
| Layer 2 详情 | usecases.md / classes.md 等文件的详细描述部分 | 按模块过滤后加载 |
| Layer 3 深度 | prototypes/ 目录；源码路径引用 | 按需加载，触发时才读取 |

---

## 四、系统词汇表

`project-facts/README.md` 中定义系统级知识类型词汇表，作为 Agent 和 Skill 之间的共同契约：

| 词汇 | 含义 | 数据来源 | 检索方式 |
|-----|------|---------|---------|
| `modules` | 功能模块树和模块详情 | modules.md | 全量加载（Layer 1），始终包含 |
| `usecases` | 用例信息 | usecases.md | 按 `模块: {id}` 标签过滤 |
| `classes` | 类包设计 | classes.md | 按 `模块: {id}` 标签过滤 |
| `interfaces` | 接口清单 | interfaces.md | 按 `模块: {id}` 标签过滤 |
| `prototypes` | 原型界面 | prototypes/{module-id}.* | 按模块 ID 定位文件 |
| `source` | 源代码 | 模块条目中声明的源码路径 | 读取声明路径下的文件 |

---

## 五、Skill 的上下文需求声明

### 设计原则

- Skill 使用系统词汇表中的词汇声明需求，**不写路径，不写层级编号**
- Skill 在不同项目的 Agent 中可复用，只要 Agent 实现了词汇表的映射
- 声明方式采用自然语言，降低出错概率

### Skill 正文写法（推荐方式）

Skill 作者在正文中自然描述所需信息，Agent 用 LLM 从中推断：

```markdown
## 工作原理

本 Skill 在编写需求规格文档时，需要读取目标模块的
**用例信息**和**功能模块描述**作为基础输入，
确保文档内容与项目实际保持一致。

当文档需要描述具体操作步骤时，可以进一步
读取**功能原型界面**来增强对交互细节的理解。
涉及接口规范描述时，可参考**接口清单**。
```

### 推断机制

Agent 在选定 Skill 后，执行一次轻量 LLM 调用：

**输入**: Skill 全文 + 系统词汇表
**输出格式**:
```
REQUIRED: modules, usecases
OPTIONAL: prototypes, interfaces
```

**推断规则**: 描述中出现"需要 X"、"基于 X"等必要性表述 → required；出现"可以参考 X"、"如有 X 则"等条件性表述 → optional。

### 兜底策略

- 推断失败时：默认 required=[modules]，optional=[usecases, interfaces, prototypes]
- Skill 作者如需精确控制，可在 skill.md 的 YAML front matter 中覆盖：

```yaml
context_needs:
  required: [modules, usecases]
  optional: [prototypes]
```

显式声明优先于推断结果。

---

## 六、Agent 的执行流程

### 完整流程

```
用户消息
   │
   ▼  Step 1: 意图理解
   │  提取 entity（目标模块名）和 task_type（文档类型）
   │  → status: "正在理解您的需求..."
   │
   ▼  Step 2: Skill 选择
   │  LLM 读取所有 Skill 的 name + description，选择最匹配的
   │  → status: "选择 Skill: {skill.name}，原因：{reason}"
   │
   ▼  Step 3: 上下文需求推断
   │  LLM 读取 Skill 全文 + 词汇表，推断 required / optional
   │  → status: "分析上下文需求..."（日志记录推断结果）
   │
   ▼  Step 4: 模块定位
   │  从 modules.md 中匹配 entity → 得到模块 ID
   │  → 若无精确匹配，用 LLM 做语义匹配
   │
   ▼  Step 5: 加载必需上下文
   │  按 required 列表逐项加载，按模块 ID 过滤
   │  → status: "加载项目上下文：{加载了什么}({条数}条)"
   │
   ▼  Step 6: LLM 第一轮生成
   │  生成文档内容
   │  如需可选上下文，在输出中声明：<!--needs: prototypes-->
   │  → status: "正在生成响应..."
   │
   ├── 不需要更多上下文 ──────────────────────────▶ 输出文档
   │
   ▼  Step 7: 按需加载可选上下文（触发时）
      Agent 加载声明的可选上下文
      → status: "补充上下文：{加载了什么}"
      → LLM 第二轮生成，完善文档
```

### 模块定位策略

```
用户说的词          匹配策略
─────────────────────────────────────────────────
"登录模块"    →    精确匹配 modules.md 中的模块名称
"用户认证"    →    LLM 语义匹配（查找最相关的模块 ID）
"auth-login"  →    精确匹配模块 ID
```

modules.md 中的模块条目可以补充别名字段以提升匹配精度：

```markdown
### 登录模块 {#auth-login}
别名: 用户登录, 用户认证, 登录功能
```

### 上下文加载的精确查询

| 词汇 | Agent 执行的查询 |
|-----|----------------|
| modules | 读取 modules.md 全文（始终执行） |
| usecases | 读取 usecases.md，过滤 `模块: auth-login` 的所有条目 |
| classes | 读取 classes.md，过滤 `模块: auth-login` 的所有条目 |
| interfaces | 读取 interfaces.md，过滤 `模块: auth-login` 的所有条目 |
| prototypes | 加载 `prototypes/auth-login.*` 文件 |
| source | 读取模块条目中 `源码目录:` 字段声明的路径 |

---

## 七、决策可观测性设计

### 对用户可见（Status Steps）

```
✓ 正在理解您的需求...
✓ 选择 Skill: 需求规格文档（用例类型匹配）
✓ 加载项目上下文：模块描述、用例信息(3条)
✓ 补充上下文：功能原型界面          ← 仅在 Step 7 触发时出现
⏳ 正在生成响应...
```

### 对开发者可见（日志）

```
[context-inference] skill=write-requirements
  inferred: required=[modules, usecases], optional=[prototypes, interfaces]
  source: LLM inference from skill content

[context-loading] entity=auth-login
  modules.md → found: auth-login (认证子系统/登录模块)
  usecases.md → filtered: 3 items (UC-001, UC-002, UC-003)

[context-optional] triggered by LLM: needs=prototypes
  prototypes/auth-login.html → loaded (42KB)
```

---

## 八、演进路径

### MVP 阶段（当前目标）

- 用户手动编辑 `modules.md`、`usecases.md` 等清单文件
- Agent 用 LLM 推断 Skill 的上下文需求
- Agent 用关键词过滤实现"按模块加载"
- Status steps 展示加载过程

### 工程化阶段（未来）

- 管理 UI 替代手动编辑文件（数据存入数据库，同步导出 Markdown）
- Agent 对 modules.md 建立内存索引，加速模块 ID 查找
- 支持更复杂的多模块、跨子系统文档生成

**关键约束**: 工程化阶段的管理系统只是把"手动编辑文件"替换为"通过 UI 编辑"，Agent 的检索逻辑和 Skill 的声明方式**不需要修改**。

---

## 九、待解决的问题

以下问题在本次设计中识别，留待后续讨论：

| 问题 | 优先级 | 说明 |
|-----|-------|------|
| entity 提取准确性 | 高 | 从用户消息中提取模块名，映射到模块 ID，是最容易出错的一环 |
| 多模块文档 | 中 | 用户要写跨多个模块的文档时，上下文加载策略需要扩展 |
| 大文件过滤效率 | 中 | usecases.md 条目多时，过滤操作的性能和 context 长度控制 |
| Skill 推断准确性验证 | 中 | 如何测试和验证 LLM 推断结果的正确性 |
| 源代码加载边界 | 低 | 源代码文件可能很大，需要设计截断和摘要策略 |
