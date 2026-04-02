## MODIFIED Requirements

### Requirement: Agent 支持精准修改和版本管理
Agent SHALL 能够识别用户的修改需求，加载正式文档的上一版本，基于上一版本进行精准修改，并生成修改差异展示。

#### Scenario: 识别修改需求
- **WHEN** 用户输入指示修改的自然语言
- **THEN** Agent SHALL 识别出这是一个修改需求，而非新增编写

#### Scenario: 加载文档版本
- **WHEN** Agent 识别出修改需求时
- **THEN** Agent SHALL：
  1. 识别要修改的文档类型和名称
  2. 仅从 `doc_output/` 读取该文档的最新正式版本
  3. 向用户展示当前版本信息（版本号、修改时间等）

#### Scenario: 精准修改执行
- **WHEN** Agent 获取到正式文档版本和修改需求时
- **THEN** Agent SHALL 调度对应的 Skill 进行修改，并将来自 `doc_output/` 的正式版本内容作为写作输入

#### Scenario: 修改差异展示
- **WHEN** Skill 完成修改后返回新版本内容
- **THEN** Agent SHALL：
  1. 计算修改前后的差异
  2. 生成类似代码 diff 的修改对比
  3. 返回修改差异信息给 Web UI 展示

#### Scenario: 修改不明确处理
- **WHEN** Agent 无法完全理解用户的修改意图
- **THEN** Agent SHALL 与用户进行交互澄清，并在确认前不加载无关正式版本

## ADDED Requirements

### Requirement: Agent 仅使用 `doc_output` 作为历史正式版本来源
Agent 在发现和加载历史正式版本时 SHALL 将 `doc_output/` 视为唯一正式版本来源。

#### Scenario: 查询历史正式版本
- **WHEN** Agent 调用历史文档发现工具查询可用正式版本
- **THEN** 工具 SHALL 仅返回 `doc_output/` 中管理的正式文档版本

#### Scenario: 加载历史正式版本
- **WHEN** Agent 调用历史文档加载工具读取指定文档
- **THEN** 工具 SHALL 仅从 `doc_output/` 中加载正式版本内容

#### Scenario: backend legacy 输出不再作为写作输入
- **WHEN** `backend/docs/` 中仍残留 legacy 输出文档
- **THEN** Agent SHALL NOT 将这些 legacy 输出文档作为写作输入来源
