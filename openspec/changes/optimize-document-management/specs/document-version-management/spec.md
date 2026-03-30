## MODIFIED Requirements

### Requirement: 文档分类存储
系统应该支持按文档类型对输出的文档进行分类存储，便于用户查找和管理。

#### Scenario: 自动分类
- **WHEN** 用户点击“保存为正式版本”后系统执行正式落盘
- **THEN** 系统 SHALL 根据 canonical 文档类型将文档保存到 `doc_output/[doc_type]/` 对应目录

#### Scenario: 官方目录结构
- **WHEN** 初始化文档管理系统
- **THEN** 系统 SHALL 在项目目录中使用以下正式输出结构：
  ```
  doc_output/
    requirements/      # 需求规格文档
    design/            # 设计方案文档
    test-plan/         # 测试方案文档
    user-manual/       # 用户手册
    api/               # API 文档
    general/           # 通用文档
  ```

#### Scenario: 历史目录只读兼容
- **WHEN** 系统查询历史正式版本时
- **THEN** 系统 MAY 读取旧目录中的历史文档，但新保存的正式版本 SHALL 只写入 `doc_output/`

### Requirement: 文档检索
系统应该提供文档检索功能，帮助用户快速找到所需的文档。

#### Scenario: 按类型检索
- **WHEN** 用户查询特定类型的文档（例如“需求规格”或“测试计划”）
- **THEN** 系统 SHALL 将用户输入映射到 canonical 文档类型后返回该类型下的文档列表

#### Scenario: 按名称检索
- **WHEN** 用户按文档名称搜索
- **THEN** 系统 SHALL 基于 canonical 文档名称和别名匹配同一文档系列，而不是仅按原始目录名精确匹配

### Requirement: 版本作为修改输入
已输出的文档版本应该可以作为修改场景下的输入，形成版本链条。

#### Scenario: 加载版本作为基础
- **WHEN** 用户指示修改某个已存在的文档
- **THEN** 系统 SHALL 使用与正式保存相同的 canonical 文档类型和 canonical 文档名称解析规则定位并加载其最新版本

## ADDED Requirements

### Requirement: 文档系列名称归一
系统 SHALL 为正式版本建立稳定的 canonical 文档名称，并支持通过别名识别同一写作对象。

#### Scenario: 剥离文档类型后缀
- **WHEN** 用户提供的文档名称包含“需求规格说明书”“设计方案”“测试方案”“用户手册”等文档类型后缀
- **THEN** 系统 SHALL 在建立文档系列时剥离这些后缀，仅保留对象名称作为 canonical 文档名称主体

#### Scenario: 识别对象名称的常见变体
- **WHEN** 用户对同一对象混用“模块”“类”“包”“系统”“服务”“组件”等描述
- **THEN** 系统 SHALL 对这些常见后缀执行轻量归一，并将识别结果归入同一文档系列（若匹配置信度足够）

#### Scenario: 保存别名信息
- **WHEN** 系统创建或更新某一文档系列
- **THEN** 系统 SHALL 保存该系列的别名集合，以便后续保存、检索和加载时复用
