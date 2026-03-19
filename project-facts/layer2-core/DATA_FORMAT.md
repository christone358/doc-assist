# 核心信息层数据格式设计

核心信息层（Layer 2 - Core Information）提供项目的详细说明，包括用例、功能、模块设计等核心内容。

## 数据格式规范

### 1. 用例描述 (usecases/)

**文件结构**: 每个用例一个文件，命名为 `UC-[序号].md`

**内容格式**:
```markdown
# UC-001: 用例名称

## 基本信息
- **用例ID**: UC-001
- **所属模块**: 模块名称
- **优先级**: 高/中/低
- **状态**: 完成/进行中/待做

## 概述
[用例的简明介绍和目标]

## 前置条件
1. 系统可用
2. 用户已注册
3. [其他前置条件]

## 主流程 (Main Flow)
1. 用户执行操作 A
2. 系统处理请求
3. 系统返回结果
4. 用户确认完成

## 备选流程 (Alternative Flows)

### 备选流程 1: 用户权限不足
1. 在步骤 2 中，如果用户无权限
2. 系统显示"权限不足"错误
3. 返回首页

### 备选流程 2: 系统出错
...

## 后置条件
1. 系统状态更新
2. 用户获得反馈
3. [其他后置条件]

## 相关接口
- API-001: POST /api/v1/operation
- API-002: GET /api/v1/status

## 相关数据实体
- Entity-A
- Entity-B

## 备注
[任何其他重要说明]
```

**数据结构**:
```json
{
  "id": "UC-001",
  "name": "用例名称",
  "module_id": "MOD-A",
  "priority": "high",
  "status": "completed",
  "preconditions": ["系统可用", "用户已认证"],
  "main_flow": ["步骤1", "步骤2", "步骤3"],
  "alternative_flows": {
    "error_handling": ["错误步骤1", "错误步骤2"],
    "user_cancel": ["取消步骤1"]
  },
  "postconditions": ["状态更新"],
  "related_apis": ["API-001"],
  "related_entities": ["Entity-A"],
  "created_at": "2026-03-16T00:00:00Z",
  "updated_at": "2026-03-16T00:00:00Z"
}
```

### 2. 功能描述 (features/)

**文件结构**: 按功能命名，如 `feature-auth.md`

**内容格式**:
```markdown
# 功能: 用户认证

## 功能概述
- **功能ID**: FEAT-AUTH
- **所属模块**: 认证模块
- **优先级**: 高
- **覆盖用例**: UC-001, UC-002, UC-003

## 功能描述
[详细的功能说明，包括功能范围、目标用户等]

## 功能需求

### 功能需求 FR-1: 用户登录
- 用户可以通过用户名和密码登录
- 系统应验证凭证有效性
- 登录失败应显示错误提示

### 功能需求 FR-2: 密码重置
...

## 非功能需求 (NFR)
- 登录延迟应 < 1 秒
- 支持并发用户数 > 1000
- 可用性 > 99.9%

## 数据要求
- 用户表包含的字段
- 权限映射关系
- 日志记录需求

## 接口要求
- 登录接口: POST /api/v1/auth/login
- 注销接口: POST /api/v1/auth/logout
- 权限检查接口: GET /api/v1/auth/verify

## 集成点
- 与数据库的集成
- 与日志系统的集成
- 与审计系统的集成

## 相关规范和标准
- OAuth2.0 认证标准
- OWASP 安全指南
```

**数据结构**:
```json
{
  "id": "FEAT-AUTH",
  "name": "用户认证",
  "module_id": "MOD-AUTH",
  "priority": "high",
  "usecases": ["UC-001", "UC-002"],
  "functional_requirements": [
    {
      "id": "FR-1",
      "title": "用户登录",
      "description": "用户可以登录系统"
    }
  ],
  "non_functional_requirements": {
    "response_time": "< 1s",
    "concurrent_users": "> 1000",
    "availability": "> 99.9%"
  },
  "apis": ["POST /api/v1/auth/login"],
  "status": "active"
}
```

### 3. 架构设计 (architecture/)

**文件结构**:
- `modules.md` - 模块设计说明
- `interfaces.md` - 接口清单
- `data-flow.md` - 数据流图
- `sequence-diagram.md` - 序列图

**modules.md 内容**:
```markdown
# 模块设计

## 系统架构
[整体架构图和说明]

## 核心模块说明

### 认证模块 (MOD-AUTH)
- **职责**: 处理用户认证和权限管理
- **主要组件**:
  - 登录服务: 处理登录请求
  - 权限检查: 检查用户权限
  - Token管理: 管理认证Token
- **依赖**: 数据库模块, 日志模块
- **接口**: 见 interfaces.md

### 数据模块 (MOD-DATA)
...

## 模块交互
[模块之间的交互方式和通信协议]
```

### 4. 数据模型 (data-model/)

**entities.md 内容**:
```markdown
# 数据实体

## 用户实体 (User)

### 基本属性
| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | UUID | PK | 用户唯一标识 |
| username | VARCHAR(255) | UNIQUE NOT NULL | 用户名 |
| email | VARCHAR(255) | UNIQUE NOT NULL | 邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |
| status | ENUM | NOT NULL | 状态 (active, inactive) |

### 索引
- PRIMARY KEY (user_id)
- UNIQUE (username)
- UNIQUE (email)

## 权限实体 (Permission)
...

## 关系
- User 1-* Permission (一个用户对应多个权限)
- Permission 1-* Resource (一个权限对应多个资源)
```

## 验证规则

- 所有用例描述应包含主流程
- 功能描述应关联至少一个用例
- 所有接口应有清晰的输入输出说明
- 数据实体应包含完整的字段定义

## 维护指南

- 当需求变更时，及时更新功能描述
- 保持用例和功能描述的一致性
- 定期审查架构设计，考虑技术进展
- 记录设计决策的历史和原因
