from pathlib import Path

from agent.context_loader import load_context
from agent.adk.fact_tools import _summarize_overview, get_fact_detail


def test_load_context_filters_usecases_by_markdown_module_field(tmp_path):
    facts_root = tmp_path
    (facts_root / "usecases.md").write_text(
        """# 用例清单

### UC-001: 配置模型
- **模块**: mod-llm
- **角色**: 用户
- **描述**: 配置 LLM 模型。

### UC-002: 其他模块用例
- **模块**: mod-agent
- **角色**: 用户
- **描述**: 其他说明。
""",
        encoding="utf-8",
    )

    result = load_context("usecases", "mod-llm", facts_root)

    assert len(result) == 1
    assert "UC-001: 配置模型" in result[0]
    assert "UC-002" not in result[0]


def test_summarize_modules_overview_includes_module_ids():
    result = """# 功能模块清单

## Agent 核心模块 {#mod-agent}

## LLM 集成模块 {#mod-llm}

## Web UI 模块 {#mod-webui}
"""

    summary = _summarize_overview("modules", result)

    assert "LLM 集成模块(mod-llm)" in summary
    assert "Agent 核心模块(mod-agent)" in summary


def test_summarize_usecases_overview_includes_module_ids():
    result = """# 用例清单

### UC-016: 用户配置和管理 LLM 模型
- **模块**: mod-llm
- **角色**: 用户

### UC-017: Agent 选择合适的 LLM 模型执行任务
- **模块**: mod-llm
- **角色**: 系统
"""

    summary = _summarize_overview("usecases", result)

    assert "UC-016 用户配置和管理 LLM 模型(mod-llm)" in summary
    assert "UC-017 Agent 选择合适的 LLM 模型执行任务(mod-llm)" in summary


def test_get_fact_detail_can_load_module_usecases_from_real_facts():
    content = get_fact_detail("mod-llm", "usecases")

    assert "UC-016: 用户配置和管理 LLM 模型" in content
    assert "UC-017: Agent 选择合适的 LLM 模型执行任务" in content
