## Why

当前 Agent 每轮对话都从零开始识别模块、重新加载项目事实，无法感知"正在写作中"的状态，导致多轮修改时模块识别错误、token 随对话轮数线性膨胀、上下文记忆失真。需要引入写作状态（WritingState）和文档驱动的多轮对话机制，使系统能像 DeepSeek/ChatGPT 一样支持连续多轮写作交互。

## What Changes

- **新增写作状态（WritingState）**：对话持有当前正在编写的模块、Skill、草稿内容和已保存版本信息，跨轮次复用，不再每轮重新识别
- **新增草稿机制**：LLM 生成结果先作为草稿保存在内存中，用户主动点击「保存」才落盘为正式版本（版本号递增）
- **新增快捷操作按钮**：文档生成后在消息末尾展示「保存」按钮，不阻塞对话继续输入
- **重构 stream_message 决策流程**：读取 writing_state → 轻量修改流程（沿用模块+草稿）或全量写作流程（加载项目事实）
- **新增历史版本作为写作基准**：首次定位到某模块时，若存在已保存版本，自动加载最新版作为写作基础
- **新增 LLM 意图判断**：判断用户是要修改当前文档、还是开始写新模块，驱动流程分支

## Capabilities

### New Capabilities

- `writing-state`: 对话级写作状态的维护、读写、重置，包括当前模块、草稿内容、已保存版本
- `draft-save`: 草稿与正式版本的分离机制：草稿驻留内存，用户显式保存才落盘并递增版本号
- `writing-intent`: 多轮写作意图识别，区分"修改当前文档"、"开始新模块"、"全部重写"三种意图
- `quick-actions`: 消息末尾的快捷操作按钮（非阻塞），首期支持「保存」操作

### Modified Capabilities

- `agent-core`: stream_message 流程重构，加入 writing_state 读取和分支逻辑
- `conversation-management`: ConversationInfo 新增 writing_state 字段
- `document-version-management`: 版本落盘时机从生成时变为用户显式保存时

## Impact

- `backend/agent/core.py`：stream_message 流程重构，新增 writing_state 相关逻辑
- `backend/agent/models.py`：新增 WritingState 模型，ConversationInfo 新增字段
- `backend/agent/conversation.py`：支持读写 writing_state
- 新增后端 API：`POST /conversations/{id}/save-draft`（草稿落盘接口）
- `frontend/src/lib/components/Chat.svelte`：新增快捷操作按钮渲染（非阻塞）
- 现有文档版本管理逻辑：落盘时机调整
