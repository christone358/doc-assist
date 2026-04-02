## ADDED Requirements

### Requirement: Skill 管理返回受控元信息
Skill 管理系统 SHALL 只返回正式支持的 Skill 元信息，避免将非契约字段暴露给技能管理页面。

#### Scenario: 查询 Skill 列表
- **WHEN** Web UI 请求 Skill 列表
- **THEN** Skill 管理系统 SHALL 返回每个 Skill 的受控元信息集合：`id`、`name`、`description`、`type`、`version`、`capabilities`

#### Scenario: 查询 Skill 详情
- **WHEN** Web UI 请求某个 Skill 的详细信息
- **THEN** Skill 管理系统 SHALL 返回该 Skill 的受控元信息和资源清单，且 SHALL NOT 返回 `tags`、绝对路径或其他未纳入元信息契约的字段

### Requirement: Skill 管理提供资源清单
Skill 管理系统 SHALL 为每个 Skill 提供可供前端展示的内部资源清单。

#### Scenario: 详情接口返回资源清单
- **WHEN** Web UI 打开某个 Skill 的详情面板
- **THEN** Skill 管理系统 SHALL 返回该 Skill 的资源条目列表，并为每个条目提供资源分类和相对路径

#### Scenario: 空资源 Skill
- **WHEN** 某个 Skill 目录中不存在 `skill.md` 之外的可展示文件
- **THEN** Skill 管理系统 SHALL 返回空的资源清单，而不是省略该字段或报错

### Requirement: Skill 管理不提供标签能力
Skill 管理系统 SHALL 移除标签相关的解析、返回和管理能力。

#### Scenario: Legacy Skill 含有标签字段
- **WHEN** 系统加载包含 `tags` 或 `Tags` 字段的历史 Skill
- **THEN** Skill 管理系统 SHALL 继续注册该 Skill，但 SHALL NOT 返回标签数据

#### Scenario: 技能管理接口不含标签入口
- **WHEN** 前端或其他调用方使用 Skill 管理接口
- **THEN** 系统 SHALL NOT 提供标签展示字段，也 SHALL NOT 提供为 Skill 添加、编辑或删除标签的接口入口
