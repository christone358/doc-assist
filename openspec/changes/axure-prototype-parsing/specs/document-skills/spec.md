## ADDED Requirements

### Requirement: 文档编写 Skill 可通过 MCP 原型工具按页面使用原型事实
需要描述真实界面内容的文档编写 Skill SHALL 能够通过 MCP server 暴露的原型工具按模块关联页面读取原型事实，并基于结构化页面要素进行写作，而不是直接依赖原始 HTML 源码或凭空推断界面内容。

#### Scenario: Skill 先定位模块关联页面再读取详情
- **WHEN** 文档编写 Skill 需要描述某个模块的页面操作步骤或界面结构
- **THEN** Skill SHALL 先通过 MCP 原型工具读取该模块关联页面列表，再按需读取具体页面的结构化页面事实

#### Scenario: Skill 使用页面事实描述界面元素和交互
- **WHEN** Skill 已取得页面事实
- **THEN** Skill SHALL 基于页面标题、按钮、输入框、表格、提示语和交互摘要编写文档内容，并在引用来源中保留页面名称或页面路径

#### Scenario: 页面事实不足时保留待确认标记
- **WHEN** 页面事实中缺少关键元素、存在解析告警或模块页面匹配不唯一
- **THEN** Skill SHALL 将相关内容标记为待确认或待补充，而不是虚构按钮名称、字段规则或交互结果
