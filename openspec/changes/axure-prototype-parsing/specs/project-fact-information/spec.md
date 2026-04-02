## MODIFIED Requirements

### Requirement: 项目事实信息三层组织结构
项目事实信息 SHALL 以星形模型组织，modules.md 作为枢纽和检索入口，其他清单文件通过模块 ID 标签与模块关联。分层披露原则体现在条目内部的信息密度分层，而非目录层级分离。

#### Scenario: 星形存储结构
- **WHEN** 用户维护项目事实信息时
- **THEN** `project-facts/` 目录 SHALL 包含以下文件：
  - `modules.md` — 模块树，每个条目包含模块 ID、名称、描述、关联资源引用
  - `usecases.md` — 所有用例，每条含 `模块: {id}` 标签
  - `classes.md` — 所有类包，每条含 `模块: {id}` 标签
  - `interfaces.md` — 所有接口，每条含 `模块: {id}` 标签
  - `prototypes/` — 原型资源目录，允许集中存放完整 Axure HTML 原型包及其资源文件
  - `generated/prototypes/` — 由系统自动生成的原型页面索引和页面事实缓存
  - `README.md` — 系统词汇表和格式规范

#### Scenario: modules.md 作为双重职责文件
- **WHEN** Agent 读取 modules.md 时
- **THEN** 该文件 SHALL 同时满足：
  1. 对 LLM：提供项目全貌（模块树结构、模块描述）
  2. 对 Agent：提供检索入口（模块 ID、关联资源路径引用）
  每个模块条目格式示例：
  ```markdown
  ### 登录模块 {#auth-login}
  别名: 用户登录, 用户认证
  负责用户认证和会话管理。
  关联资源:
  - 用例: UC-001, UC-002
  - 核心类: AuthService, PasswordValidator
  - 接口: POST /api/auth/login
  - 原型: prototypes/axure-export/login.html
  - 源码目录: src/auth/login/
  ```

#### Scenario: 清单文件条目包含摘要和详情两个层次
- **WHEN** Agent 读取清单文件中的条目时
- **THEN** 每个条目 SHALL 包含摘要行（供快速了解）和详细描述（供深度理解），Agent 可选择读取深度

#### Scenario: 关系通过模块条目单点维护
- **WHEN** 用户需要建立知识要素之间的关联时
- **THEN** 所有跨要素关联 SHALL 只在 modules.md 的模块条目中声明，usecases.md / classes.md 等文件的条目只需包含自身内容和模块归属标签，不需要交叉引用

## ADDED Requirements

### Requirement: 原型派生页面事实不作为并列权威事实源
系统 SHALL 允许基于集中存放的原型资源自动生成页面索引和页面事实，但这些派生产物 MUST 作为读取优化和写作证据存在，而不是作为与人工维护事实并列的权威事实源。

#### Scenario: 模块档案中的页面名称仍然是模块关联依据
- **WHEN** 模块档案中声明了页面名称列表
- **THEN** 系统 SHALL 将这些页面名称视为模块关联页面的权威来源，并基于派生页面索引执行匹配，而不是反向用派生产物改写模块档案

#### Scenario: 派生页面事实用于检索和写作
- **WHEN** Agent 或 Skill 读取原型相关事实
- **THEN** 系统 SHALL 优先返回派生的页面索引和结构化页面事实，并保留来源路径与解析告警，供检索、上下文装载和文档写作使用
