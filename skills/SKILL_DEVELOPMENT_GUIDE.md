# 文档编写 Skill 开发指南

本指南说明如何开发符合 NextAgent Doc Assistant 规范的文档编写 Skill。

---

## 一、核心概念

### 什么是 Skill

Skill 是一个**独立的文档编写模块**，封装了某一类型文档的生成逻辑。每个 Skill：
- 以独立目录的形式存在于 `skills/` 下
- 通过 `skill.md` 声明元信息和描述能力
- 由 Agent 在运行时自动发现、加载并调用
- 负责将用户需求转换为高质量的 Markdown 文档

### Skill 与 Agent 的关系

```
用户  ──(自然语言)──▶  Agent  ──(选择 Skill)──▶  Skill  ──(生成文档)──▶  docs/
                          │
                          └─(查询)──▶  项目事实信息
```

Agent 根据用户意图匹配最合适的 Skill，并将执行上下文（用户需求 + 项目事实信息）传递给它。

---

## 二、Skill 目录结构

```
skills/
└── [skill-id]/                  # 必需；kebab-case 命名，如 write-requirements
    ├── skill.md                 # 必需；Skill 定义文件
    ├── scripts/
    │   └── main.py              # 推荐；主实现脚本
    └── reference/               # 可选；模板、示例等参考资料
        └── template.md
```

**命名规范**：Skill 目录名即为 Skill ID，使用 kebab-case（小写字母、数字、连字符），例如：
- `write-requirements`
- `write-design-doc`
- `write-api-doc`
- `write-test-plan`

---

## 三、skill.md 格式规范

`skill.md` 是 Skill 的核心定义文件，分为两部分：

### 3.1 元信息块（必需）

在文件顶部放置一个 YAML 代码块（` ```yaml ... ``` `）声明元信息：

```yaml
Skill Name: 需求规格文档编写
Description: 根据用户需求和项目事实信息，编写符合规范的软件需求规格文档（SRS）
Type: document-writing
Version: 1.0.0
Author: Your Name
Tags:
  - requirements
  - srs
  - specification
Input Parameters:
  - name: project_module
    type: string
    required: true
    description: 目标模块名称（如"用户认证模块"）
  - name: base_version
    type: string
    required: false
    description: 修改场景下的基础版本路径
Output Format: markdown
Capabilities:
  - 软件需求规格文档（SRS）
  - 功能需求分析
  - 非功能需求整理
  - 用例描述
Constraints:
  - 输出语言：中文
  - 输出格式：Markdown
  - 依赖项目事实信息中的用例清单和功能描述
```

#### 必需字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `Skill Name` | Skill 的中文名称，显示在 UI 中 | `需求规格文档编写` |
| `Description` | 一句话描述 Skill 的功能 | `编写软件需求规格文档` |
| `Type` | 固定值 `document-writing` | `document-writing` |

#### 可选字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `Version` | Skill 版本号 | `1.0.0` |
| `Author` | 开发者姓名 | `张三` |
| `Tags` | 标签列表，用于搜索 | `requirements, srs` |
| `Input Parameters` | 参数定义列表 | 见上示例 |
| `Output Format` | 输出格式，通常是 `markdown` | `markdown` |
| `Capabilities` | Skill 能力列表，Agent 用于匹配用户意图 | 见上示例 |
| `Constraints` | 约束条件 | 见上示例 |

### 3.2 详细描述（推荐）

元信息块之后，用 Markdown 正文详细描述 Skill：

```markdown
## 概述

本 Skill 帮助用户编写符合国家标准或企业规范的软件需求规格文档（SRS）。
输入为目标模块名称，输出为完整的需求规格 Markdown 文档。

## 能力范围

### 支持
- 根据项目用例清单生成需求概述
- 描述功能需求和非功能需求
- 生成用例描述章节
- 支持精准修改（基于已有版本）

### 不支持
- 生成 UML 图（仅文字描述）
- 自动获取代码级别的实现细节

## 输入要求

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| project_module | string | 是 | 模块名称 |
| base_version | string | 否 | 待修改的文档版本路径 |

来自 Agent 的上下文（自动注入）：
- 项目事实信息（用例清单、功能描述）
- 对话历史
- 用户确认的需求点

## 输出规范

输出为标准 Markdown 格式，包含：
1. 文档标题和元信息
2. 范围
3. 功能需求
4. 非功能需求
5. 约束条件
6. 附录
```

---

## 四、与项目事实信息的集成

Skill 脚本通过 Agent 注入的上下文对象访问只读的项目事实信息：

```python
# 在 scripts/main.py 中

async def handle_request(context: dict) -> dict:
    """
    context 由 Agent 提供，包含：
    - context["user_requirement"]: 用户的原始需求描述
    - context["fact_info"]: 项目事实信息（只读）
      - context["fact_info"]["usecases"]: 用例清单
      - context["fact_info"]["modules"]: 模块清单
      - context["fact_info"]["interfaces"]: 接口列表（如有）
    - context["conversation_history"]: 近期对话历史
    - context["base_document"]: 待修改的文档内容（精准修改场景）
    - context["llm_service"]: LLM 服务（可选，供 Skill 内部调用 LLM）
    """

    # 读取项目事实信息
    usecases = context["fact_info"].get("usecases", [])
    modules = context["fact_info"].get("modules", [])

    # 读取用户需求
    requirement = context["user_requirement"]

    # 可选：调用 LLM 生成内容
    if "llm_service" in context:
        llm = context["llm_service"]
        content = await llm.complete(
            system_prompt="你是一个需求分析专家...",
            messages=[],
            user_message=requirement,
        )
    else:
        content = "..."  # 使用模板逻辑

    # 返回生成的文档
    return {
        "status": "success",
        "document": content,
        "metadata": {
            "doc_type": "requirements",
            "doc_name": "需求规格-模块名",
        }
    }
```

---

## 五、输入参数和输出格式标准

### 输入（由 Agent 传入）

```python
context = {
    "user_requirement": str,         # 用户的自然语言需求
    "conversation_history": list,    # 近 N 轮对话历史
    "fact_info": {                   # 项目事实信息（只读）
        "usecases": list,
        "modules": list,
        "interfaces": list,
    },
    "base_document": str | None,     # 精准修改时的基础文档内容
    "skill_params": dict,            # skill.md 中定义的参数值
    "llm_service": object | None,    # LLM 服务（可选）
}
```

### 输出（Skill 返回）

```python
result = {
    "status": "success" | "error",

    # 成功时
    "document": str,              # 文档内容（Markdown 格式）
    "metadata": {
        "doc_type": str,          # 文档类型（requirements/design/api/test/...）
        "doc_name": str,          # 文档名称（用于保存路径）
        "title": str,             # 文档标题（可选）
    },

    # 失败时
    "error_message": str,
    "error_type": str,
}
```

---

## 六、最佳实践

1. **保持单一职责**：每个 Skill 只生成一类文档。
2. **利用项目事实信息**：优先从事实信息中获取数据，而非硬编码。
3. **支持精准修改**：检查 `context["base_document"]`，如有则基于已有文档修改，而非重新生成。
4. **明确的错误消息**：返回用户可理解的中文错误提示。
5. **文档结构一致性**：使用统一的文档标题、章节结构，便于版本比较。
6. **测试你的 Skill**：在 `scripts/` 下提供本地测试脚本。

---

## 七、开发流程

1. 复制 `skills/_template/` 目录，重命名为你的 Skill ID
2. 编辑 `skill.md`，填写元信息和详细描述
3. 实现 `scripts/main.py` 中的 `handle_request` 函数
4. 本地测试：`python scripts/main.py`
5. 将 Skill 目录放入 `skills/`，重启 Agent 即可自动加载
