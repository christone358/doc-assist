## Why

当前 Agent 加载项目事实信息的方式是文件全量扫描 + 关键词模糊匹配，将命中文件全部塞入 system prompt，违背了分层披露的设计初衷，且随项目规模增长 context 不可控。同时 Skill 没有机制声明自己需要哪类上下文，Agent 无法按需精确加载，文档生成质量依赖 LLM 从大量无关信息中自行筛选。

## What Changes

- **重构 project-facts 存储结构**：从按层级分目录，改为星形模型（modules.md 为枢纽 + 各清单文件按模块标签组织），modules.md 同时承担项目地图和检索入口双重职责
- **建立系统词汇表**：定义 6 个标准上下文类型词汇（modules / usecases / classes / interfaces / prototypes / source），作为 Agent 和 Skill 之间的共同契约
- **Skill 上下文需求推断**：Agent 在选定 Skill 后，用 LLM 从 Skill 正文推断所需上下文类型（required / optional），Skill 作者无需显式声明，可选覆盖
- **精确模块定位**：Agent 从用户消息提取目标模块名，映射到模块 ID，按模块 ID 过滤清单文件，实现精确按需加载
- **两轮生成支持可选上下文**：LLM 第一轮生成时如判断需要可选上下文，通过内嵌标记触发 Agent 加载，执行第二轮生成
- **加载过程可观测**：status steps 展示每步上下文加载行为，日志记录推断结果和加载路径

## Capabilities

### New Capabilities
- `context-vocabulary`: 系统词汇表定义与 Agent 的词汇到路径映射逻辑
- `skill-context-inference`: Agent 用 LLM 从 Skill 正文推断 required/optional 上下文类型
- `module-entity-resolution`: 从用户消息提取目标模块名并映射到模块 ID
- `structured-context-loading`: 按词汇类型和模块 ID 精确加载项目事实信息

### Modified Capabilities
- `project-fact-information`: 存储结构从三层目录改为星形模型，查询方式从关键词扫描改为模块过滤
- `agent-core`: 消息处理流程新增上下文推断、模块定位、精确加载三个步骤，并支持两轮生成
- `skill-framework`: skill.md 新增可选的 `context_needs` YAML 字段用于覆盖推断结果

## Impact

- `project-facts/` 目录结构需要迁移重组（现有三层目录 → 星形平铺结构）
- `backend/agent/core.py`：`_recommend_facts()` 重构为多步骤加载流程
- `skills/*/skill.md`：现有 Skill 无需修改（推断方式向后兼容），可选新增 `context_needs` 字段
- 前端 status steps 新增上下文加载相关步骤展示
