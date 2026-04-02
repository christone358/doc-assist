## MODIFIED Requirements

### Requirement: Skill 目录结构规范
每个 Skill MUST 遵循标准的目录结构，包含必需的描述文件和可选的支持文件；这些可选资源在被宿主系统支持时，SHALL 能在运行时被当前 Skill 访问。

#### Scenario: 标准目录结构
- **WHEN** Agent 加载 Skill 时
- **THEN** Skill 目录 SHALL 包含必需的 `skill.md`，并 MAY 包含 `scripts/`、`templates/`、`reference/`、`references/`、`assets/` 以及其他辅助文件

#### Scenario: 文件层级
- **WHEN** 查询 Skill 的组织方式时
- **THEN** 系统 SHALL 识别每个 Skill 目录中的必需文件（`skill.md`）和可选资源文件，并将 `scripts`、`templates`、`reference` / `references` 与其他资源分开归类

#### Scenario: 运行时资源访问范围以 Skill 根目录为边界
- **WHEN** 当前 Skill 在执行中访问其本地资源
- **THEN** 系统 SHALL 仅允许访问该 Skill 根目录下的相对路径资源，不得允许跨 Skill 或跨宿主目录访问

## ADDED Requirements

### Requirement: Skill 正文可声明本地资源的使用时机
`skill.md` 正文 MAY 使用自然语言描述需要读取或执行的本地资源及其调用时机，宿主系统 SHALL 允许当前 Skill 在执行时按这些说明访问对应资源。

#### Scenario: Skill 正文引用相对路径参考资料
- **WHEN** `skill.md` 正文中引用诸如 `references/structure/module-manual.md` 这类相对 Skill 根目录的资源路径
- **THEN** 宿主系统 SHALL 允许当前 Skill 在运行时按相对路径读取该资源

#### Scenario: Skill 正文引用相对路径脚本
- **WHEN** `skill.md` 正文中引用诸如 `scripts/extract_outline.py` 这类相对 Skill 根目录的脚本路径
- **THEN** 宿主系统 SHALL 允许当前 Skill 在运行时按相对路径执行该脚本，并将结果返回给当前执行链路
