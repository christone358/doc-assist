## MODIFIED Requirements

### Requirement: 从用户消息提取目标模块并映射到模块 ID
Agent SHALL 优先根据模块档案的名称、别名和系统派生的模块索引解析目标模块。模块内部标识仅作为系统检索键使用，用户日常提问和维护时 MUST NOT 被要求显式提供模块 ID。

#### Scenario: 按模块名称精确匹配
- **WHEN** 用户消息中的模块名称与模块档案标题完全匹配时
- **THEN** Agent SHALL 直接定位到对应模块，并在内部使用该模块的派生标识完成后续加载

#### Scenario: 按模块别名匹配
- **WHEN** 用户消息未命中模块标准名称，但命中了模块档案中登记的别名时
- **THEN** Agent SHALL 将该别名解析为对应模块，并继续执行上下文加载

#### Scenario: 多模块歧义时请求澄清
- **WHEN** 用户消息同时匹配多个模块名称或别名，无法唯一定位模块时
- **THEN** Agent SHALL 中断后续模块相关写作或查询流程，并向用户展示候选模块名称，请求用户确认目标模块

#### Scenario: 模块定位结果在 status step 中展示
- **WHEN** 模块定位完成时
- **THEN** Agent SHALL 在 status steps 中展示定位结果，例如：“已定位模块：云主机资产管理”

#### Scenario: 模块未找到时中断并引导用户
- **WHEN** 系统无法从模块名称、别名或索引中定位到目标模块时
- **THEN** Agent SHALL 中断写作流程，在 status step 中展示“未识别到目标模块”，并输出当前可用模块名称列表，引导用户重新指定
