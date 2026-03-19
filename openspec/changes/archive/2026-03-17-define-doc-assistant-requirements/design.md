## Context

NextAgent Doc Assistant 需要作为一个 MVP 产品，验证通过 AI Agent 调度多个文档编写 skill 的可行性。当前的挑战包括：
1. 需要定义清晰的 Agent-skill 通信协议
2. 需要设计可扩展但简洁的 skill 框架
3. 需要集成 LLM 以理解用户的文档编写需求
4. 需要构建 Web 界面提供用户友好的交互

系统的主要参与者：
- 用户：通过 Web UI 输入文档编写需求
- Web UI：前端应用，接收用户输入并展示结果
- Agent：核心引擎，理解需求并调度 skill
- Skill：特定类型文档的编写模块
- LLM：理解自然语言并辅助决策

## Goals / Non-Goals

**Goals:**
- 建立清晰的 Agent 核心架构，能够理解和调度 skill
- 定义 skill 的标准接口和框架，支持多种文档类型
- 设计 Agent 与 LLM 的集成方式（提示词工程、上下文管理）
- 定义 Web UI 与后端 Agent 的通信协议
- 制定 skill 扩展的规范和流程

**Non-Goals:**
- 实现具体的 skill 细节（留给 specs 和实现阶段）
- 从零开始构建前端框架（基于 open-webui 进行定制和扩展）
- 实现复杂的权限和多租户管理
- 优化性能和可扩展性（MVP 阶段）

## Decisions

**1. 架构分层：前端、Agent 服务、Skill 执行器**
- 前端（Web UI）：负责用户交互和结果展示
- Agent 服务：REST API 或 WebSocket 服务，处理请求调度和 skill 编排
- Skill 执行器：独立的 skill 进程或模块，执行具体的文档编写任务
- 选择该架构是为了清晰的职责划分和易于扩展

**2. Skill 框架采用插件模式**
- 每个 skill 实现标准接口：输入、处理、输出
- Skill manifest 文件（JSON/YAML）定义元数据：名称、支持的文档类型、参数要求
- Skill 通过目录自动发现和注册
- 替代方案（不采用）：动态脚本执行（安全风险高），单体架构（扩展性差）

**3. Agent 决策使用 LLM + 规则结合**
- LLM 理解用户自然语言，提取文档需求和关键信息
- Agent 使用简单规则匹配候选 skill（基于文档类型）
- 可选项：LLM 直接决策调度（复杂度更高，MVP 阶段不采用）
- 此方案平衡了灵活性和可控性

**4. Web UI 基于 Open WebUI 进行定制**
- Open WebUI：Svelte 前端框架，FastAPI 后端，WebSocket 实时通信
- 克隆并扩展 open-webui 项目，针对 NextAgent 的需求进行定制
- 优势：成熟的对话界面、实时推送基础设施、现成的组件库
- 避免重复造轮子，快速构建 MVP 前端

**5. Agent 与 Web UI 通信采用 REST API + WebSocket 混合**
- REST API：用于配置管理、Skill 查询等请求-响应式操作
- WebSocket：用于对话流、实时进度推送、多轮交互
- 此方案充分利用 open-webui 的基础设施，快速实现实时功能
- `DocumentRequest`: 用户需求（自然语言、文档类型、上下文）
- `SkillDefinition`: Skill 元数据（名称、输入参数、输出格式）
- `ExecutionTask`: 执行任务（skill ID、参数、状态）
- `DocumentOutput`: 最终生成的文档内容

## Risks / Trade-offs

### 功能相关风险

[风险] 自然语言理解准确度不足 → [缓解] 提供文档类型下拉选择，减少依赖 LLM 的部分；设计清晰的提示词减少歧义

[风险] Skill 执行失败导致整个流程中断 → [缓解] 设计清晰的错误处理和日志机制；允许用户修改 skill 参数重新执行

[风险] Skill 框架过度设计，MVP 阶段不需要 → [缓解] 采用最小化设计，只包含必要的扩展点；后续可迭代演进

[权衡] 使用 REST API vs WebSocket：REST API 更简单，WebSocket 更实时 → MVP 选择混合方式（REST API 用于配置，WebSocket 用于实时对话）

[权衡] LLM 决策 vs 规则匹配：LLM 更灵活，规则更可控 → MVP 选择混合方式（规则为主，LLM 辅助）

### 技术架构风险

**[风险] 前后端混合型技术栈的复杂性**

当前采用的是 Svelte + FastAPI 的混合型架构。架构评估如下：

| 维度 | 混合型(推荐) | 全Python | 全JavaScript |
|------|----------|---------|------------|
| 开发效率 | 8/10 | 7/10 | 6/10 |
| 性能 | 9/10 | 5/10 | 8/10 |
| 可维护性 | 7/10 | 8/10 | 7/10 |
| AI集成 | 9/10 | 10/10 | 4/10 |
| 前端体验 | 9/10 | 4/10 | 10/10 |
| 部署难度 | 6/10 | 8/10 | 8/10 |
| **综合评分** | **8.5/10** ✅ | 6/10 | 5/10 |

**选择理由：**
- Python 是 AI/LLM 生态主导，Svelte/FastAPI 的组合在 AI 应用中已被验证（如 open-webui）
- 充分利用两个生态的优势：Python 的 LLM SDK 丰富，JavaScript 的前端体验好
- 符合 MVP 阶段的目标：快速验证 Agent 逻辑（Python）+ 良好用户体验（Svelte）

**缓解方案：**
1. **部署架构**：使用 Docker 多阶段构建，前端打包后由 FastAPI 直接提供静态文件
2. **API 设计**：定义清晰的 OpenAPI 规范，前后端并行开发
3. **团队组织**：采用前后端分工，但通过 API 契约紧密协作

**后期演进路径：**
- 前端可独立迭代（Svelte）
- 后端可扩展成微服务架构
- 如需完全统一，可在 v2 阶段考虑切换（但不推荐）

## Implementation Approach

### 架构部署方案

**混合型架构的部署策略：**

```
前端构建 → FastAPI 服务端服务 → 用户浏览器
  ↓
Svelte 编译成静态文件
  ↓
FastAPI 在 /static 目录下提供静态文件
  ↓
WebSocket 和 REST API 通过同一个端口
  ↓
单一 Docker 镜像，简化部署
```

**多阶段 Docker 构建（推荐）：**

```dockerfile
# 阶段 1：构建前端
FROM node:18 as frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend .
RUN npm run build  # 输出到 build/ 目录

# 阶段 2：FastAPI 服务（整合前端）
FROM python:3.11
WORKDIR /app

# 复制构建好的前端静态文件
COPY --from=frontend-build /app/frontend/build ./static

# 复制后端代码
COPY backend ./backend
COPY requirements.txt .

# 安装依赖
RUN pip install -r requirements.txt

# FastAPI 配置，提供静态文件
# app.mount("/", StaticFiles(directory="static"), name="static")

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**发展阶段：**
1. **MVP 阶段（现在）**：前端和后端共享一个 Docker 镜像
2. **v1 阶段**：分离前后端镜像，用 docker-compose 编排
3. **v2+ 阶段**：微服务架构，Kubernetes 部署

### 开发流程

1. **第一阶段**：建立 Agent 服务框架和 skill 框架原型
2. **第二阶段**：LLM 集成（DeepSeek、QWen）和 Agent 核心逻辑
3. **第三阶段**：基于 open-webui 定制开发 Web UI（对话界面、配置管理、文档展示）
4. **第四阶段**：项目事实信息系统集成
5. **第五阶段**：完整流程测试、迭代优化和文档编写
6. **第六阶段**：Docker 镜像构建和部署验证

## Open Questions

- Skill 的执行应该是同步还是异步？
- 是否需要持久化存储历史执行记录？
- Open WebUI 的扩展点和定制深度如何最优？
