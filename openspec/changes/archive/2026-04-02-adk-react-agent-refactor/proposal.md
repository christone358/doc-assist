## Why

当前 Agent 采用固定流水线（Fixed Pipeline）模式，执行路径由代码硬编码，LLM 只在预设位置执行孤立的微任务，无法根据实际加载结果自我修正。重构为 Google ADK + ReAct 模式，让 Agent 通过"思考-行动-观察"循环自主决策资料收集路径，提升文档生成的适应性和质量。

## What Changes

- **BREAKING** 移除 `AgentCore` 固定流水线实现，替换为基于 Google ADK 的主子 Agent 架构
- 新增 `FactGatheringAgent`：ReAct 模式子 Agent，负责根据 Skill 上下文需求逐层加载项目事实信息
- 新增 `WritingAgent`：单次调用子 Agent，接收已收集资料后生成文档
- 新增 `DocumentAgent`：主 Agent，负责意图理解、Skill 选择、协调两个子 Agent
- **BREAKING** `Skill.md` 结构扩展：新增 `## 上下文需求` 段落，描述 Skill 所需的项目事实信息（自然语言）
- 现有项目事实加载方法包装为 ADK Tool，供 `FactGatheringAgent` 调用
- `ConversationManager` 保持不变，WebSocket 协议保持不变，前端无需修改
- LLM 配置切换为 LiteLLM，统一支持 DeepSeek、QWen 等模型

## Capabilities

### New Capabilities

- `react-fact-gathering`: FactGatheringAgent 的 ReAct 循环行为——根据 Skill 描述的上下文需求，使用工具集逐层加载项目事实，支持向用户提问补充缺失信息
- `adk-agent-orchestration`: 主 Agent（DocumentAgent）协调 FactGatheringAgent 与 WritingAgent 的顺序执行，管理阶段间数据交接

### Modified Capabilities

- `agent-core`: Agent 核心从固定流水线改为 ADK-based 主子 Agent，意图识别、Skill 选择、流程控制逻辑全部重构
- `skill-framework`: Skill.md 新增 `## 上下文需求` 段落，供 FactGatheringAgent 读取并理解资料收集目标
- `skill-context-inference`: 原独立的上下文推断步骤融入 FactGatheringAgent 的 ReAct 循环，不再是单次 LLM 调用
- `structured-context-loading`: 项目事实分层加载方法重新包装为 ADK Tool，接口不变，调用方改为 ADK Agent

## Impact

- **`backend/agent/core.py`**：完全重写
- **`backend/agent/`**：新增 ADK Agent 模块文件
- **`backend/main.py`**：WebSocket handler 适配 ADK Runner 事件流
- **`backend/skills/*/skill.md`**：各 Skill 文件新增 `## 上下文需求` 段落
- **依赖新增**：`google-adk`，`litellm`
- **前端**：无变化
- **API 协议**：无变化（WebSocket 消息格式不变）
