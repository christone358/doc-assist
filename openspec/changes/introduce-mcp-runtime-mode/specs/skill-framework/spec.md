## ADDED Requirements

### Requirement: Skill 运行时资源访问通过 `skill.*` namespace 暴露
Skill 框架 SHALL 将当前 Skill 目录内的本地资源以 `skill.*` namespace 的形式暴露给执行中的 Skill，而不是依赖隐式宿主加载或仅靠正文约定。

#### Scenario: Skill 读取本地参考资料
- **WHEN** 执行中的 Skill 需要读取 `references/`、`reference/`、`templates/` 或其他文本资源
- **THEN** 系统 SHALL 通过 `skill.read_resource(relative_path)` 这类 `skill.*` namespace 能力提供标准访问入口

#### Scenario: Skill 执行本地脚本
- **WHEN** 执行中的 Skill 需要运行当前 Skill 根目录下的 Python 脚本
- **THEN** 系统 SHALL 通过 `skill.run_script(relative_path, payload)` 这类 `skill.*` namespace 能力提供受限执行入口

#### Scenario: Skill 查看可用资源清单
- **WHEN** 执行中的 Skill 需要了解当前有哪些本地资源可用
- **THEN** 系统 SHALL 通过 `skill.list_resources()` 提供资源清单及分类信息

### Requirement: Skill 资源声明与运行时访问解耦于具体宿主工具名
Skill 正文 MAY 描述需要读取的资源和调用时机，但 Skill 契约 SHALL 面向能力和 namespace，而不是绑定某个宿主内部工具名称。

#### Scenario: Skill 正文描述运行时能力需求
- **WHEN** Skill 作者在 `skill.md` 中描述“读取参考文件”“执行脚本”“读取历史基线”等动作
- **THEN** 系统 SHALL 允许这些描述在运行时映射到对应 namespace 能力，而不要求 Skill 作者依赖特定的宿主函数名

#### Scenario: Skill 迁移到不同宿主运行时
- **WHEN** 同一个 Skill 被加载到支持相同 MCP namespace 契约的不同宿主运行时
- **THEN** Skill 的本地资源访问方式 SHALL 保持一致，不要求修改其资源路径描述或使用约定
