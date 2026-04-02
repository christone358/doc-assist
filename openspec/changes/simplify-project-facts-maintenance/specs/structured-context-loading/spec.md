## MODIFIED Requirements

### Requirement: 按词汇类型和模块 ID 精确加载上下文
Agent SHALL 以模块档案和系统派生索引作为事实加载入口，按目标模块精确加载对应上下文。用户不需要提供显式模块 ID；系统可以在内部使用派生标识和索引完成定位与加载。

#### Scenario: 模块索引作为概览入口
- **WHEN** Agent 开始加载项目事实信息上下文时
- **THEN** Agent SHALL 先加载模块名称、别名和摘要组成的模块索引，用于定位目标模块和展示项目概览

#### Scenario: 目标模块档案作为主要上下文
- **WHEN** Agent 已定位到目标模块时
- **THEN** Agent SHALL 优先加载该模块档案中的功能描述、功能点、API 清单、页面原型、包/类和依赖模块等信息，而不是依赖用户手工维护的模块标签过滤总表

#### Scenario: 派生视图可作为读取优化
- **WHEN** 系统存在由模块档案派生的聚合视图或索引缓存时
- **THEN** Agent MAY 使用这些派生视图优化检索性能，但最终事实依据 SHALL 仍然以模块档案内容为准

#### Scenario: 加载结果在 status step 中展示
- **WHEN** 上下文加载完成时
- **THEN** Agent SHALL 在 status step 中展示加载摘要，例如：“已加载模块档案：功能点 5 项、API 3 项、页面原型 2 项”
