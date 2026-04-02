# 对话展示与过程信息分层设计

更新时间：2026-04-01

## 1. 目标

本设计用于统一 NextAgent Doc Assistant 在对话页面中的信息展示逻辑，明确：

- 有哪些信息对象
- 每类信息应该展示在左侧还是右侧
- 哪些信息是正式结果，哪些信息是过程观测
- 哪些信息可以双显，哪些信息必须单点展示

本设计重点解决的问题：

- 正式正文和过程性文本混淆
- 思考、工具调用、提问、总结、摘要展示位置不一致
- 写作场景下附属产物与正式文档正文边界不清

## 2. 总体原则

### 2.1 左右分工

- 左侧是“结果区”。
  面向用户消费、回复、保存、继续编辑。
- 右侧是“过程区”。
  面向观察 Agent 如何工作，不承担正式交付。

### 2.2 三层信息模型

- 主结果层：真正交付给用户的正式内容
- 过程观测层：思考、工具调用、状态推进、提问链路
- 附属产物层：写作总结、写作摘要、保存结果、版本元数据

### 2.3 单一主展示位

同一类信息必须有唯一主展示位：

- 正式正文主展示位在左侧
- 完整过程主展示位在右侧
- 附属产物主展示位在左侧正文下方

如果需要双显：

- 左侧只能展示精简镜像
- 右侧保留完整过程

## 3. 信息对象定义

### 3.1 用户输入类

- `user_message`
  用户发送的自然语言输入

### 3.2 正式结果类

- `text`
  正式回答正文，或正式文档正文
- `document`
  与当前正式输出关联的文档路径、版本、保存元信息
- `error`
  当前轮对用户可见的执行失败信息

### 3.3 过程观测类

- `thinking`
  Agent 的过程性思考文本
- `status(tool_call)`
  工具调用开始
- `status(detail)`
  工具返回结果摘要
- `skill_start`
  主 Agent 选择 skill
- `subagent_start`
  子 Agent 开始执行
- `done`
  一轮执行结束、usage 等收尾信息

### 3.4 交互控制类

- `question`
  Agent 面向用户发出的澄清问题

### 3.5 写作附属产物类

- `reflection`
  写作总结，面向用户解释本轮执行与检查结果
- `summary`
  写作摘要，面向系统上下文压缩，但允许用户查看

## 4. 展示策略

### 4.1 左侧主对话区

#### 4.1.1 正式对话气泡

左侧正式气泡只允许承载以下内容：

- `text`
- `question`
- `error`

禁止进入正式气泡的内容：

- `thinking`
- `status(tool_call/detail)`
- `skill_start`
- `subagent_start`
- `reflection`
- `summary`

#### 4.1.2 思考面板

在 assistant 正式气泡上方允许存在一个折叠的“思考过程”面板。

用途：

- 作为右侧完整 thinking 的左侧精简镜像
- 给用户一个轻量的“系统在做什么”感知

约束：

- 仅展示 `thinking`
- 不展示工具调用链
- 不展示提问
- 不展示写作总结和写作摘要

#### 4.1.3 附属产物区

在 assistant 正式气泡下方允许展示独立折叠区域：

- 写作总结：`reflection`
- 写作摘要：`summary`
- 保存结果、版本信息、文档路径：`document` / meta

这些区域不是正文的一部分，也不应参与正文持久化。

### 4.2 右侧过程明细区

右侧是完整过程时间线。

建议承载：

- `thinking`
- `skill_start`
- `subagent_start`
- `status(tool_call)`
- `status(detail)`
- `question`
- `reflection`
- `summary`
- `done`

右侧不承载：

- 正式正文 `text`
- 用户最终阅读版文档内容

## 5. 关键边界规则

### 5.1 正式正文边界

只有真正交付给用户的内容才属于 `text`。

以下内容不得映射为 `text`：

- “我将先…”
- “现在让我获取…”
- “接下来我会…”
- 工具调用回显
- 写作总结
- 写作摘要
- 面向用户的澄清提问

### 5.2 提问边界

所有面向用户的提问都必须作为 `question` 事件发出。

禁止出现在：

- `thinking`
- `text`
- `reflection`
- `summary`

典型错误例子：

- “为了准确编写，我需要了解…”
- “请问这个模块的具体标识符是什么？”

这些内容如果面向用户，就必须进入独立提问气泡。

### 5.3 写作附属产物边界

`reflection` 和 `summary` 满足以下规则：

- 可被用户查看
- 不属于正式正文
- 不进入正式文档持久化
- 不与 `text` 混流

### 5.4 工具调用边界

工具调用和工具结果属于执行观测信息：

- 右侧展示
- 左侧不直接展示

## 6. 生命周期示例

### 6.1 普通问答

1. 用户发送问题
2. Agent 输出 `thinking`
3. Agent 输出 `text`
4. Agent 输出 `done`

展示：

- 左侧：思考面板 + 正式回答气泡
- 右侧：thinking + done

### 6.2 写作任务

1. 用户发送写作请求
2. 主 Agent 输出 `thinking`
3. 主 Agent 选择 `skill_start`
4. 子 Agent 输出 `subagent_start`
5. 子 Agent 输出 `status(tool_call/detail)`
6. `write_document` 输出 `text`
7. 写作完成后输出 `reflection`
8. 随后输出 `summary`
9. 最后输出 `done`

展示：

- 左侧：思考面板 + 正文气泡 + 写作总结面板 + 写作摘要面板
- 右侧：完整过程时间线

### 6.3 需要用户澄清

1. Agent 判断无法继续
2. Agent 调用 `question`
3. 页面展示独立提问气泡
4. 用户回复
5. 执行继续

展示：

- 左侧：独立提问气泡
- 右侧：question 节点

## 7. 前端状态职责

### 7.1 `messages`

`messages` 是左侧主对话区的数据源，承载用户真正需要消费的消息对象。

职责：

- 存储用户消息
- 存储 assistant 正式输出正文
- 存储独立提问气泡
- 存储错误消息
- 存储与当前消息绑定的附属区域数据，如思考面板、写作总结、写作摘要、保存状态、文档路径、token 元数据

设计含义：

- `messages` 面向“结果展示”
- 它不是完整执行过程日志

### 7.2 `obsStore`

`obsStore` 是右侧过程明细面板的数据源，专门承载执行过程事件。

职责：

- 管理右侧过程面板的开关状态
- 存储过程事件时间线
- 将连续的流式过程 chunk 合并为更稳定的展示节点

承载的典型事件：

- `thinking`
- `status`
- `skill`
- `subagent_start`
- `question`
- `reflection`
- `summary`
- `done`

设计含义：

- `obsStore` 面向“过程观测”
- 它不承载正式正文，也不应成为文档持久化来源

### 7.3 二者关系

- `messages` 回答“最终给用户看什么”
- `obsStore` 回答“系统执行过程中发生了什么”

两者必须分离，原因是：

- 正式输出需要稳定、可保存、可继续编辑
- 过程输出是流式的、碎片化的、可折叠的、可丢弃的
- 如果把过程事件直接混进正式消息对象，会导致正文污染、提问错位、工具调用噪声泄漏

### 7.4 当前代码位置

- `messages` 与 `obsStore` 定义在 [frontend/src/lib/stores.js](/Users/chris/Documents/dev/nextAgent/doc-assit/frontend/src/lib/stores.js)
- 左侧主对话区消费 `messages`，位于 [frontend/src/lib/components/Chat.svelte](/Users/chris/Documents/dev/nextAgent/doc-assit/frontend/src/lib/components/Chat.svelte)
- 右侧过程区消费 `obsStore`，位于 [frontend/src/lib/components/ObservabilityPanel.svelte](/Users/chris/Documents/dev/nextAgent/doc-assit/frontend/src/lib/components/ObservabilityPanel.svelte)

## 8. 当前实现对照

对照文件：

- [frontend/src/lib/components/Chat.svelte](/Users/chris/Documents/dev/nextAgent/doc-assit/frontend/src/lib/components/Chat.svelte)
- [frontend/src/lib/components/ObservabilityPanel.svelte](/Users/chris/Documents/dev/nextAgent/doc-assit/frontend/src/lib/components/ObservabilityPanel.svelte)
- [backend/agent/adk/runner_adapter.py](/Users/chris/Documents/dev/nextAgent/doc-assit/backend/agent/adk/runner_adapter.py)
- [backend/agent/adk/execute_skill_tool.py](/Users/chris/Documents/dev/nextAgent/doc-assit/backend/agent/adk/execute_skill_tool.py)
- [backend/agent/adk/document_agent.py](/Users/chris/Documents/dev/nextAgent/doc-assit/backend/agent/adk/document_agent.py)
- [backend/main.py](/Users/chris/Documents/dev/nextAgent/doc-assit/backend/main.py)

### 8.1 已基本符合

- 左侧正式气泡与写作总结/写作摘要已拆分
- 左侧已有折叠“思考过程”面板
- 右侧已有工具调用、状态、提问、子 Agent 时间线模型
- 写作正文、总结、摘要在后端已形成独立事件类型

### 8.2 当前差异项

#### 差异 1：右侧未接收到写作总结与写作摘要事件

设计要求：

- `reflection`
- `summary`

都应在右侧过程区可见。

当前实现中，前端收到这两类事件后只写入左侧消息对象，没有同步写入 `obsStore`，因此右侧过程区看不到这两类事件。

#### 差异 2：右侧 skill 事件目前会丢失

设计要求：

- `skill_start` 应作为过程节点可见

当前实现中，Chat 侧把 `skill_start` 转成了 `obsStore` 的 `type: "skill"`，但右侧构建逻辑没有处理 `skill` 类型，因此会被静默丢弃。

#### 差异 3：写作请求识别仍依赖关键字启发式

设计要求：

- 只有真正的过程性文本进入 `thinking`
- 只有正式结果进入 `text`

当前实现中，主 Agent 对写作请求的分流部分依赖 `_looks_like_writing_request(...)` 启发式判断。该策略能缓解“写作规划文本进入正文”的问题，但仍可能误判“包含文档相关词汇的普通查询”。

#### 差异 4：提问正确性仍主要依赖提示词约束

设计要求：

- 面向用户的澄清必须发为 `question`

当前实现中，这一约束已写入主 Agent 与子 Agent 提示词，但后端尚未加入“明显提问文本自动纠偏为 `question`”的防线，因此仍存在模型不遵守提示词时展示跑偏的风险。

## 9. 后续实施建议

### 优先级 P1

- 前端把 `reflection` 与 `summary` 同步写入 `obsStore`
- 右侧过程区补上 `skill` 类型渲染

### 优先级 P2

- 在后端加入“提问文本纠偏”为 `question` 的兜底规则
- 用显式执行状态代替纯关键字启发式分流，减少 `thinking/text` 误判

### 优先级 P3

- 进一步收敛左侧思考面板内容，支持“精简思考摘要”和“完整右侧链路”分层
