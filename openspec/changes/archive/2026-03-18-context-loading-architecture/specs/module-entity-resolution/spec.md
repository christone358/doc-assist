## ADDED Requirements

### Requirement: 从用户消息提取目标模块并映射到模块 ID
Agent SHALL 从用户消息中提取目标模块名称，并将其映射到 modules.md 中定义的模块 ID，作为后续上下文加载的检索键。

#### Scenario: 精确字符串匹配
- **WHEN** 用户消息中的模块名称与 modules.md 中某个模块的名称完全匹配时
- **THEN** Agent SHALL 直接使用该模块的 ID，不执行额外的 LLM 调用

#### Scenario: LLM 语义匹配兜底
- **WHEN** 精确字符串匹配未命中时
- **THEN** Agent SHALL 执行一次 LLM 调用，输入模块列表和用户消息，由 LLM 选择最匹配的模块 ID；若 LLM 无法确定，返回 null

#### Scenario: 模块定位结果在 status step 中展示
- **WHEN** 模块定位完成时
- **THEN** Agent SHALL 在 status steps 中展示定位结果，例如："已定位模块: 登录模块（auth-login）"，使用户可以验证定位是否正确

#### Scenario: 模块未找到时中断并引导用户
- **WHEN** 所有匹配策略均未找到对应模块时
- **THEN** Agent SHALL 中断写作流程，在 status step 中展示「未识别到目标模块」，并输出一段引导文字，列出 modules.md 中所有可用模块名称，要求用户明确指定目标模块后重新提问
