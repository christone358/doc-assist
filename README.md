# NextAgent Doc Assist

面向软件工程场景的 AI Agent 文档生产平台。项目通过主 Agent 编排、Skill 子 Agent 执行、MCP Runtime 统一资源访问，以及项目事实库支撑，实现需求文档、设计文档、用户手册等工程文档的生成、修订和版本追踪。

这个仓库不是单纯的聊天应用，而是围绕“事实驱动的文档编写”组织的一套完整工程系统，包含前端交互界面、后端 API、MCP Server、Skill 框架、项目事实管理和 LLM 配置管理。

## 项目定位

本项目用于解决软件项目文档编写中常见的几个问题：

- 文档编写严重依赖个人经验，风格和结构不稳定
- 文档内容容易脱离真实项目事实，后期难以维护
- 新文档、修订稿、历史版本之间缺少统一管理
- 不同类型文档需要不同写作规范，难以复用

对应地，NextAgent Doc Assist 提供了以下能力：

- 用对话方式发起文档编写和修订任务
- 由主 Agent 根据意图选择合适的 Skill
- 由 Skill 子 Agent 结合项目事实、历史文档和 Skill 资源完成写作
- 通过 MCP Runtime 提供统一的事实、原型、文档和 Skill 资源访问协议
- 对生成结果进行版本化保存，便于追踪和回看

## 当前能力

### 1. Agent 编排与对话式写作

- 支持多轮对话生成和迭代文档
- 支持会话创建、查询、重命名、删除和自动命名
- 支持保存草稿、基于历史版本继续修订
- 后端通过 REST API 和 WebSocket 提供会话与流式执行能力

### 2. Skill 驱动的专业写作

- `skills/` 目录下可安装或维护自定义文档 Skill
- 每个 Skill 通过 `SKILL.md` 描述适用场景、写作规范、资源和脚本
- 系统启动时自动发现 Skill，并在前端展示能力与资源

### 3. MCP Runtime / MCP Server

- 提供统一的运行时资源访问层
- 当前设计覆盖 `facts.*`、`prototypes.*`、`docs.*`、`artifacts.*`、`skill.*` 等能力边界
- 本地开发脚本支持独立启动 MCP Server，便于与 Agent 执行链路解耦

### 4. 项目事实库

- 通过 `project-facts/` 维护项目模块档案
- 以模块为聚合根组织项目知识，而不是堆积成松散文档
- 支持模块事实、原型资源和派生视图的管理方式
- 为文档生成提供更可追溯的事实来源

### 5. LLM 配置管理

- 支持在界面中配置、测试和切换模型
- 当前文档与实现中覆盖 DeepSeek、Qwen 和 Ollama 兼容模型接入方式
- 后端通过统一配置将模型参数转换为运行时可用形式

### 6. Web 可视化界面

- 前端提供对话、Skill、文档、事实信息、LLM 配置等页面
- 支持查看执行过程和流式响应
- 适合作为本地研发团队的文档工作台

## 系统架构

```text
用户
  |
  v
前端 Web UI（Svelte）
  |- 对话
  |- Skill 管理
  |- 文档浏览
  |- 事实信息浏览
  |- LLM 配置
  |
  v
后端 API / WebSocket（FastAPI）
  |- 会话管理
  |- Agent 运行入口
  |- 文档版本管理
  |- 项目事实接口
  |- LLM 配置接口
  |
  v
主 Agent / Orchestrator
  |- 意图识别
  |- Skill 选择
  |- 子 Agent 调度
  |
  +-----------------------------+
  |                             |
  v                             v
MCP Runtime                 Skill Sub-agent
  |- facts.*                   |- 读取 Skill 规则
  |- prototypes.*              |- 读取项目事实
  |- docs.*                    |- 读取历史文档
  |- artifacts.*               |- 生成和修订正文
  |- skill.*
  |
  v
工作区数据
  |- docs/
  |- project-facts/
  |- skills/
  |- doc_output/
  |- backend/llm_configs.json
```

更完整的架构说明可参考：

- `docs/整体架构说明.md`
- `docs/mcp-runtime-unified-protocol-design.md`
- `docs/整体架构图.md`
- `docs/高层架构图.md`

## 仓库结构

```text
.
├── backend/            # FastAPI 后端、Agent 编排、LLM 接入、MCP server 入口
├── frontend/           # Svelte 前端工作台
├── skills/             # 文档编写 Skill 及其资源
├── project-facts/      # 项目事实库（模块档案、原型、派生视图）
├── docs/               # 设计文档、使用文档和生成文档
├── doc_output/         # 文档导出相关脚本和输出目录
├── openspec/           # 规格设计与任务管理
├── scripts/            # 辅助脚本
├── start.sh            # 本地一键启动脚本
├── stop.sh             # 本地停止脚本
└── docker-compose.yml  # Docker Compose 部署定义
```

## 技术栈

- 前端：Svelte + Vite
- 后端：FastAPI + Pydantic
- Agent：Google ADK
- 模型接入：LiteLLM
- 协议与运行时：MCP Python SDK / FastMCP
- 测试：pytest、pytest-asyncio

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- 可用的 LLM API Key 或兼容服务地址

### 方式一：本地开发一键启动

```bash
./start.sh
```

该脚本会完成以下工作：

- 检查 Python 和 Node.js 版本
- 安装后端和前端依赖
- 启动后端服务
- 启动前端开发服务器
- 启动 MCP Server

默认端口：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- MCP：`http://localhost:8765/mcp`
- 后端 OpenAPI：`http://localhost:8000/docs`

也可以按需单独启动：

```bash
./start.sh backend
./start.sh frontend
./start.sh mcp
```

### 方式二：Docker Compose

```bash
docker compose up -d
```

当前 Compose 文件主要包含：

- `backend`
- `frontend`

如需在容器化环境中单独暴露 MCP Server，可在现有部署基础上继续扩展。

## 使用流程

### 1. 配置模型

进入前端的“LLM 配置”页面，添加至少一个可用模型并通过连接测试。

### 2. 准备项目事实

在 `project-facts/modules/` 中维护模块档案，在 `project-facts/prototypes/` 中放置原型资料，为文档生成提供事实基础。

### 3. 安装或维护 Skill

在 `skills/` 中放入目标文档 Skill。每个 Skill 至少应包含：

- `SKILL.md`
- 可选的 `scripts/`
- 可选的 `templates/`
- 可选的 `references/`

### 4. 发起文档任务

在前端对话页输入文档需求，例如：

```text
帮我为用户认证模块编写需求规格文档
```

系统会由主 Agent 识别意图、选择 Skill，并由子 Agent 结合事实库和上下文完成写作。

### 5. 查看结果与版本

- 在“文档”页查看已生成文档
- 在同一会话中继续修订
- 查看版本历史并追踪演进

## 关键目录说明

### `backend/`

- FastAPI 入口位于 `backend/main.py`
- LLM 配置与路由位于 `backend/llm/`
- MCP Server 启动入口位于 `backend/mcp_server.py`
- 文档版本与项目事实相关服务位于后端业务模块中

### `frontend/`

- 基于 Svelte 的前端应用
- 包含对话、事实信息、Skill 和 LLM 配置等页面

### `project-facts/`

- `modules/`：人工维护的模块档案
- `prototypes/`：原型资源目录
- `generated/`：系统派生视图，不建议人工直接维护

### `skills/`

- 自定义 Skill 的安装位置
- Skill 开发规范详见 `skills/README.md` 和 `skills/SKILL_DEVELOPMENT_GUIDE.md`

## 补充文档

- `docs/user-guide.md`：用户使用指南
- `docs/deployment.md`：部署与运维说明
- `docs/llm-config-guide.md`：LLM 配置指南
- `docs/project-facts-management-design.md`：项目事实管理设计
- `project-facts/README.md`：项目事实初始化与维护说明
- `skills/README.md`：Skill 结构与开发约定

## 适合的使用场景

- 软件项目需求文档和设计文档编写
- 用户手册、操作手册等结构化文档生产
- 基于既有项目事实的文档修订与重写
- 团队内部可扩展的 Skill 化文档生产工作台

## 当前状态说明

项目已经具备前后端交互、Agent 编排、MCP 支持、项目事实管理和模型配置等核心链路，适合作为持续演进中的工程化文档助手基础仓库使用。更细的功能边界和专题设计已沉淀在 `docs/` 与 `openspec/` 中，可继续作为后续公司内仓库演进的基础材料。
