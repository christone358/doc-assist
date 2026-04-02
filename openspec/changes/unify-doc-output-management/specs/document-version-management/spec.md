## MODIFIED Requirements

### Requirement: 文档分类存储
系统 SHALL 支持按文档类型对正式输出文档进行分类存储，便于用户查找和管理。

#### Scenario: 自动分类
- **WHEN** 用户触发“保存为正式版本”并完成正式落盘
- **THEN** 系统 SHALL 根据文档的实际 canonical type 将文档保存到 `doc_output/[doc_type]/` 对应目录

#### Scenario: 目录结构
- **WHEN** 初始化文档管理系统
- **THEN** 系统 SHALL 将 `doc_output/` 作为正式输出根目录，并在写入时按需创建对应类型目录

#### Scenario: backend 输出目录停用
- **WHEN** 系统写入新的正式输出文档
- **THEN** 系统 SHALL NOT 再将正式输出文档写入 `backend/docs/` 或其他 legacy 输出目录

#### Scenario: legacy 正式输出迁移
- **WHEN** 系统停用 `backend/docs/` 作为正式输出目录
- **THEN** 系统 SHALL 先将其中的 legacy 正式输出迁移到 `doc_output/`，再删除旧的正式输出目录

### Requirement: 文档检索
系统 SHALL 提供文档检索功能，帮助用户快速找到所需的正式文档。

#### Scenario: 按类型检索
- **WHEN** 用户查询特定类型的文档
- **THEN** 系统 SHALL 返回 `doc_output/` 下该类型的正式文档及其最新版本

#### Scenario: 按名称检索
- **WHEN** 用户按文档名称搜索
- **THEN** 系统 SHALL 仅在 `doc_output/` 管理的正式文档系列中执行匹配并返回结果

#### Scenario: 需求规格与用户手册按模块检索
- **WHEN** 用户在需求规格或用户手册类型下按模块名称过滤或搜索文档
- **THEN** 系统 SHALL 基于 `doc_output/` 中文档系列的 canonical 模块名及其别名返回匹配结果

#### Scenario: 不再混用 backend 输出文档
- **WHEN** 系统列出文档管理页的结果或查询历史正式版本
- **THEN** 系统 SHALL NOT 将 `backend/docs/` 下的输出文档纳入正式结果集

### Requirement: 版本作为修改输入
已输出的正式文档版本 SHALL 可以作为修改场景下的输入，形成版本链条。

#### Scenario: 加载版本作为基础
- **WHEN** 用户指示修改某个已存在的文档
- **THEN** 系统 SHALL 仅从 `doc_output/` 中定位并加载该文档的最新正式版本，作为后续写作输入

#### Scenario: 持续迭代
- **WHEN** 用户对文档进行多次修改
- **THEN** 系统 SHALL 基于 `doc_output/` 中的上一正式版本继续迭代，不再回退到 `backend/docs/` 中的 legacy 输出
