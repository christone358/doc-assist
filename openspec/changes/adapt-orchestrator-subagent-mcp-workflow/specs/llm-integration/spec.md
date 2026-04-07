## ADDED Requirements

### Requirement: LLM 提示词工程 SHALL 区分 Orchestrator 与 Skill Sub-agent
系统 SHALL 为主 Agent 与 Skill Sub-agent 维护不同的提示词模板和工具声明策略。

#### Scenario: Orchestrator 提示词使用编排视角
- **WHEN** LLM 被用于主 Agent 决策
- **THEN** 系统 SHALL 使用面向编排和状态管理的提示词模板，并包含主 Agent 当前可用工具与职责边界

#### Scenario: Skill 提示词使用执行视角
- **WHEN** LLM 被用于 Skill Sub-agent 执行
- **THEN** 系统 SHALL 使用面向具体任务执行的提示词模板，并包含子 Agent 当前可用工具与执行约束

### Requirement: 系统 SHALL 将主子 Agent prompt 管理为独立文档模板
系统 SHALL 将 Orchestrator 与 Skill Sub-agent 的系统提示词从 Python 内联字符串迁移到独立文本模板中管理，并保留少量运行时插槽注入能力。

#### Scenario: Orchestrator prompt 从独立模板加载
- **WHEN** 系统构建主 Agent 的 system prompt
- **THEN** 系统 SHALL 从独立提示词文档模板加载静态规则，并在运行时注入技能列表、草稿状态提示或等价动态片段

#### Scenario: Skill 执行规范从独立模板加载
- **WHEN** 系统构建 Skill Sub-agent 的 system prompt
- **THEN** 系统 SHALL 从独立提示词文档模板加载系统级执行规范，并与 Skill 自身的 `SKILL.md` 正文分层拼装

### Requirement: 工具声明 SHALL 反映工具分级与职责边界
系统 SHALL 让 LLM 看到与当前 Agent 角色一致的工具集合，而不是向主 Agent 和子 Agent 公开同样的工具世界。

#### Scenario: 主 Agent 仅声明编排相关工具
- **WHEN** 系统构建主 Agent 的工具声明
- **THEN** 系统 SHALL 优先声明公共工具集、委派工具和必要澄清工具，而不是完整下沉 Skill 私有执行工具

#### Scenario: 子 Agent 获得执行相关工具
- **WHEN** 系统构建 Skill Sub-agent 的工具声明
- **THEN** 系统 SHALL 声明写作执行和内部资源访问相关工具，并避免把主 Agent 的规划职责重复注入

### Requirement: Prompt 中的工具说明 SHALL 从当前 tool view 派生
系统 SHALL 让主 Agent 与 Skill Sub-agent 提示词中的“可用工具”说明由当前 `tool view` 与工具 schema 元数据动态生成或动态注入，而不是长期维护与真实工具集合分离的静态工具清单文本。

#### Scenario: tool view 变化时 prompt 工具说明同步变化
- **WHEN** 某个 Agent 当前可见的工具集合因 MCP 发现结果或宿主策略变化而发生变化
- **THEN** 系统 SHALL 让该 Agent prompt 中的工具说明随之更新，避免提示词继续声明已下线工具或遗漏新暴露工具

#### Scenario: Prompt 只描述当前角色真正可见的工具
- **WHEN** 宿主为不同 Agent 角色生成不同的 `tool view`
- **THEN** 系统 SHALL 仅在对应 prompt 中描述该角色当前可见的工具与职责边界，而不是复用一份手写的通用工具清单
