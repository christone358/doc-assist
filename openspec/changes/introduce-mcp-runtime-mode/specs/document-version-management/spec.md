## ADDED Requirements

### Requirement: 历史文档可通过 `docs.*` MCP namespace 作为标准写作基线来源
系统 SHALL 通过 `docs.*` namespace 向主 Agent 和 Skill Sub-agent 暴露历史文档列表与加载能力，使已保存版本成为修改场景下的标准基线来源。

#### Scenario: 主 Agent 查询历史文档元数据
- **WHEN** 主 Agent 需要判断某类文档是否已有已保存版本
- **THEN** 系统 SHALL 通过 `docs.*` namespace 提供文档列表或版本元数据查询能力

#### Scenario: Skill Sub-agent 加载历史基线稿
- **WHEN** Skill Sub-agent 需要基于某个已保存版本继续修改
- **THEN** 系统 SHALL 通过 `docs.*` namespace 提供标准化的文档加载能力，并返回对应版本的正文和元数据

### Requirement: `docs.*` 工具集合应覆盖历史文档主读取路径
系统 SHALL 让 `docs.*` namespace 至少覆盖“查列表”和“读正文”两个主读取路径。

#### Scenario: 历史文档列表工具标准化
- **WHEN** Agent Runtime 需要查看某类文档是否已有保存版本
- **THEN** 系统 SHALL 提供 `docs.list_saved(doc_type?)` 工具，返回匹配范围内的文档元数据列表

#### Scenario: 历史文档加载工具标准化
- **WHEN** Agent Runtime 需要读取某一文档系列的最新版本或指定版本
- **THEN** 系统 SHALL 提供 `docs.load_saved(doc_type, doc_name, version?)` 工具，返回正文和对应版本元数据

### Requirement: `docs.*` namespace 保持版本语义稳定
系统 SHALL 让 `docs.*` namespace 围绕文档类型、文档名称和版本语义暴露能力，而不是退化为普通文件读取接口。

#### Scenario: 通过文档语义而非路径加载版本
- **WHEN** Agent Runtime 请求加载某个已保存文档版本
- **THEN** 系统 SHALL 以 `doc_type`、`doc_name` 和可选 `version` 作为主要查询语义，而不是要求调用方直接传递底层存储路径

#### Scenario: `docs.*` 在第一阶段保持只读
- **WHEN** Agent Runtime 使用 `docs.*` namespace
- **THEN** 系统 SHALL 仅提供列表、加载和可选比较等读操作，不得在该 namespace 中承担正式保存写入职责

### Requirement: 未保存草稿不应与 `docs.*` 的正式版本语义混用
系统 SHALL 将当前对话中的未保存草稿视为会话态 working draft，而不是 `docs.*` namespace 下的标准版本资源。

#### Scenario: 已保存正式文档通过 `docs.*` 加载
- **WHEN** Agent Runtime 需要读取正式保存过的历史版本
- **THEN** 系统 SHALL 通过 `docs.list_saved` / `docs.load_saved` 提供标准版本读取能力

#### Scenario: 未保存草稿通过会话态上下文延续
- **WHEN** 当前对话中存在尚未保存为正式版本的草稿，且 Agent Runtime 需要继续修改它
- **THEN** 系统 SHALL 通过会话态草稿状态或等价内部上下文提供该草稿，而不是要求调用方通过 `docs.*` 加载
