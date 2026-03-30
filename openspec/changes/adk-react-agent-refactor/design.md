## Context

当前 Agent 采用固定流水线（Fixed Pipeline）模式：`_select_skill()` → `_infer_context_needs()` → `_resolve_module()` → `_load_context()` → `_stream_llm_response()`。执行路径由代码硬编码，LLM 只在预设位置执行孤立的微任务，无法根据实际加载结果自我修正。

重构目标：以 Google ADK 为框架，DocumentAgent 作为 ReAct Agent，持有工具集，由 LLM 推理决定何时收集事实、何时写作，彻底移除固定执行路径。

## Goals / Non-Goals

**Goals:**
- 引入 Google ADK `LlmAgent`、`Tool` 替代手写流水线
- `DocumentAgent` 以 ReAct 循环运行，持有 `gather_facts`、`write_document`、`ask_user` 等工具，由 LLM 推理决定调用顺序
- `gather_facts` 工具内部以 ReAct 循环加载项目事实，支持向用户提问补充缺失信息
- WebSocket 流式协议和前端保持不变
- 修改流程：LLM 推理判断已有草稿，直接调用 `write_document`，不调用 `gather_facts`

**Non-Goals:**
- 前端代码变更
- `fact_info_service`、`doc_version_service` 的业务逻辑变更
- 新增文档类型 Skill
- 多 Agent 并行执行

## Decisions

### 决策 1：使用 Google ADK 而非手写 ReAct 循环

**选择**：Google ADK v1.x（`google-adk` + `litellm`）

**理由**：
- ADK 的 `LlmAgent` 原生支持 ReAct（Thought/Action/Observation 循环），无需手写工具调用解析
- `litellm` 统一适配 DeepSeek、QWen 等现有 LLM 配置，无需修改模型配置逻辑
- **替代方案**：手写 ReAct 循环 — 需要自己解析 Thought/Action 文本，维护成本高

### 决策 2：DocumentAgent 持有工具集，LLM 推理决定执行顺序

**结构**：
```
DocumentAgent (ReAct LlmAgent)
  工具集：
    gather_facts(skill_context_desc, user_intent)  → 内部 ReAct 循环，返回收集结果
    get_current_draft()                             → 读取当前对话的已有草稿（按需加载）
    write_document(skill_writing_inst, context, user_intent) → 生成文档，流式输出
    ask_user(question)                              → 向用户提问，等待回答
```

**执行路径由 LLM 推理决定，示例**：
```
# 新编写
Thought: 用户要写认证模块需求规格，需要先收集项目事实
Action: gather_facts(skill=requirements-spec, intent=...)
Observation: 已收集模块功能描述、用例列表...
Thought: 资料充足，开始写作
Action: write_document(...)

# 修改
Thought: 用户要修改第三节，当前对话有草稿，需要先读取
Action: get_current_draft()
Observation: [当前草稿全文]
Thought: 基于草稿执行修改
Action: write_document(context=草稿内容, 修改指令)
```

**理由**：
- 执行顺序由 LLM 推理决定，而非代码强制，符合 ReAct 原则
- 修改流程无需特殊路由逻辑，LLM 自然推理出无需收集
- `gather_facts` 内部封装 ReAct 循环，DocumentAgent 无需感知加载细节
- **替代方案**：SequentialAgent 强制 gather → write — 顺序由代码硬编码，部分违背 ReAct 原则，且修改流程需要额外路由机制

### 决策 3：Skill 描述两类信息，格式由作者自定

**约定**：Skill 描述文件须清晰表达两类信息：（1）所需项目事实类型；（2）写作规范。具体格式不作约束，`gather_facts` 工具接收 Skill 的上下文需求描述，`write_document` 工具接收 Skill 的写作指令部分。

**理由**：
- 自然语言描述比字段约束更灵活，LLM 可自主理解并决定加载策略
- 不约束段落名称和文件结构，Skill 作者可选择单文件或多文件组织方式

### 决策 4：草稿作为对话级可读资源，与项目事实分开管理

**草稿的性质**：草稿是 LLM 生成的写作产出，属于对话级状态（存储于 `ConversationInfo.writing_state`），与项目事实（人工维护、项目级共享）是两类不同的信息，独立管理。

**传递方式**：
- DocumentAgent 的系统提示包含轻量元信息：当前对话是否存在草稿（布尔值）
- 草稿全文通过 `get_current_draft()` 工具按需加载，不在启动时注入上下文
- DocumentAgent 的 LLM 自主判断何时调用 `get_current_draft()`（修改场景）或 `gather_facts()`（新编写场景）

**理由**：
- 与项目事实的分层按需加载逻辑保持一致，Agent 行为模式统一
- 草稿通常 2000-3000 tokens，按需加载避免无效上下文膨胀
- 新编写场景中 Agent 可自主决定是否参考历史草稿，灵活性更高

### 决策 5：工具间数据通过返回值传递，不依赖共享状态

**流转方式**：
```
gather_facts(...) → 返回 gathered_facts 字符串/结构
DocumentAgent 持有结果 → 传入 write_document(context=gathered_facts)
```

**理由**：工具返回值是 ReAct 循环的 Observation，DocumentAgent 自然持有并可传递给后续工具，无需额外的共享状态机制（Session State）

### 决策 6：WebSocket 流式事件适配 ADK Runner 事件

**适配层**（`main.py`）：将 ADK `Runner.run_async()` 产生的事件映射到现有 WebSocket 消息类型：

| ADK 事件 | WebSocket 消息类型 |
|---------|-----------------|
| `PartialResponseEvent` | `text` |
| `ToolCallEvent` | `status`（展示工具调用信息） |
| `FinalResponseEvent` | `done` |
| `ErrorEvent` | `error` |

现有前端无需修改。

## Risks / Trade-offs

- **ADK API 稳定性风险** → 固定版本（`google-adk==1.x.x`），不自动升级；ADK 当前为 v1.27.x，API 相对稳定
- **LiteLLM 配置迁移** → 现有 `llm_configs.json` 格式需映射到 LiteLLM 参数；现有配置管理 UI 保留，新增 LiteLLM 转换层
- **gather_facts 内部循环不终止** → 设置 `max_steps` 硬上限；Skill 上下文需求描述清晰时该问题极少出现
- **LLM 推理偏差** → 若 LLM 误判意图（如将新编写判断为修改），可能跳过必要的事实收集；通过清晰的系统提示词和用户反馈纠正
- **ADK Runner vs FastAPI 并发模型** → ADK Runner 是 async，与 FastAPI 兼容；需验证 WebSocket + ADK streaming 的背压处理

## Migration Plan

1. 在 `react-mode` 分支进行，不影响 `develop` 分支
2. 新增依赖：`google-adk`、`litellm`（`requirements.txt`）
3. 新建 `backend/agent/adk/` 目录，存放 ADK Agent 和 Tool 实现
4. 保留 `backend/agent/core.py` 接口签名（`stream_message`、`process_message`），内部替换为 ADK 实现
5. 更新现有 `skills/*/skill.md`，确保包含事实需求描述和写作规范两类信息
6. `main.py` WebSocket handler 适配 ADK Runner 事件流
7. 手动测试：新编写流程、修改流程、无匹配 Skill 的兜底响应

**回滚**：`develop` 分支保留完整旧实现，`react-mode` 分支独立迭代

## Open Questions

- `ask_user` 工具在 ADK ReAct 循环中如何实现：需要暂停循环等待用户 WebSocket 输入，涉及异步状态机设计，需要验证可行性
- `gather_facts` 作为工具调用时，其内部 ReAct 循环与外层 DocumentAgent ReAct 循环的嵌套方式在 ADK 中如何实现（工具函数 vs 嵌套 LlmAgent）
