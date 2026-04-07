## MODIFIED Requirements

### Requirement: 按词汇类型和模块 ID 精确加载上下文
Agent SHALL 根据推断的词汇列表和解析出的模块 ID，按执行阶段精确加载对应的项目事实信息，并对进入历史与进入写作上下文的内容采用不同策略；系统不得默认把无关模块数据或大体量原文重复注入到历史和最终写作 prompt。

#### Scenario: modules 词汇作为定位入口时受预算控制
- **WHEN** Agent 在模块发现或消歧阶段加载 modules 相关上下文
- **THEN** 系统 SHALL 仅将足以完成模块定位的模块地图或摘要信息注入当前阶段，不得默认把全量 modules.md 原文直接带入最终写作 prompt

#### Scenario: 清单文件按模块 ID 过滤
- **WHEN** Agent 加载 usecases / classes / interfaces 词汇时
- **THEN** Agent SHALL 仅读取对应清单文件中 `模块: {module-id}` 标签匹配的条目，不加载其他模块的条目

#### Scenario: prototypes 按模块 ID 定位文件
- **WHEN** Agent 加载 prototypes 词汇时
- **THEN** Agent SHALL 查找与目标模块关联的原型页面，并优先保留页面摘要和关键交互信息；大体量页面 JSON 不得默认同时写入历史和最终写作 prompt

#### Scenario: 加载结果在 status step 中展示
- **WHEN** 上下文加载完成时
- **THEN** Agent SHALL 在 status step 中展示加载摘要，例如："加载项目上下文：模块描述、原型摘要(3页)、规则模板(2份)"

#### Scenario: 工具历史与 working context 分层
- **WHEN** 上下文加载工具返回结果
- **THEN** Agent SHALL 仅将摘要写入对话历史，并将原始正文保存在当轮 working context 中供写作阶段使用
