# 项目事实信息系统 - 使用和维护指南

## 概述

项目事实信息系统是 NextAgent Doc Assistant 的知识底座，存储软件工程项目的结构化信息，Agent 只读访问，由人工维护。

---

## 目录结构

```
project-facts/
├── layer1-inventory/     # 第一层：清单层
│   ├── DATA_FORMAT.md    # 数据格式说明
│   ├── use-cases/        # 用例清单
│   └── modules/          # 功能模块清单
├── layer2-core/          # 第二层：核心信息层
│   ├── DATA_FORMAT.md
│   ├── use-case-descriptions/  # 用例详细描述
│   ├── module-details/         # 模块详细描述
│   ├── class-designs/          # 类包设计
│   └── interfaces/             # 接口清单
└── layer3-design/        # 第三层：设计开发层
    ├── DATA_FORMAT.md
    ├── prototypes/         # 产品原型
    ├── prd/                # PRD 文档
    └── source-refs/        # 源代码引用
```

---

## 三层结构说明

### 第一层：清单层（Agent 初始可见）

用于让 Agent 了解项目范围，只包含摘要信息：

- **用例清单**：系统支持的所有用例列表
- **系统功能清单**：按系统→分系统→子系统→模块层级组织

**适合添加的内容**：
- 项目包含哪些主要功能
- 系统的高层次模块划分

---

### 第二层：核心信息层（按需加载）

当 Agent 需要更多细节时请求此层：

- **用例描述**：参与者、主流程、异常处理
- **功能详细描述**：功能点、依赖关系
- **类包设计**：核心类和包结构
- **接口清单**：API 或模块间接口

**适合添加的内容**：
- 主要业务流程
- 核心数据模型
- 关键 API 定义

---

### 第三层：设计开发层（深度参考）

最细粒度的信息：

- **产品原型**：UI/UX 设计
- **PRD 文档**：完整产品需求
- **源代码引用**：指向实际代码位置

---

## 维护指南

### 添加用例信息

在 `layer1-inventory/use-cases/` 目录下创建 JSON 文件：

```json
{
  "id": "uc-001",
  "name": "用户注册",
  "description": "用户通过邮箱和密码创建账号",
  "actors": ["新用户"],
  "status": "implemented",
  "layer": "manifest",
  "category": "use_case"
}
```

### 添加模块信息

在 `layer1-inventory/modules/` 下创建：

```json
{
  "id": "mod-auth",
  "name": "认证模块",
  "description": "处理用户认证和授权",
  "key_features": ["登录", "注册", "密码重置", "Token管理"],
  "layer": "manifest",
  "category": "module"
}
```

### 更新现有信息

直接编辑对应的 JSON 文件。Agent 每次启动时会重新加载。

---

## 注意事项

1. **Agent 只读**：不要通过 Agent 修改事实信息，所有更新通过手动编辑文件完成
2. **ID 唯一性**：每条记录的 `id` 字段在整个系统中必须唯一
3. **层级关联**：第二、三层记录应通过 `related_ids` 字段引用第一层的 ID
4. **格式规范**：文件内容使用 UTF-8 编码，JSON 格式规范

---

## 访问控制

| 角色 | 权限 |
|------|------|
| Agent | 只读（query/search） |
| Admin | 完全控制（CRUD） |

人工维护通过直接编辑文件系统实现，无需通过 API。
