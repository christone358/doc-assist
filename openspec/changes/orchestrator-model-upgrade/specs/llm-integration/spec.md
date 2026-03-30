## MODIFIED Requirements

### Requirement: LLM 模型配置管理（新增角色字段）

`LLMConfig` 数据模型 SHALL 新增 `role` 字段，取值为 `orchestrator`、`worker` 或 `default`。

#### Scenario: 配置角色字段

- **WHEN** 用户添加或编辑 LLM 配置时
- **THEN** 系统 SHALL 支持为该配置指定角色（Orchestrator / Worker / Default）；现有配置未指定角色时默认为 `default`

#### Scenario: 按角色查询模型

- **WHEN** 系统需要获取特定角色的 LLM 配置时
- **THEN** `get_litellm_model_config(role)` 接口 SHALL 优先返回匹配该角色的激活配置；无匹配时返回 `is_default=True` 的配置；均无则返回 `None`

#### Scenario: 现有配置向后兼容

- **WHEN** 系统加载不含 `role` 字段的旧版 `llm_configs.json` 时
- **THEN** 系统 SHALL 将这些配置的 `role` 视为 `default`，不产生错误，行为与升级前一致
