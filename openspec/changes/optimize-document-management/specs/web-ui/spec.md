## MODIFIED Requirements

### Requirement: Web UI 展示文档生成结果
文档生成完成后，Web UI 应该显示生成文档的文件路径和文件名，用户可以在本地打开查看。

#### Scenario: 显示文档保存位置
- **WHEN** 用户点击“保存为正式版本”且保存成功
- **THEN** Web UI SHALL 显示该文档在 `doc_output/` 下的实际保存路径、版本号和保存结果

### Requirement: Web UI 提供自然语言输入界面
Web 应用应该提供一个用户友好的界面，让用户用自然语言描述文档编写需求。

#### Scenario: 中间结果保存
- **WHEN** 用户在对话过程中查看已正式保存的结果
- **THEN** Web UI SHALL 展示 canonical 文档类型、canonical 文档名称和正式版本路径，避免同一对象以多个名称重复显示

## ADDED Requirements

### Requirement: 文档管理页展示 canonical 分类与别名信息
Web UI 的文档管理页 SHALL 按 canonical 文档类型组织展示文档，并向用户暴露必要的归一结果。

#### Scenario: 按 canonical 文档类型过滤
- **WHEN** 用户在文档管理页切换文档类型筛选
- **THEN** Web UI SHALL 使用 canonical 文档类型值进行过滤，例如 `requirements`、`design`、`test-plan`、`user-manual`

#### Scenario: 展示路径与别名
- **WHEN** 文档管理页展示某个文档系列
- **THEN** Web UI SHALL 显示：
  1. canonical 文档名称
  2. 文档类型标签
  3. 最新版本号与日期
  4. 实际保存路径
  5. 别名信息或别名数量（如存在）
