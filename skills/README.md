# Skill 框架目录结构

本目录用于存放用户自定义的文档编写 Skill 模块。

## Skill 目录结构

每个 Skill 应按以下结构组织：

```
skills/
├── [skill-name]/                    # Skill 标识符（kebab-case）
│   ├── skill.md                     # Skill 元信息和说明文档
│   ├── scripts/                     # Skill 实现脚本
│   │   └── main.py                  # 主实现文件
│   │   ├── helper.py                # 辅助模块（可选）
│   │   └── config.json              # 配置文件（可选）
│   └── reference/                   # 参考资源（可选）
│       ├── template.md              # 文档模板
│       ├── examples/                # 示例文件
│       └── guidelines.md            # 编写指南
└── [other-skill]/
    └── ...
```

## skill.md 元信息格式

每个 Skill 的 `skill.md` 应包含以下部分（前置声明 + 详细描述）：

### 前置声明（YAML 格式，在代码块中）

```yaml
# 必需字段
Skill Name: 文档编写 - 需求规格
Description: 用于编写软件工程项目的需求规格文档
Type: document-writing
Version: 1.0.0

# 可选字段
Author: Your Name
Tags:
  - requirements
  - specification
  - documentation
Input Parameters:
  - name: project_name
    type: string
    required: true
    description: 项目名称
Output Format: markdown
Capabilities:
  - 需求分析和整理
  - 需求规格文档生成
  - 版本控制支持
Constraints:
  - 仅支持中文输入
  - 输出格式为 Markdown
```

### 详细描述部分

1. **概述**：Skill 的简明介绍
2. **能力范围**：该 Skill 能做什么，不能做什么
3. **输入要求**：需要从用户或 Agent 接收的数据
4. **输出规范**：生成的文档格式和结构
5. **配置说明**：如有特殊配置需求
6. **使用示例**：调用该 Skill 的示例代码或命令
7. **错误处理**：可能的错误和处理方式
8. **扩展性**：如何扩展或定制该 Skill

## Skill 开发指南

### 基本要求

1. **命名规范**：使用 kebab-case 命名 Skill 目录
   - 例：`write-requirements`, `api-documentation`, `test-plan`

2. **必需文件**：
   - `skill.md`：Skill 定义和说明
   - `scripts/main.py`：主实现文件

3. **可选文件**：
   - `scripts/helper.py` 等辅助模块
   - `reference/` 目录中的文档和示例

### 实现规范

- 使用 Python 3.11+ 实现
- 遵循 PEP 8 代码风格
- 编写单元测试
- 提供清晰的错误消息

### 输入和输出

**输入**：
- Agent 通过 JSON 格式传递参数
- 包含用户需求、项目信息、版本信息等

**输出**：
- 生成的文档内容（Markdown 格式）
- 包含文档元数据（标题、日期、版本等）

### 与项目事实信息的集成

Skill 可以访问只读的项目事实信息库，用于：
- 获取项目信息（模块、接口、用例等）
- 推荐相关的设计决策
- 引用已有的文档内容

```python
# 示例：在 Skill 中访问项目事实信息
from agent.fact_info import FactInformationService

fact_service = FactInformationService()
usecases = fact_service.query(layer='manifest', category='usecases')
api_interfaces = fact_service.query(layer='core', category='interfaces')
```

## Skill 自动发现

系统启动时会自动：
1. 扫描 `skills/` 目录
2. 验证每个 Skill 的有效性（必需文件、元信息完整）
3. 加载和注册 Skill 到管理器
4. 记录加载过程中的任何错误

## 示例 Skill

系统不包含任何预置 Skill。用户根据需要自行创建。

参考 OpenSpec 规格中的"文档编写Skill的开发指南"，了解如何编写自己的 Skill。

## 常见问题

**Q：如何创建新的 Skill？**
A：参考开发指南，在 `skills/` 目录下创建新目录，按标准结构组织文件。

**Q：Skill 之间可以互相调用吗？**
A：可以，通过 Agent 的任务编排机制。

**Q：如何测试我的 Skill？**
A：编写单元测试并在本地运行，或通过 Web UI 直接测试。

**Q：Skill 可以访问文件系统吗？**
A：可以，但应该限制在安全的目录范围内。

**Q：如何处理 Skill 执行失败？**
A：实现清晰的错误处理，返回错误消息和建议的修复方案。
