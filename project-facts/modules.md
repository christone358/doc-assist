# 功能模块清单

NextAgent Doc Assistant 系统由以下核心模块组成。

---

## Agent 核心模块 {#mod-agent}

**描述**: 负责理解用户需求并调度合适的 Skill 执行，是系统的核心控制中枢。

**关键特性**:
- 自然语言理解和需求分类
- Skill 编排和调度
- 多轮对话上下文管理
- 结构化上下文加载（按模块、按词汇类型）

**关联资源**:
- 用例: [查看用例](usecases.md#mod-agent)
- 类包: [查看类包](classes.md#mod-agent)
- 接口: [查看接口](interfaces.md#mod-agent)

---

## Skill 框架模块 {#mod-skill}

**描述**: 定义 Skill 标准接口，管理 Skill 的注册、加载和执行生命周期。

**关键特性**:
- Skill 自动发现和加载
- skill.md 元信息解析
- Skill 能力边界管理
- 支持用户自定义扩展 Skill

**关联资源**:
- 用例: [查看用例](usecases.md#mod-skill)
- 类包: [查看类包](classes.md#mod-skill)

---

## LLM 集成模块 {#mod-llm}

**描述**: 集成 DeepSeek 和 QWen 模型，提供自然语言理解和文档生成能力。

**关键特性**:
- 多模型支持（DeepSeek-V3、QWen-max 等）
- 模型配置管理（API 地址、Token、参数）
- 流式输出（Server-Sent Events）
- 支持运行时切换模型

**关联资源**:
- 用例: [查看用例](usecases.md#mod-llm)
- 类包: [查看类包](classes.md#mod-llm)
- 接口: [查看接口](interfaces.md#mod-llm)

---

## 文档版本管理模块 {#mod-doc-ver}

**描述**: 管理 Agent 生成文档的版本控制和历史追踪。

**关键特性**:
- 语义版本号管理（vX.Y.Z）
- 日期目录结构（`docs/[type]/[name]/[date]/[version].md`）
- 版本链追踪
- 对话与文档关联

**关联资源**:
- 用例: [查看用例](usecases.md#mod-doc-ver)
- 类包: [查看类包](classes.md#mod-doc-ver)

---

## 项目事实信息模块 {#mod-facts}

**描述**: 存储和提供项目的结构化知识信息，支持 Agent 按模块精确查询。

**关键特性**:
- 星形模型存储（modules 为中心枢纽）
- 系统词汇表定义（modules/usecases/classes/interfaces/prototypes）
- 按模块 ID 过滤加载
- 人工维护、Agent 只读

**关联资源**:
- 用例: [查看用例](usecases.md#mod-facts)

---

## 对话管理模块 {#mod-conv}

**描述**: 记录和管理用户与 Agent 的对话历史，支持多对话和文档关联。

**关键特性**:
- 多轮对话上下文维护
- 对话持久化（含每轮输入、输出、Skill 调用、LLM 调用记录）
- 对话与生成文档的版本关联
- 对话状态管理（进行中/已完成）

**关联资源**:
- 用例: [查看用例](usecases.md#mod-conv)
- 类包: [查看类包](classes.md#mod-conv)

---

## Web UI 模块 {#mod-webui}

**描述**: 基于 Svelte 的 Web 对话界面，提供聊天式文档编写体验。

**关键特性**:
- 实时消息流（WebSocket / SSE）
- Skill 选择展示
- Token 用量显示
- 文档路径和版本展示

**关联资源**:
- 用例: [查看用例](usecases.md#mod-webui)
- 接口: [查看接口](interfaces.md#mod-webui)

---

## 模块依赖关系

```
MOD-WEBUI
    └── MOD-AGENT (REST API + WebSocket)
           ├── MOD-SKILL (Skill 调用)
           ├── MOD-LLM (语言理解和生成)
           ├── MOD-FACTS (项目事实查询)
           ├── MOD-DOC-VER (文档保存)
           └── MOD-CONV (对话记录)
```
