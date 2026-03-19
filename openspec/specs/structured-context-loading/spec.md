## ADDED Requirements

### Requirement: 按词汇类型和模块 ID 精确加载上下文
Agent SHALL 根据推断的词汇列表和解析出的模块 ID，一次性精确加载所有对应的项目事实信息，不加载无关模块的数据。

#### Scenario: modules 词汇始终加载全量
- **WHEN** Agent 加载上下文时
- **THEN** modules.md SHALL 始终全量加载，无论推断列表是否包含 modules，因为它是项目地图和检索入口

#### Scenario: 清单文件按模块 ID 过滤
- **WHEN** Agent 加载 usecases / classes / interfaces 词汇时
- **THEN** Agent SHALL 仅读取对应清单文件中 `模块: {module-id}` 标签匹配的条目，不加载其他模块的条目

#### Scenario: prototypes 按模块 ID 定位文件
- **WHEN** Agent 加载 prototypes 词汇时
- **THEN** Agent SHALL 查找 `project-facts/prototypes/{module-id}.*` 路径下的文件，找到则加载，不存在则跳过并记录日志

#### Scenario: 加载结果在 status step 中展示
- **WHEN** 上下文加载完成时
- **THEN** Agent SHALL 在 status step 中展示加载摘要，例如："加载项目上下文：模块描述、用例信息(3条)、接口清单(2条)"
