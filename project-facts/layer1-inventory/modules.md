# 功能模块清单

## 系统概述
NextAgent Doc Assistant 系统由以下核心模块组成。

## 核心模块

### 1. Agent 核心模块 (MOD-AGENT)
- **简介**: 负责理解用户需求并调度合适的Skill执行
- **关键特性**: 自然语言理解、需求分类、Skill编排、多轮对话
- **技术栈**: Python, FastAPI, WebSocket

### 2. Skill 框架模块 (MOD-SKILL)
- **简介**: 定义Skill标准接口，管理Skill的注册和执行
- **关键特性**: Skill自动发现、元信息解析、生命周期管理
- **技术栈**: Python

### 3. LLM 集成模块 (MOD-LLM)
- **简介**: 集成DeepSeek和QWen模型，提供自然语言理解能力
- **关键特性**: 多模型支持、配置管理、自动降级
- **技术栈**: Python, OpenAI SDK

### 4. 文档版本管理模块 (MOD-DOC-VER)
- **简介**: 管理生成文档的版本控制和历史追踪
- **关键特性**: 语义版本、日期目录结构、版本链追踪
- **技术栈**: Python, 文件系统

### 5. 项目事实信息模块 (MOD-FACTS)
- **简介**: 存储和查询项目的三层事实信息
- **关键特性**: 三层结构、只读Agent访问、智能推荐
- **技术栈**: Python, JSON/Markdown

### 6. 对话管理模块 (MOD-CONV)
- **简介**: 记录和管理用户与Agent的对话历史
- **关键特性**: 多轮对话、对话持久化、文档关联
- **技术栈**: Python, JSON

### 7. Web UI 模块 (MOD-WEBUI)
- **简介**: 基于open-webui的Web对话界面
- **关键特性**: 实时消息、Skill展示、文档路径显示
- **技术栈**: Svelte, TypeScript, WebSocket

## 模块依赖关系

```
MOD-WEBUI
    └── MOD-AGENT (REST API + WebSocket)
           ├── MOD-SKILL (Skill调用)
           ├── MOD-LLM (语言理解)
           ├── MOD-FACTS (事实查询)
           ├── MOD-DOC-VER (文档保存)
           └── MOD-CONV (对话记录)
```
