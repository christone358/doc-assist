# [Skill 名称]

```yaml
Skill Name: [写在这里]
Description: [写在这里]
Type: document-writing
Version: 1.0.0
Author: [Your Name]
Tags:
  - [tag1]
  - [tag2]
Input Parameters:
  - name: [parameter_name]
    type: string
    required: true
    description: [参数描述]
Output Format: markdown
Capabilities:
  - [能力1]
  - [能力2]
Constraints:
  - [约束1]
```

## 概述

*在这里描述 Skill 的整体功能和目标*

## 能力范围

### 支持的功能
- *列出 Skill 支持的所有功能*
- *例如：需求分析、文档结构设计等*

### 不支持的功能
- *明确说明不支持的内容*

## 输入要求

| 参数名称 | 类型 | 必需 | 说明 |
|---------|------|------|------|
| parameter1 | string | 是 | 说明 |
| parameter2 | integer | 否 | 说明 |

## 输出规范

生成的文档应该包含：
- 标题部分
- 目录（可选）
- 正文内容
- 附录（可选）

## 配置说明

*如有特殊配置要求，在这里说明*

## 使用示例

```python
# 如何调用该 Skill
skill_input = {
    "parameter1": "value1",
    "parameter2": "value2"
}

# Agent 会将请求发送给该 Skill
result = await execute_skill("skill-name", skill_input)
```

## 错误处理

| 错误类型 | 原因 | 处理方案 |
|---------|------|---------|
| InvalidInput | 输入参数不合法 | 返回清晰的错误提示 |
| ProcessingError | 处理过程出错 | 返回错误日志和建议 |

## 扩展性

*说明该 Skill 如何扩展或定制*

---

*删除这个示例文件，使用你自己的 skill.md*
