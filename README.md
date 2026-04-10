# NextAgent Doc Assistant

一个基于 AI Agent 的智能文档编写工具，通过调度多个专业文档编写 Skill，为软件工程项目提供高效的文档生成能力。

## 项目结构

```
project/
├── backend/          # Python FastAPI 后端服务
├── frontend/         # Svelte Web UI 前端
├── skills/           # 文档编写 Skill 模块（用户自定义）
├── docs/             # 生成的项目文档
├── project-facts/    # 项目事实信息库（modules / prototypes / generated）
└── openspec/         # 规格定义（需求、设计、任务）
```

## 核心特性

- **Agent 核心引擎**: 理解用户需求，自动调度合适的 Skill
- **可扩展 Skill 框架**: 支持用户自定义各类型文档编写 Skill
- **LLM 集成**: 支持 DeepSeek 和 QWen 模型
- **Web 对话界面**: 基于 open-webui 构建，支持多轮交互
- **版本管理**: 自动版本控制和文档历史追踪
- **项目事实信息**: 基于模块档案聚合的项目知识库，支持智能推荐

## 快速开始

*待实现*

## 文档

所有项目文档和规格定义位于 `openspec/` 目录。
