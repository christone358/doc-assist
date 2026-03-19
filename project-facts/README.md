# 项目事实信息维护规范

项目事实信息（Project Facts）是 Agent 执行文档编写任务的知识来源。本目录采用**星形模型**组织数据：`modules.md` 作为中心枢纽，其他清单文件通过 `模块: {module-id}` 标签与模块关联。

---

## 系统词汇表

Agent 使用以下 5 个标准词汇来描述和加载上下文信息：

| 词汇 | 对应文件 | 加载方式 |
|------|---------|---------|
| `modules` | `project-facts/modules.md` | 全量加载，始终包含 |
| `usecases` | `project-facts/usecases.md` | 按 `模块: {module-id}` 标签过滤 |
| `classes` | `project-facts/classes.md` | 按 `模块: {module-id}` 标签过滤 |
| `interfaces` | `project-facts/interfaces.md` | 按 `模块: {module-id}` 标签过滤 |
| `prototypes` | `project-facts/prototypes/{module-id}.*` | 按模块 ID 定位文件，找到则加载 |

**说明**：
- Agent 加载 `usecases`、`classes`、`interfaces` 时，只读取标注了目标模块 ID 的条目，不加载无关模块的信息
- `prototypes` 按文件名约定定位，文件格式可以是 `.md`、`.html`、`.png` 等
- `modules` 始终全量加载，因为它提供项目全貌，也是 Agent 定位模块 ID 的入口

---

## 文件格式规范

### modules.md — 功能模块清单

每个模块条目必须包含 `{#module-id}` 锚点，供 Agent 精确定位。

**格式**：
```markdown
## 模块名称 {#module-id}

**描述**: 模块的简要说明（1-2句话）

**关键特性**:
- 特性1
- 特性2

**关联资源**:
- 用例: [查看用例](usecases.md#module-id)
- 类包: [查看类包](classes.md#module-id)
- 接口: [查看接口](interfaces.md#module-id)
- 原型: [查看原型](prototypes/module-id.html)
```

**示例**：
```markdown
## 用户认证模块 {#auth-login}

**描述**: 处理用户登录、注册和会话管理功能。

**关键特性**:
- 支持用户名/密码登录
- JWT Token 会话管理
- 登录失败重试限制

**关联资源**:
- 用例: [查看用例](usecases.md#auth-login)
- 类包: [查看类包](classes.md#auth-login)
- 接口: [查看接口](interfaces.md#auth-login)
```

---

### usecases.md — 用例清单

每条用例条目必须包含 `模块: {module-id}` 标签，供 Agent 按模块过滤。

**格式**：
```markdown
### UC-XXX: 用例名称
- **模块**: {module-id}
- **角色**: 参与角色
- **描述**: 用例的简要描述

**主流程**:
1. 步骤1
2. 步骤2

**异常处理**:
- 异常场景1
```

**示例**：
```markdown
### UC-001: 用户登录
- **模块**: auth-login
- **角色**: 注册用户
- **描述**: 用户通过用户名和密码登录系统，获取访问令牌。

**主流程**:
1. 用户输入用户名和密码
2. 系统验证凭证
3. 系统签发 JWT Token
4. 用户跳转到主页

**异常处理**:
- 密码错误：提示错误，记录失败次数
- 连续失败5次：锁定账号30分钟
```

---

### classes.md — 类包清单

每个类/包条目必须包含 `模块: {module-id}` 标签。

**格式**：
```markdown
### 类名或包名 {#class-id}
- **模块**: {module-id}
- **类型**: class | interface | enum | package
- **描述**: 职责说明

**主要方法/属性**:
- `methodName(params): returnType` — 说明
```

**示例**：
```markdown
### AuthService {#auth-service}
- **模块**: auth-login
- **类型**: class
- **描述**: 处理用户认证逻辑，包括登录验证和 Token 管理。

**主要方法**:
- `login(username, password): TokenResult` — 验证用户凭证，返回 JWT Token
- `logout(token): void` — 使 Token 失效
- `validateToken(token): UserInfo` — 验证 Token 有效性
```

---

### interfaces.md — 接口清单

每条接口条目必须包含 `模块: {module-id}` 标签。

**格式**：
```markdown
### 接口名称
- **模块**: {module-id}
- **方法**: GET | POST | PUT | DELETE
- **路径**: /api/v1/path
- **描述**: 接口功能说明

**请求参数**: 参数说明

**响应**: 响应格式说明
```

**示例**：
```markdown
### 用户登录接口
- **模块**: auth-login
- **方法**: POST
- **路径**: /api/v1/auth/login
- **描述**: 验证用户凭证，返回访问令牌。

**请求参数**:
- `username` (string, 必填): 用户名
- `password` (string, 必填): 密码

**响应**:
- 成功: `{ token, user: { id, username } }`
- 失败: `{ error: "invalid_credentials" }`
```

---

### prototypes/ — 原型界面

按模块 ID 命名文件，Agent 通过 `prototypes/{module-id}.*` 定位。

**命名规则**: `{module-id}.html` 或 `{module-id}.md` 或 `{module-id}.png`

**示例**:
```
prototypes/
├── auth-login.html       # 登录模块原型（HTML 交互稿）
├── dashboard.md          # 仪表盘原型（Markdown 描述）
└── user-profile.png      # 用户资料页面截图
```

---

## 添加新模块的步骤

1. **在 `modules.md` 中添加模块条目**，包含 `{#module-id}` 锚点和 `关联资源:` 块
2. **在 `usecases.md` 中添加用例**，每条用例标注 `模块: {module-id}`
3. **根据需要**在 `classes.md`、`interfaces.md` 中添加条目，同样标注模块 ID
4. **如有原型**，按命名规则放入 `prototypes/` 目录

---

## 维护说明

- 所有文件由人工维护，Agent **只读不可修改**
- `modules.md` 是核心枢纽，新增模块务必先在此注册
- 模块 ID 使用 kebab-case 格式（如 `auth-login`、`doc-version`）
- 确保各清单文件中的 `模块: {module-id}` 与 `modules.md` 中的锚点一致
