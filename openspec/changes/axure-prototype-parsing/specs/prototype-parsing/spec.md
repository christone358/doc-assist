## ADDED Requirements

### Requirement: 系统自动解析 Axure 原型包并生成页面索引
系统 SHALL 自动扫描 `project-facts/prototypes/` 下集中存放的 Axure HTML 原型包，识别包根目录、入口页和页面清单，并生成可复用的派生页面索引。

#### Scenario: 扫描完整 Axure 原型包
- **WHEN** `project-facts/prototypes/` 下存在包含 `index.html` 和多个页面 HTML 文件的 Axure 导出目录
- **THEN** 系统 SHALL 识别该目录为一个原型包，并为其中每个页面生成稳定的页面索引记录，至少包含页面 ID、页面名称、相对路径、标题和所属原型包

#### Scenario: 原型包变更后增量刷新
- **WHEN** 原型包中的 HTML 或关联资源文件发生变化
- **THEN** 系统 SHALL 在下一次派生视图刷新或原型查询前自动刷新受影响页面的索引和页面事实，而不是要求用户手工重建

### Requirement: 系统为页面提取结构化页面事实
系统 SHALL 为已识别的原型页面提取结构化页面事实，供 Agent 和 Skill 读取，而不是直接暴露原始 HTML 作为写作上下文。

#### Scenario: 提取页面结构和界面要素
- **WHEN** 系统解析某个原型页面
- **THEN** 系统 SHALL 提取页面标题、布局分区以及关键界面要素，至少覆盖按钮、输入框、表格、选项卡、对话框、可见提示文本和链接

#### Scenario: 提取页面交互和跳转关系
- **WHEN** 页面中存在可识别的 Axure 交互或页面跳转
- **THEN** 系统 SHALL 在页面事实中记录触发对象、交互类型和目标页面或结果描述，并生成页面间的出链关系

#### Scenario: 记录证据和解析告警
- **WHEN** 系统输出页面事实
- **THEN** 页面事实 SHALL 同时包含来源页面路径、关键证据片段以及解析告警信息，使调用方能够追溯来源并识别不确定内容

#### Scenario: 页面事实包含 LLM 可直接消费的摘要
- **WHEN** 系统完成单页结构化解析
- **THEN** 系统 SHALL 基于页面事实生成紧凑的 `llm_summary`，总结页面定位、关键区域、关键控件、用户可见反馈和主要交互，供 Agent 或 Skill 直接注入写作上下文

### Requirement: 系统通过 MCP server 暴露原型查询能力
系统 SHALL 通过 MCP server 暴露可被 Agent 和文档编写 Skill 调用的原型查询能力，使调用方可以先定位模块关联页面，再按需读取页面详情。

#### Scenario: 查询模块关联页面列表
- **WHEN** Agent 或 Skill 调用 `prototypes.list_pages(module_ref)`
- **THEN** 系统 SHALL 返回该模块档案中声明的页面名称及其匹配到的页面路径、标题和匹配状态

#### Scenario: 查询单个页面详情
- **WHEN** Agent 或 Skill 调用 `prototypes.get_page(page_ref)`
- **THEN** 系统 SHALL 返回该页面的结构化页面事实、交互摘要、来源路径和解析告警，而不是返回整页 HTML 源码

#### Scenario: 原型查询能力对外遵循 MCP 公共工具契约
- **WHEN** MCP server 对外暴露原型工具
- **THEN** 系统 SHALL 使用宿主无关的参数和结构化返回语义，不得要求调用方依赖宿主内部会话对象或 ADK 上下文才能正确调用

#### Scenario: MCP 页面详情同时返回结构化数据与文本摘要
- **WHEN** 调用方请求 `prototypes.get_page(page_ref)`
- **THEN** 系统 SHALL 同时返回结构化页面事实和适合 LLM 消费的文本摘要，而不是要求调用方自行从 HTML 或原始 JSON 拼装可读内容
