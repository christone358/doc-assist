## MODIFIED Requirements

### Requirement: 主 Agent instruction 基调改为对话连续性

主 Agent 的 instruction SHALL 以"持续对话"为基调，不以"每轮意图分类"为结构，并包含明确的跨轮上下文感知规则。

#### Scenario: instruction 包含对话连续性规则

- **WHEN** 构建 document_orchestrator 的 instruction 时
- **THEN** instruction SHALL 包含以下两条高优先级规则，位于所有工作流描述之前：
  1. **指代词解析规则**：用户使用指代词时从历史解析，不重复询问已建立信息
  2. **澄清循环闭合规则**：收到澄清回答后合并入原始意图继续执行，不重新分类

#### Scenario: instruction 降低决策树密度

- **WHEN** 描述主 Agent 的工作流时
- **THEN** instruction SHALL 以意图识别 + 工具映射的原则式结构描述，
  减少嵌套 if-else 条件分支；草稿状态相关的细节决策委托给 Sub-agent，
  不在 Orchestrator instruction 中展开
