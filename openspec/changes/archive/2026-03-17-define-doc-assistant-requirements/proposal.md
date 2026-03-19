## Why

NextAgent Doc Assistant 是一个智能文档编写工具，旨在通过 AI Agent 自动调度多个专业文档编写 skill，为软件工程项目提供高效的文档生成能力。当前缺少对这一工具的完整需求规格定义，导致开发方向不明确。通过建立明确的需求规格，我们可以验证 MVP 产品设计的合理性，并确立后续实现的基准。

## What Changes

- 建立完整的需求规格文档，明确定义 Agent、skill 框架和 Web 界面的核心功能需求
- 定义多种文档类型 skill 的标准接口和能力要求
- 建立 Agent 的核心调度逻辑和 LLM 交互机制
- 建立 Agent 的精准修改能力和版本管理机制
- 设计 Web UI 与 Agent 的交互方式，支持新增编写和精准修改场景
- 确立 skill 扩展的规范，支持用户后续增加新的文档类型
- 建立文档输出和版本管理系统

## Capabilities

### New Capabilities
- `agent-core`: Agent 核心引擎，负责理解用户自然语言需求，调度合适的文档编写 skill，协调 skill 执行流程。支持新增编写和基于版本的精准修改模式，支持多轮对话交互
- `skill-framework`: 可扩展的 skill 框架，定义 skill 的标准接口、生命周期、参数格式，支持新 skill 的动态加载和注册
- `document-skills`: 文档编写Skill的标准规范和指南，定义各类型文档Skill应该如何编写和提供文档生成能力。系统初始化时可能不包含任何Skill，用户可以根据需要自行添加各种类型的文档编写Skill
- `web-ui`: Web 用户界面，提供自然语言输入、skill 选择、实时反馈、结果展示功能，支持多轮对话交互
- `llm-integration`: LLM 集成模块，处理用户自然语言理解、需求解析和 skill 调度决策，支持深度思考模式
- `skill-management`: Skill 管理系统，支持 skill 的注册、发现、版本管理和可用性查询
- `document-version-management`: 文档版本管理系统，支持文档的分类存储、版本管理（日期+版本号格式）、版本链条追踪和检索
- **`project-fact-information`**: 项目事实信息管理系统，以三层逐层披露方式组织软件工程项目的事实信息，包括清单层、核心信息层和设计开发层，支持Agent的只读查询和智能信息推荐
- **`conversation-management`**: 对话记录和管理系统，支持保存每次编写为对话记录、管理多个对话、记录对话详细过程、追踪对话与文档的关联、管理文档输出目录

### Modified Capabilities
<!-- 无现有 capabilities 需要修改 -->

## Impact

- 前端：基于 open-webui（Svelte + FastAPI）进行定制，实现对话界面、配置管理、文档展示、事实信息浏览
- 后端：需要建立 Agent 服务、skill 执行框架、版本管理系统、事实信息查询服务
- 架构：需要定义 Agent-skill 通信协议、数据模型、版本链条管理、事实信息的分层组织和检索
- 存储：需要按文档类型建立分类目录、支持版本号命名规范、组织和管理项目事实信息（三层结构）
- 数据维护：项目事实信息需要人工维护，建立维护流程和规范
- 文档：所有需求和设计文档需使用中文编写
