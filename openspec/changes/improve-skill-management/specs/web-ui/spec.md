## MODIFIED Requirements

### Requirement: Web UI 显示可用 Skill 列表
Web 应用 SHALL 向用户显示当前系统中可用的 Skill，让用户了解系统能力，同时在技能管理页严格区分元信息与内部资源。

#### Scenario: 显示 Skill 列表
- **WHEN** 用户访问 Web UI 的 Skill 管理页面
- **THEN** 系统 SHALL 显示所有可用 Skill 的列表，包括名称、描述、支持的文档类型，以及可选版本信息

#### Scenario: 查看 Skill 详情
- **WHEN** 用户点击 Skill 列表中的某个 Skill
- **THEN** Web UI SHALL 显示该 Skill 的详细信息，并且仅在元信息区域展示受支持的元信息字段

#### Scenario: 展示 Skill 内部资源
- **WHEN** 用户查看某个 Skill 的详情
- **THEN** Web UI SHALL 在独立的资源区域中分组展示该 Skill 的脚本工具、模板、参考资料和其他资源文件

#### Scenario: 技能管理页不展示标签
- **WHEN** 用户浏览 Skill 列表或详情面板
- **THEN** Web UI SHALL NOT 渲染标签区域、标签徽章或任何为 Skill 打标签的交互入口

#### Scenario: 非元信息字段不进入面板
- **WHEN** Skill 详情数据中存在非元信息字段或内部实现字段
- **THEN** Web UI SHALL NOT 将这些字段渲染为技能元信息
