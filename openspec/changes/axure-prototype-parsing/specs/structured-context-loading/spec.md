## MODIFIED Requirements

### Requirement: 按词汇类型和模块 ID 精确加载上下文
Agent SHALL 根据推断的词汇列表和解析出的模块 ID，一次性精确加载所有对应的项目事实信息，不加载无关模块的数据。对于原型类上下文，Agent SHALL 优先加载模块关联页面的结构化页面摘要，而不是原始 HTML 文件内容。

#### Scenario: modules 词汇始终加载全量
- **WHEN** Agent 加载上下文时
- **THEN** modules.md SHALL 始终全量加载，无论推断列表是否包含 modules，因为它是项目地图和检索入口

#### Scenario: 清单文件按模块 ID 过滤
- **WHEN** Agent 加载 usecases / classes / interfaces 词汇时
- **THEN** Agent SHALL 仅读取对应清单文件中 `模块: {module-id}` 标签匹配的条目，不加载其他模块的条目

#### Scenario: prototypes 词汇按模块关联页面加载摘要
- **WHEN** Agent 加载 prototypes 词汇时
- **THEN** Agent SHALL 根据目标模块已声明的页面名称列表和派生页面索引，加载该模块关联页面的摘要、路径和匹配状态，而不是直接拼接原始 HTML 文件内容

#### Scenario: 页面详情按需通过原型查询能力加载
- **WHEN** Skill 需要描述某个页面的真实界面元素或交互细节
- **THEN** 系统 SHALL 允许 Skill 在基础上下文之外按需读取单页结构化页面事实，而不是在初始上下文加载阶段一次性注入全部页面详情

#### Scenario: 加载结果在 status step 中展示
- **WHEN** 上下文加载完成时
- **THEN** Agent SHALL 在 status step 中展示加载摘要，例如：“加载项目上下文：模块描述、用例信息(3条)、页面原型(2页)”
