## 1. LLM 配置模型扩展

- [ ] 1.1 在 `LLMConfig` dataclass 中新增 `role: str = "default"` 字段（取值：`orchestrator`、`worker`、`default`）
- [ ] 1.2 在 `LLMConfigManager` 中新增 `get_by_role(role: str) -> Optional[LLMConfig]` 方法：返回该角色的激活配置；无匹配时返回 `None`
- [ ] 1.3 更新 `get_litellm_model_config()` 签名为 `get_litellm_model_config(role: str = "default") -> Optional[LiteLLMModelConfig]`：优先查找指定角色，回退到 default
- [ ] 1.4 验证现有 `llm_configs.json` 加载时 `role` 字段缺失不报错（dataclass 默认值保证向后兼容）

## 2. Agent 模型配置读取

- [ ] 2.1 `document_agent.py` 中 `build_document_agent` 调用改为 `get_litellm_model_config(role="orchestrator")`
- [ ] 2.2 `execute_skill_tool.py` 中 `_build_skill_subagent` 内的 `get_litellm_model_config()` 调用改为 `get_litellm_model_config(role="worker")`
- [ ] 2.3 `execute_skill_tool.py` 中 `_extract_and_load_skill_tools` 内的调用改为 `get_litellm_model_config(role="worker")`

## 3. 前端 LLM 配置界面

- [ ] 3.1 在 LLM 配置表单中新增「角色」选择字段（Orchestrator / Worker / Default），编辑和新增时均可指定
- [ ] 3.2 配置列表中每条配置显示角色标签（小徽章样式）
- [ ] 3.3 更新前端与后端配置接口的请求/响应模型，确保 `role` 字段正确传递和展示

## 4. 后端配置 API 更新

- [ ] 4.1 LLM 配置相关的 Pydantic 请求/响应模型中新增 `role` 字段（默认 `"default"`）
- [ ] 4.2 配置保存和读取接口正确处理 `role` 字段的序列化/反序列化

## 5. 验证

- [ ] 5.1 验证只有 default 配置时：orchestrator 和 worker 均回退到 default，行为与升级前一致
- [ ] 5.2 验证配置了 orchestrator 专用模型后：主 Agent 使用新模型，Sub-agent 仍使用 default
- [ ] 5.3 验证同时配置 orchestrator 和 worker 专用模型：两层 Agent 各自独立使用对应模型
- [ ] 5.4 验证旧版 `llm_configs.json`（无 role 字段）加载无异常
