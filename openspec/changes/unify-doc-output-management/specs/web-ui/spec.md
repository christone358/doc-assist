## MODIFIED Requirements

### Requirement: Web UI 展示文档生成结果
文档生成完成后，Web UI SHALL 显示生成文档的文件路径和文件名，用户可以在本地打开查看。

#### Scenario: 显示文档保存位置
- **WHEN** 用户完成“保存为正式版本”
- **THEN** Web UI SHALL 显示该文档在 `doc_output/` 下的完整相对路径、版本号和生成时间

#### Scenario: 快速定位文档
- **WHEN** 用户查看生成结果
- **THEN** Web UI SHALL 提供复制 `doc_output/` 相对路径的能力，帮助用户快速定位正式输出文档

### Requirement: Web UI 支持多轮对话交互
Web UI SHALL 提供多轮对话界面，让用户与 Agent 进行交互式的需求描述、反馈和修正。

#### Scenario: 中间结果保存
- **WHEN** 用户在对话过程中保存正式版本后查看结果
- **THEN** Web UI SHALL 将 `doc_output/` 下的正式版本视为唯一正式结果来源，不再展示 `backend/docs/` 中的 legacy 输出路径

## ADDED Requirements

### Requirement: 文档结果管理页按实际输出类型管理文档
文档结果管理页 SHALL 按正式输出文档的实际 canonical 类型对文档进行筛选、分组和展示。

#### Scenario: 按实际输出类型筛选
- **WHEN** 用户在文档结果管理页切换类型筛选
- **THEN** 页面 SHALL 基于实际输出的 canonical 文档类型过滤结果，而不是基于 legacy 目录名或历史别名

#### Scenario: 按文档类型分类展示
- **WHEN** 用户进入文档结果管理页
- **THEN** 页面 SHALL 先按文档类型组织和展示文档结果，再在类型内展示对应文档列表

#### Scenario: 结果页展示正式输出路径
- **WHEN** 页面展示文档列表或版本历史
- **THEN** 页面 SHALL 展示 `doc_output/` 下的真实正式路径

#### Scenario: 结果页排除 backend legacy 输出
- **WHEN** 页面加载文档结果
- **THEN** 页面 SHALL NOT 展示 `backend/docs/` 下的 legacy 输出文档

#### Scenario: 需求规格按模块过滤和搜索
- **WHEN** 当前文档类型为 `requirements`
- **THEN** 页面 SHALL 提供按模块过滤和搜索的能力，以 canonical 模块名及别名匹配文档结果

#### Scenario: 用户手册按模块过滤和搜索
- **WHEN** 当前文档类型为 `user-manual`
- **THEN** 页面 SHALL 提供按模块过滤和搜索的能力，以 canonical 模块名及别名匹配文档结果
