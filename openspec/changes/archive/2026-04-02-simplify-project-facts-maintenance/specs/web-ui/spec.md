## ADDED Requirements

### Requirement: Web UI 展示项目事实信息管理视图
Web UI SHALL 提供项目事实信息管理页面，用于浏览已经维护的项目事实信息，并以模块档案为主视角展示模块详情和关联信息。

#### Scenario: 模块列表作为默认入口
- **WHEN** 用户进入项目事实信息管理页面
- **THEN** Web UI SHALL 默认展示已维护模块的列表，而不是仅展示按层级平铺的事实条目列表

#### Scenario: 模块详情展示已维护事实信息
- **WHEN** 用户在模块列表中选择某个模块
- **THEN** Web UI SHALL 在详情区域展示该模块的功能描述、功能点、API 清单、页面/原型、包/类和依赖模块信息

#### Scenario: 页面支持筛选和搜索
- **WHEN** 用户需要查找特定模块或识别知识库范围时
- **THEN** Web UI SHALL 支持按关键词、所属系统或模块状态筛选和搜索模块

#### Scenario: 原型页名称展示
- **WHEN** 模块关联的原型资源来自集中存放的 Axure HTML 原型包
- **THEN** Web UI SHALL 在模块详情中展示该模块关联的页面名称列表，并在可行时提供跳转到集中原型资源的入口
