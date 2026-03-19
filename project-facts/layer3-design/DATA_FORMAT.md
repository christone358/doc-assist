# 设计开发层数据格式设计

设计开发层（Layer 3 - Design & Development）提供项目的实现细节，包括原型、PRD、源代码引用等。

## 数据格式规范

### 1. 原型设计 (prototypes/)

**文件结构**: 按功能或页面命名，如 `wireframe-login.md`

**内容格式**:
```markdown
# 线框图: 登录页面

## 基本信息
- **原型ID**: PROTO-LOGIN-001
- **功能**: 用户登录
- **覆盖用例**: UC-001
- **状态**: 完成/设计中

## 原型说明

### 页面布局
```
+-----------------------------------+
|      NextAgent Doc Assistant      |
|                                   |
|   +--------------------------+    |
|   |  用户名                  |    |
|   +--------------------------+    |
|   |  密码                    |    |
|   +--------------------------+    |
|   | [登录]  [注册]  [忘记密码] |    |
|   +--------------------------+    |
+-----------------------------------+
```

### 交互流程
1. 用户输入用户名
2. 用户输入密码
3. 用户点击登录
4. 页面导航到首页

### 数据绑定
| UI 元素 | 数据字段 | 验证规则 |
|--------|---------|---------|
| 用户名输入框 | username | 长度 4-20 字符 |
| 密码输入框 | password | 长度 6-50 字符 |
| 记住我复选框 | remember_me | 布尔值 |

### 样式指南
- 登录按钮颜色: 蓝色 (#0066CC)
- 字体: 宋体, 14px
- 按钮圆角: 4px
```

**数据结构**:
```json
{
  "id": "PROTO-LOGIN-001",
  "name": "登录页面线框图",
  "feature_id": "FEAT-AUTH",
  "usecase_ids": ["UC-001"],
  "status": "completed",
  "components": [
    {
      "id": "COMP-USERNAME",
      "type": "input",
      "label": "用户名",
      "data_binding": "username",
      "validation": "length:4-20"
    }
  ],
  "interactions": [
    {
      "trigger": "click",
      "action": "submit",
      "target": "POST /api/v1/auth/login"
    }
  ]
}
```

### 2. 产品需求文档 (prds/)

**文件结构**: 按功能命名，如 `feature-auth-prd.md`

**内容格式**:
```markdown
# PRD: 用户认证功能

## 文档信息
- **功能ID**: FEAT-AUTH
- **版本**: 1.0
- **作者**: 产品经理名字
- **日期**: 2026-03-16
- **审核者**: [审核人]

## 背景和机会
[为什么需要这个功能]

## 产品目标
- 提供安全的用户认证机制
- 支持多种登录方式（用户名密码、社交登录等）
- 提高用户转化率

## 功能范围

### 范围内
- ✓ 用户注册
- ✓ 用户登录
- ✓ 密码重置
- ✓ 登出

### 范围外
- ✗ 多因素认证 (MVP 不包含)
- ✗ 社交登录 (后续迭代)

## 用户故事

### 故事 1
```
作为一个新用户
我想要快速注册账户
以便使用系统的功能

验收标准:
- 注册表单包含用户名、邮箱、密码字段
- 系统验证邮箱唯一性
- 注册成功后自动登录
- 用户收到确认邮件
```

### 故事 2
...

## 设计和技术规范

### 技术方案
- 使用 JWT 进行会话管理
- 密码使用 bcrypt 加密
- 使用 Redis 存储会话

### API 规范
[详见 api-design/ 目录]

### 数据库设计
[详见 code-references/ 目录]

## 成功指标
- 用户注册成功率 > 95%
- 登录响应时间 < 1s
- 用户满意度评分 > 4.5/5

## 时间表
- 设计阶段: 2026-03-16 ~ 2026-03-20
- 实现阶段: 2026-03-21 ~ 2026-04-04
- 测试阶段: 2026-04-05 ~ 2026-04-11
- 发布: 2026-04-12

## 风险和缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 密码泄露 | 低 | 高 | 加密存储, 定期审计 |
| 性能问题 | 中 | 中 | 缓存, 数据库优化 |
```

### 3. API 设计 (api-design/)

**endpoints.md 内容**:
```markdown
# API 端点列表

## 认证相关 (Authentication)

### POST /api/v1/auth/register
- **功能**: 用户注册
- **参数**: username, email, password
- **返回**: { token, user_id, message }
- **错误码**: 400, 409 (邮箱已存在)

### POST /api/v1/auth/login
- **功能**: 用户登录
- **参数**: username/email, password, remember_me
- **返回**: { token, expires_in, user }
- **错误码**: 400, 401 (凭证无效)

### POST /api/v1/auth/logout
- **功能**: 用户登出
- **认证**: 需要有效的 token
- **返回**: { message }

### POST /api/v1/auth/refresh
- **功能**: 刷新 token
- **参数**: refresh_token
- **返回**: { token, expires_in }
- **错误码**: 401 (token 过期)

### POST /api/v1/auth/reset-password
- **功能**: 密码重置
- **参数**: email
- **返回**: { message }

## 权限相关 (Permission)

### GET /api/v1/auth/permissions
- **功能**: 获取当前用户权限列表
- **认证**: 需要有效的 token
- **返回**: { permissions: [] }
```

**单个接口详细设计示例**:
```markdown
# API: POST /api/v1/auth/login

## 请求

### URL
```
POST https://api.example.com/api/v1/auth/login
```

### 请求头
```
Content-Type: application/json
```

### 请求体
```json
{
  "username": "john_doe",
  "password": "secure_password_123",
  "remember_me": true
}
```

## 响应

### 成功响应 (200 OK)
```json
{
  "status": "success",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "user": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### 错误响应 (401 Unauthorized)
```json
{
  "status": "error",
  "error_code": "INVALID_CREDENTIALS",
  "message": "用户名或密码错误"
}
```

## 技术细节

### Token 说明
- 类型: JWT (JSON Web Token)
- 有效期: 1 小时
- 刷新令牌有效期: 7 天

### 安全要求
- 密码应至少 8 个字符
- 支持 HTTPS 加密传输
- 实施速率限制（防止暴力破解）
```

### 4. 代码引用 (code-references/)

**auth-module-map.md 内容**:
```markdown
# 认证模块代码映射

## 模块结构

```
backend/
├── auth/                      # 认证模块主目录
│   ├── __init__.py
│   ├── models.py              # 用户和权限数据模型
│   ├── schemas.py             # Pydantic 验证模式
│   ├── service.py             # 业务逻辑
│   ├── routes.py              # API 路由
│   ├── dependencies.py        # 依赖注入
│   ├── utils.py               # 工具函数
│   └── tests/                 # 单元测试
│       ├── test_service.py
│       ├── test_routes.py
│       └── test_utils.py
└── ...
```

## 关键类和函数

### AuthService (auth/service.py)
```python
class AuthService:
    async def register_user(self, username: str, email: str, password: str) -> User
    async def authenticate_user(self, username: str, password: str) -> User
    async def verify_token(self, token: str) -> User
    async def refresh_token(self, refresh_token: str) -> str
    async def reset_password(self, email: str) -> bool
```

### 路由 (auth/routes.py)
- `POST /api/v1/auth/register` -> `register()`
- `POST /api/v1/auth/login` -> `login()`
- `POST /api/v1/auth/logout` -> `logout()`
- `POST /api/v1/auth/refresh` -> `refresh_token()`

## 依赖关系

```
AuthService
├── UserRepository (数据访问)
├── PasswordHasher (密码加密)
├── TokenManager (Token 管理)
└── EmailService (邮件发送)
```

## 测试覆盖

- 单元测试覆盖率: > 80%
- 集成测试: 所有 API 端点
- 安全测试: SQL 注入、XSS、CSRF 防护
```

**db-schema.md 内容**:
```markdown
# 数据库模式

## 用户表 (users)

```sql
CREATE TABLE users (
  user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  username VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  status ENUM('active', 'inactive', 'banned') DEFAULT 'active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login TIMESTAMP,

  INDEX idx_username (username),
  INDEX idx_email (email),
  INDEX idx_created_at (created_at)
);
```

## 权限表 (permissions)

```sql
CREATE TABLE permissions (
  permission_id UUID PRIMARY KEY,
  name VARCHAR(255) UNIQUE NOT NULL,
  description TEXT,
  resource VARCHAR(255),
  action VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uk_resource_action (resource, action)
);
```

## 用户权限关联表 (user_permissions)

```sql
CREATE TABLE user_permissions (
  user_id UUID NOT NULL,
  permission_id UUID NOT NULL,
  granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (user_id, permission_id),
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  FOREIGN KEY (permission_id) REFERENCES permissions(permission_id)
);
```
```

## 验证规则

- 所有接口规范应包含清晰的请求和响应例子
- 代码引用应映射到实际的源代码位置
- 数据库模式应与实际实现一致
- 原型设计应与最终 UI 保持同步

## 维护指南

- 当实现与设计出现偏差时，立即更新文档
- 定期更新 API 文档以反映最新实现
- 保持代码引用的准确性
- 记录设计决策和变更原因
