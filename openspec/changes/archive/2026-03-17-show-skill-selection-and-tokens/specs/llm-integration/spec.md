## MODIFIED Requirements

### Requirement: LLM 集成模块接受用户输入
LLM 集成模块应该接收来自 Web UI 的用户自然语言输入，并将其传递给 LLM 进行处理。调用完成后 SHALL 返回 token 用量数据。

#### Scenario: 接收输入
- **WHEN** Agent 收到用户的自然语言输入
- **THEN** LLM 集成模块应该接收该输入，并准备调用 LLM API

#### Scenario: 输入验证
- **WHEN** LLM 集成模块接收用户输入时
- **THEN** 应该验证输入的长度和格式，防止异常的请求

#### Scenario: 非流式调用返回 token 用量
- **WHEN** 通过 complete() 方法完成一次 LLM 非流式调用
- **THEN** 返回值 SHALL 包含响应文本和 token 用量信息（prompt_tokens、completion_tokens、total_tokens）

#### Scenario: 流式调用结束后提供 token 用量
- **WHEN** 通过 stream_complete() 方法完成流式 LLM 调用
- **THEN** 流式输出结束后 SHALL 提供本次调用的 token 用量；若 provider 不支持流式 usage，则用量数据为 None
