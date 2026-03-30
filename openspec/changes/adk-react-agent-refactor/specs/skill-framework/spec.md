## MODIFIED Requirements

### Requirement: Skill 描述必须涵盖两类信息
每个 Skill SHALL 明确表达两类信息：（1）编写该类文档所需的项目事实类型；（2）文档的写作规范（结构、格式、风格等）。两类信息的具体组织方式和格式不作约束，由 Skill 作者自行决定。

#### Scenario: Skill 包含项目事实需求说明
- **WHEN** Skill 被加载时
- **THEN** Skill 的描述 SHALL 包含对所需项目事实类型的说明，使 Agent 能够理解编写该类文档需要哪类项目背景信息

#### Scenario: Skill 包含写作规范说明
- **WHEN** Skill 被加载时
- **THEN** Skill 的描述 SHALL 包含文档的写作规范，涵盖文档结构、章节组织、内容要求、格式风格等，使 Agent 能够据此生成符合要求的文档

#### Scenario: 元信息必需字段（保持不变）
- **WHEN** 解析 Skill 的元数据时
- **THEN** Skill MUST 包含以下基本标识信息：唯一名称（kebab-case 格式）、功能描述、文档类型

### Requirement: Skill 可包含内部资源，Agent 在 Skill 指导下按需使用
Skill SHALL 能够将参考文档、脚本工具及其他辅助文件作为内部资源与描述文件一同提供。Skill 的描述 SHALL 说明这些资源的用途和使用时机。Agent SHALL 在 Skill 描述的指导下，按需加载文档资源或调用脚本工具，无需在启动时全量加载。

#### Scenario: Skill 包含参考文档资源
- **WHEN** Skill 描述中说明存在参考文档（如写作示例、已有文档范本等）
- **THEN** Agent SHALL 在需要参考时读取对应文档内容，将其纳入写作上下文

#### Scenario: Skill 包含可执行脚本工具
- **WHEN** Skill 描述中说明存在可调用的脚本工具（如 HTML 原型解析脚本、格式转换工具等）
- **THEN** Agent SHALL 能够按 Skill 的指引调用该脚本，并将执行结果作为上下文信息使用

#### Scenario: Agent 按需使用，而非全量预加载
- **WHEN** Agent 判断某项 Skill 内部资源与当前任务相关时
- **THEN** Agent SHALL 主动加载或调用该资源，对于与当前任务无关的资源则不加载，避免无效的上下文膨胀

#### Scenario: 内部资源缺失时不中断流程
- **WHEN** Skill 描述中引用的资源文件不存在时
- **THEN** Agent SHALL 记录警告并继续执行，不因资源缺失而中断整体流程
