## MODIFIED Requirements

### Requirement: Agent 匹配并调度合适的 Skill
DocumentAgent SHALL 根据用户自然语言输入，基于语义理解从已注册 Skill 中选择最合适的 Skill，并告知用户选择结果和理由。

#### Scenario: 单个 Skill 调度
- **WHEN** 用户需求匹配到唯一的 Skill
- **THEN** Agent SHALL 选定该 Skill，并向用户告知本轮使用的 Skill 名称和选择理由

#### Scenario: 基于语义理解匹配 Skill
- **WHEN** Agent 执行 Skill 选择时
- **THEN** Agent SHALL 基于对用户意图和各 Skill 能力的语义理解选出最匹配的 Skill，并给出可读的选择理由

#### Scenario: 多个 Skill 协同（可选）
- **WHEN** 用户需求可能需要多个 Skill 组合时
- **THEN** Agent SHALL 选择最合适的主 Skill，或向用户说明情况并请其确认

### Requirement: Agent 支持精准修改
Agent SHALL 识别修改意图，在修改流程中以已有草稿作为写作基础，根据修改内容的实际需要自主判断是否需要补充加载相关项目事实。

#### Scenario: 识别修改需求
- **WHEN** 用户输入修改类指令且当前对话存在已生成的草稿时
- **THEN** Agent SHALL 识别为修改意图，以已有草稿为基础，根据修改内容的实际需要，自主判断是否需要补充加载相关项目事实

#### Scenario: 精准修改执行
- **WHEN** 写作阶段以修改方式运行时
- **THEN** Agent SHALL 以已有草稿作为主要上下文，结合用户修改指令，生成修改后的文档

#### Scenario: 无草稿时提示用户
- **WHEN** 用户发出修改指令但当前对话尚无草稿时
- **THEN** Agent SHALL 提示用户先完成初次文档生成，再执行修改

### Requirement: Agent 支持多轮对话持续迭代
Agent SHALL 在同一对话中持续维护写作上下文，使用户可以通过多次交互逐步完善文档，而无需每次重新描述完整需求。

#### Scenario: 无需重复描述上下文
- **WHEN** 用户在同一对话中发出后续指令时
- **THEN** Agent SHALL 基于已有的写作上下文理解用户意图，用户不需要重新说明文档类型、写作目标等已建立的上下文信息

#### Scenario: 每轮完成后更新写作上下文
- **WHEN** 一轮文档生成或修改完成后
- **THEN** Agent SHALL 将本轮产出更新为当前草稿，作为后续轮次的写作基础

### Requirement: Agent 响应携带 Skill 和用量元数据
Agent 在完成每轮响应时 SHALL 告知用户本轮使用的 Skill 信息（含选择理由）和 token 用量数据。

#### Scenario: 响应过程中展示 Skill 选择
- **WHEN** Agent 确定要使用某个 Skill 时
- **THEN** Agent SHALL 向用户展示本轮启用的 Skill 名称和选择理由

#### Scenario: 完成时携带完整元数据
- **WHEN** Agent 完成一轮响应时
- **THEN** Agent SHALL 告知用户：使用的 Skill 标识和名称、选择理由、token 用量、是否产生了可保存的草稿
