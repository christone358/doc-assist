## Why

当前系统虽然允许将 Axure 导出的完整 HTML 原型包集中存放在 `project-facts/prototypes/` 中，并在模块档案里维护页面名称，但 Agent 在写作文档时仍然只能读取原始 HTML 文件或页面名索引，无法稳定理解页面结构、界面要素和交互关系。这使用户手册、需求说明和设计文档在描述真实页面时仍然大量依赖人工补充，无法充分复用已有原型资产。

随着项目事实维护模式已经收敛到“模块档案 + 集中原型包 + 自动派生索引”，现在需要补上“自动解析原型并向写作 Skill 提供结构化页面事实”这一层系统能力，让专项写作 Skill 可以按页面、按模块读取真实页面要素，而不是直接消费 HTML 源码。

## What Changes

- 新增系统级 Axure 原型包解析能力，支持扫描 `project-facts/prototypes/` 下的完整导出目录，自动构建页面清单、入口关系和页面级结构化事实。
- 新增原型查询工具，允许 Skill 按模块关联页面或按页面路径读取页面结构、元素和交互摘要，而不是直接读取原始 HTML。
- 将原型解析结果沉淀为派生索引与页面事实缓存，供 Agent、Skill 和后续浏览能力复用，同时保持模块档案仍然是唯一人工维护事实源。
- 调整上下文加载与文档编写规范，使写作 Skill 在需要描述真实界面时优先使用解析后的页面事实，并保留来源追溯。

## Capabilities

### New Capabilities
- `prototype-parsing`: 自动解析 Axure 原型包，生成页面 sitemap、页面事实和可供 Skill 调用的查询能力。

### Modified Capabilities
- `project-fact-information`: 扩展原型事实存放和派生索引规范，使完整 Axure 原型包和解析结果可以稳定共存。
- `structured-context-loading`: 调整原型上下文加载方式，使 Agent/Skill 加载的是模块关联页面的结构化页面事实，而非原始 HTML 文件内容。
- `document-skills`: 扩展文档编写 Skill 的上下文利用规范，使专项写作 Skill 可以调用原型查询能力并基于页面事实写作。

## Impact

- 影响 `project-facts/prototypes/` 的组织约定和解析派生产物格式。
- 影响 `backend/project_fact_modules.py`、原型扫描/索引生成、Agent 上下文加载与 ADK 工具注册逻辑。
- 影响 `backend/agent/context_loader.py`、`backend/agent/adk/fact_tools.py`、`backend/agent/adk/execute_skill_tool.py` 等上下文与工具链路。
- 影响 `skills/write-user-manual` 及其他需要引用真实界面信息的写作 Skill。
