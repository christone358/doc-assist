## ADDED Requirements

### Requirement: 首轮对话完成后自动生成语义化标题
对话完成首轮交互后，系统 SHALL 调用 LLM 自动生成一个简短的语义化中文标题，替换默认的时间戳命名。

#### Scenario: 首轮对话完成触发命名
- **WHEN** 对话的第一轮完成（收到 `done` 事件）且对话名称仍为默认格式（以"对话 "开头）
- **THEN** 系统 SHALL 异步调用命名接口，使用该轮的 user_input 和 agent_response 生成标题

#### Scenario: 命名成功更新对话标题
- **WHEN** LLM 命名调用成功返回
- **THEN** 系统 SHALL 将返回的标题（≤20 字中文）更新到对话记录，并刷新导航栏的对话列表

#### Scenario: 命名失败保留原名
- **WHEN** LLM 命名调用失败（网络错误、LLM 错误等）
- **THEN** 系统 SHALL 保留当前时间戳名称，不阻断用户流程，失败静默处理

#### Scenario: 命名 LLM 调用参数
- **WHEN** 系统调用 LLM 生成标题时
- **THEN** 系统 SHALL 使用温度 0.3、max_tokens 50，prompt 模板为"请为以下对话生成一个不超过15字的中文标题，只返回标题文本：\n用户：{user_input}\nAI：{response_summary}"，其中 response_summary 为 agent_response 的前200字
