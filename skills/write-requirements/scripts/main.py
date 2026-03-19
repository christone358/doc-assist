"""
write-requirements - Requirements Specification Document Skill

Reference implementation for writing software requirements specification (SRS) documents.
This is an example implementation. Users should customize it for their project needs.
"""

import json
from datetime import datetime
from typing import Any, Dict


async def handle_request(context: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a requirements specification document.

    Args:
        context: Agent-provided context including user requirements and project facts

    Returns:
        Dictionary containing the generated document and metadata
    """
    try:
        requirement = context.get("user_requirement", "")
        fact_info = context.get("fact_info", {})
        base_document = context.get("base_document")
        skill_params = context.get("skill_params", {})
        llm_service = context.get("llm_service")

        module_name = skill_params.get("project_module", "目标模块")
        today = datetime.now().strftime("%Y-%m-%d")

        # If modifying an existing document
        if base_document:
            return await _modify_document(
                base_document=base_document,
                requirement=requirement,
                llm_service=llm_service,
                module_name=module_name,
            )

        # Generate new document
        return await _generate_new_document(
            requirement=requirement,
            fact_info=fact_info,
            module_name=module_name,
            today=today,
            llm_service=llm_service,
        )

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"生成需求规格文档失败：{str(e)}",
            "error_type": type(e).__name__,
        }


async def _generate_new_document(
    requirement: str,
    fact_info: dict,
    module_name: str,
    today: str,
    llm_service=None,
) -> Dict[str, Any]:
    """Generate a new requirements specification document."""

    # Extract relevant project facts
    usecases = fact_info.get("usecases", [])
    modules = fact_info.get("modules", [])

    # Build usecases section from facts
    uc_section = ""
    if usecases:
        uc_section = "\n".join(
            f"- **{uc.get('id', '')}**: {uc.get('name', '')} — {uc.get('description', '')}"
            for uc in usecases[:10]
        )

    if llm_service:
        prompt = f"""请根据以下信息，为"{module_name}"编写一份完整的软件需求规格文档（Markdown格式）。

用户需求：{requirement}

相关用例：
{uc_section or "（暂无）"}

请按照以下结构编写：
1. 文档信息
2. 概述（目的、范围）
3. 功能需求
4. 非功能需求
5. 约束条件

输出语言：中文，格式：Markdown
"""
        content = await llm_service.complete(
            system_prompt="你是一名资深软件需求分析师，擅长编写清晰、完整的需求规格文档。",
            messages=[],
            user_message=prompt,
        )
    else:
        # Fallback template when no LLM is configured
        content = f"""# 需求规格文档 - {module_name}

| 属性 | 值 |
|------|----|
| 文档版本 | v1.0.0 |
| 创建日期 | {today} |
| 模块名称 | {module_name} |

---

## 1. 概述

### 1.1 目的
本文档描述 {module_name} 的软件需求规格，为开发团队提供明确的功能和非功能需求定义。

### 1.2 范围
本文档覆盖 {module_name} 的所有功能模块。

---

## 2. 功能需求

> 用户需求：{requirement}

*（请根据实际项目需求补充具体功能需求）*

---

## 3. 非功能需求

### 3.1 性能要求
- 响应时间 < 1 秒（P99）

### 3.2 安全要求
- 所有接口需要身份验证
- 敏感数据加密存储

### 3.3 可用性要求
- 系统可用性 > 99.9%

---

## 4. 约束条件

- 遵循公司代码规范
- 依赖现有基础设施

---

*本文档由 NextAgent Doc Assistant 生成*
"""

    return {
        "status": "success",
        "document": content,
        "metadata": {
            "doc_type": "requirements",
            "doc_name": f"需求规格-{module_name}",
            "title": f"需求规格文档 - {module_name}",
        },
    }


async def _modify_document(
    base_document: str,
    requirement: str,
    llm_service=None,
    module_name: str = "",
) -> Dict[str, Any]:
    """Modify an existing requirements document."""
    if llm_service:
        prompt = f"""请根据以下修改要求，对已有的需求规格文档进行精准修改。

修改要求：{requirement}

已有文档：
{base_document}

要求：
1. 只修改与需求相关的部分
2. 保持文档其他内容不变
3. 输出完整的修改后文档（Markdown格式）
4. 修改的部分可以适当说明修改原因
"""
        content = await llm_service.complete(
            system_prompt="你是一名资深软件需求分析师，请对文档进行精准、专业的修改。",
            messages=[],
            user_message=prompt,
        )
    else:
        content = base_document + f"\n\n---\n\n*修改记录：{requirement}（请人工完成修改）*"

    return {
        "status": "success",
        "document": content,
        "metadata": {
            "doc_type": "requirements",
            "doc_name": f"需求规格-{module_name}",
            "title": f"需求规格文档 - {module_name}（已修改）",
        },
    }


if __name__ == "__main__":
    """Local testing."""
    import asyncio

    test_context = {
        "user_requirement": "编写用户认证模块的需求规格文档",
        "fact_info": {
            "usecases": [
                {"id": "UC-001", "name": "用户登录", "description": "用户通过用户名密码登录"},
                {"id": "UC-002", "name": "用户注册", "description": "新用户创建账户"},
            ]
        },
        "skill_params": {"project_module": "用户认证模块"},
    }

    result = asyncio.run(handle_request(test_context))
    print(result["document"])
