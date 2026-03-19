## ADDED Requirements

### Requirement: 系统词汇表定义
系统 SHALL 在 `project-facts/README.md` 中定义标准上下文类型词汇表，作为 Agent 和 Skill 之间的共同契约。

#### Scenario: 词汇表包含五类标准词汇
- **WHEN** Agent 或 Skill 作者查阅词汇表时
- **THEN** 词汇表 SHALL 包含以下五个词汇及其映射关系：
  - `modules` → modules.md（全量加载，始终包含）
  - `usecases` → usecases.md（按模块 ID 过滤）
  - `classes` → classes.md（按模块 ID 过滤）
  - `interfaces` → interfaces.md（按模块 ID 过滤）
  - `prototypes` → prototypes/{module-id}.*（按模块 ID 定位文件）

#### Scenario: Agent 按词汇执行路径映射
- **WHEN** Agent 收到词汇类型（如 `usecases`）和模块 ID（如 `auth-login`）时
- **THEN** Agent SHALL 按词汇表中定义的映射规则定位并读取对应数据，不依赖硬编码路径

#### Scenario: 词汇表对用户可见
- **WHEN** 用户编写 Skill 或维护 project-facts 时
- **THEN** `project-facts/README.md` SHALL 提供词汇表的完整说明，包括每个词汇的含义、对应文件和检索方式
