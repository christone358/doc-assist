## ADDED Requirements

### Requirement: Skill 运行时可访问本地文本资源
系统 SHALL 为正在执行的 Skill 提供访问其本地文本资源的能力，供 Sub-agent 按需读取参考资料、模板或配置文件。

#### Scenario: 读取 Skill 目录内参考文件
- **WHEN** Skill Sub-agent 调用 `read_skill_resource(relative_path)` 且目标文件位于当前 Skill 根目录内
- **THEN** 系统 SHALL 返回该文件的文本内容，并记录资源相对路径与来源类型

#### Scenario: 读取结果进入共享执行上下文
- **WHEN** `read_skill_resource(relative_path)` 成功返回文本内容
- **THEN** 系统 SHALL 将该内容以带来源标签的形式写入本轮共享执行上下文，供后续写作或生成步骤继续使用

### Requirement: Skill 运行时可执行本地 Python 脚本
系统 SHALL 为正在执行的 Skill 提供执行其本地 Python 脚本的能力，用于一次性数据整理、结构提取或其他辅助计算。

#### Scenario: 执行 Skill 目录内 Python 脚本
- **WHEN** Skill Sub-agent 调用 `run_skill_script(relative_path, payload)` 且目标文件是当前 Skill 根目录内的 `.py` 文件
- **THEN** 系统 SHALL 在该 Skill 根目录作为工作目录运行脚本，并将 stdout 作为工具结果返回

#### Scenario: 脚本输出进入共享执行上下文
- **WHEN** `run_skill_script(relative_path, payload)` 成功返回结果
- **THEN** 系统 SHALL 将脚本输出以带来源标签的形式写入本轮共享执行上下文，供后续写作或生成步骤继续使用

### Requirement: Skill 本地资源访问必须受宿主安全边界约束
系统 MUST 将 Skill 本地资源访问限制在当前 Skill 根目录内，并对路径与执行行为做安全校验。

#### Scenario: 拒绝越权路径访问
- **WHEN** `read_skill_resource(relative_path)` 或 `run_skill_script(relative_path, payload)` 解析后的目标路径超出当前 Skill 根目录
- **THEN** 系统 SHALL 拒绝执行，并返回明确的越权错误信息

#### Scenario: 拒绝不受支持的脚本类型
- **WHEN** `run_skill_script(relative_path, payload)` 的目标文件不是 `.py`
- **THEN** 系统 SHALL 拒绝执行，并提示当前仅支持 Python 脚本

#### Scenario: 脚本执行失败时返回可诊断结果
- **WHEN** Skill 脚本执行超时、退出码非零或输出超出限制
- **THEN** 系统 SHALL 终止该次执行，记录失败原因，并将可诊断的错误摘要返回给 Skill Sub-agent
