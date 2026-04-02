import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

from agent.adk import fact_tools
from agent.context_loader import load_context
from agent.adk.fact_tools import (
    _classify_fact_result,
    _classify_module_resolution_result,
    _summarize_detail,
    _summarize_module_fact_sheet,
    _summarize_overview,
    get_fact_overview,
    get_fact_detail,
    create_fact_tools,
    resolve_target_module,
)
from project_fact_modules import ModuleArchiveRepository


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


def test_summarize_modules_overview_uses_module_archive_names():
    result = """# 功能模块清单

## Agent 核心模块 {#mod-agent}

## LLM 集成模块 {#mod-llm}

## Web UI 模块 {#mod-webui}
"""

    summary = _summarize_overview("modules", result)

    assert summary == "已加载模块档案概览：Agent 核心模块、LLM 集成模块、Web UI 模块"


def test_summarize_systems_overview_uses_system_names():
    result = """# 系统概览

## 业务保障管理系统

## 业务协同管理系统
"""

    summary = _summarize_overview("systems", result)

    assert summary == "已加载系统概览：业务保障管理系统、业务协同管理系统"


def test_summarize_function_points_overview_uses_module_names():
    result = """# 功能点概览

## 云主机资产管理 {#mod-cloud}
- [云服务资产列表] 资产导入

## 终端资产管理 {#mod-endpoint}
- [终端资产列表] 资产登记
"""

    summary = _summarize_overview("function_points", result)

    assert summary == "已加载功能点概览：云主机资产管理、终端资产管理"


def test_summarize_usecases_overview_uses_module_names():
    result = """# 用例概览

## 云主机资产管理 {#mod-cloud}
- 查看资产列表 [资产管理员]: 查看资产列表数据

## 终端资产管理 {#mod-endpoint}
- 导出资产清单 [资产管理员]: 导出筛选后的资产清单
"""

    summary = _summarize_overview("usecases", result)

    assert summary == "已加载用例信息概览：云主机资产管理、终端资产管理"


def test_summarize_overview_reports_empty_result_explicitly():
    summary = _summarize_overview("modules", "未找到 modules 概览信息。")

    assert summary == "未加载到数据：未找到 modules 概览信息。"


def test_summarize_detail_reports_error_explicitly():
    summary = _summarize_detail(
        "mod-llm",
        "function_points",
        "project-facts 目录不存在，无法加载 function_points 详情。",
    )

    assert summary == "加载失败：project-facts 目录不存在，无法加载 function_points 详情。"


def test_summarize_module_fact_sheet_returns_agent_readable_structure():
    result = """# 脆弱性管理

## 基本信息
- 所属系统: 业务协同管理系统
- 所属子系统: 业务运行保障

## 功能描述
面向企业员工，提供脆弱性管理功能，实现资产脆弱性的查看和处置。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
_待补充_

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 脆弱性总览 | 脆弱性概览 |  |  |
| 脆弱性列表 | 脆弱性视图统计 |  |  |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|
_待补充_

## 页面 / 原型
_待补充_

## 包 / 类
- VulnerabilityService

## 依赖模块
- 无

## 备注
由资产功能规划导入
"""

    summary = _summarize_module_fact_sheet("脆弱性管理", result)

    assert "已加载模块事实主档：" in summary
    assert "- 模块: 脆弱性管理" in summary
    assert "- 所属系统: 业务协同管理系统" in summary
    assert "- 所属子系统: 业务运行保障" in summary
    assert "- 功能描述: 面向企业员工，提供脆弱性管理功能，实现资产脆弱性的查看和处置。" in summary
    assert "- 用例信息: 待补充" in summary
    assert "- 功能点: 共 2 项；脆弱性概览、脆弱性视图统计" in summary
    assert "- API 清单: 待补充" in summary
    assert "- 页面 / 原型: 待补充" in summary
    assert "- 包 / 类: VulnerabilityService" in summary
    assert "- 依赖模块: 无" in summary
    assert "- 主档已覆盖以上章节；仅在用户明确追问专项细节时再补充 get_fact_detail。" in summary


def test_load_module_fact_sheet_fn_returns_full_fact_sheet_text(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "脆弱性管理.md").write_text(
        """# 脆弱性管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 资产脆弱性管理

## 功能描述
面向资产管理员，提供脆弱性全生命周期管理。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
_待补充_

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 脆弱性列表 | 脆弱性检索 | 支持条件筛选 |  |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|
_待补充_

## 页面 / 原型
_待补充_

## 包 / 类
_待补充_

## 依赖模块
- 无

## 备注
由测试生成
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    class DummyCtx:
        def __init__(self):
            self.collected_facts_parts = []
            self.ws_sender = AsyncMock()

    ctx = DummyCtx()
    _, load_module_fact_sheet_fn, _, _ = create_fact_tools(ctx)

    result = asyncio.run(load_module_fact_sheet_fn("脆弱性管理"))

    assert "# 脆弱性管理" in result
    assert "## 功能描述" in result
    assert "## 功能点" in result
    assert ctx.collected_facts_parts
    ctx.ws_sender.assert_awaited()


def test_resolve_target_module_fn_remembers_current_module_identity(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "脆弱性管理.md").write_text(
        """# 脆弱性管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 资产脆弱性管理

## 功能描述
提供脆弱性处理能力。
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    repo = ModuleArchiveRepository(facts_root)
    module_id = repo.archives[0].module_id

    class DummyCtx:
        def __init__(self):
            self.collected_facts_parts = []
            self.ws_sender = AsyncMock()
            self.current_module_id = None
            self.current_module_name = None
            self.current_system_name = None
            self.current_subsystem_name = None

    ctx = DummyCtx()
    resolve_target_module_fn, _, _, _ = create_fact_tools(ctx)

    result = asyncio.run(resolve_target_module_fn("脆弱性管理"))

    assert "模块定位结果：FOUND" in result
    assert ctx.current_module_id == module_id
    assert ctx.current_module_name == "脆弱性管理"
    assert ctx.current_system_name == "业务保障管理系统"
    assert ctx.current_subsystem_name == "资产脆弱性管理"


def test_classify_fact_result_distinguishes_success_empty_and_error():
    assert _classify_fact_result("已找到内容") == "success"
    assert _classify_fact_result("未找到 target_id='mod-llm' 的 usecases 信息。") == "empty"
    assert _classify_fact_result("不支持的事实类型 'foo'。") == "error"


def test_classify_module_resolution_result_distinguishes_outcomes():
    assert _classify_module_resolution_result("模块定位结果：FOUND\n- 模块: A") == "success"
    assert _classify_module_resolution_result("模块定位结果：NOT_FOUND\n- 输入: A") == "empty"
    assert _classify_module_resolution_result("模块定位结果：AMBIGUOUS\n- 输入: A") == "error"


def test_get_fact_detail_can_load_module_usecases_from_temp_facts(tmp_path, monkeypatch):
    (tmp_path / "usecases.md").write_text(
        """# 用例清单

### UC-016: 用户配置和管理 LLM 模型
- **模块**: mod-llm
- **角色**: 用户
- **描述**: 配置模型。

### UC-017: Agent 选择合适的 LLM 模型执行任务
- **模块**: mod-llm
- **角色**: 系统
- **描述**: 自动选择模型。
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", tmp_path)

    content = get_fact_detail("mod-llm", "usecases")

    assert "UC-016: 用户配置和管理 LLM 模型" in content
    assert "UC-017: Agent 选择合适的 LLM 模型执行任务" in content


def test_get_fact_overview_can_load_systems_from_module_archives(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "云主机资产管理.md").write_text(
        """# 云主机资产管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 保障资产管理

## 功能描述
描述

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 子模块A | 功能点A | 描述A | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 列表页

## 包 / 类
- CloudHostService

## 依赖模块
- 无

## 备注
无
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    content = get_fact_overview("systems")

    assert "## 业务保障管理系统" in content
    assert "- 模块数: 1" in content


def test_get_fact_detail_can_load_module_sections_from_module_archives(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "云主机资产管理.md").write_text(
        """# 云主机资产管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 保障资产管理

## 功能描述
面向资产管理员，提供云资源自动化同步监控能力。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看资产列表 | 查看资产列表数据 | 资产管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 云服务资产列表 | 资产导入 | 批量导入云主机资产 | 已完成 |
| 云服务资产列表 | 资产更新 | 更新资产信息 | 进行中 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|
| 云主机查询接口 | 查询云主机列表 | /api/cloud-hosts | GET |

## 页面 / 原型
- 云主机列表页

## 包 / 类
- CloudHostService

## 依赖模块
- 公共资产模块

## 备注
由测试生成
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    overview = get_fact_overview("modules")
    assert "{#mod-" in overview
    target_id = overview.split("{#")[1].split("}")[0]

    module_content = get_fact_detail(target_id, "module")
    usecases = get_fact_detail(target_id, "usecases")
    function_points = get_fact_detail(target_id, "function_points")
    apis = get_fact_detail(target_id, "apis")
    dependencies = get_fact_detail(target_id, "dependencies")

    assert "# 云主机资产管理" in module_content
    assert "## 用例信息" in usecases
    assert "查看资产列表" in usecases
    assert "## 功能点" in function_points
    assert "资产导入" in function_points
    assert "## API 清单" in apis
    assert "云主机查询接口" in apis
    assert "## 依赖模块" in dependencies
    assert "公共资产模块" in dependencies


def test_resolve_target_module_can_find_unique_scoped_module(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "系统A-脆弱性管理.md").write_text(
        """# 脆弱性管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 资产脆弱性管理

## 功能描述
系统A中的脆弱性管理模块。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看脆弱性列表 | 查看数据 | 管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 默认子模块 | 功能点A | 描述A | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 列表页

## 包 / 类
- VulnerabilityService

## 依赖模块
- 公共模块

## 备注
无
""",
        encoding="utf-8",
    )
    (modules_dir / "系统B-脆弱性管理.md").write_text(
        """# 脆弱性管理

## 基本信息
- 所属系统: 业务协同管理系统
- 所属子系统: 业务运行保障

## 功能描述
系统B中的脆弱性管理模块。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看脆弱性列表 | 查看数据 | 管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 默认子模块 | 功能点A | 描述A | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 列表页

## 包 / 类
- VulnerabilityService

## 依赖模块
- 公共模块

## 备注
无
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    content = resolve_target_module("业务保障管理系统/脆弱性管理模块")

    assert content.startswith("模块定位结果：FOUND")
    assert "- 所属系统: 业务保障管理系统" in content
    assert "- 所属子系统: 资产脆弱性管理" in content
    assert "- 模块ID: mod-" in content


def test_resolve_target_module_reports_ambiguity(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    for system_name, subsystem_name in (
        ("业务保障管理系统", "资产脆弱性管理"),
        ("业务协同管理系统", "业务运行保障"),
    ):
        (modules_dir / f"{system_name}-脆弱性管理.md").write_text(
            f"""# 脆弱性管理

## 基本信息
- 所属系统: {system_name}
- 所属子系统: {subsystem_name}

## 功能描述
{system_name}中的脆弱性管理模块。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看脆弱性列表 | 查看数据 | 管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 默认子模块 | 功能点A | 描述A | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 列表页

## 包 / 类
- VulnerabilityService

## 依赖模块
- 公共模块

## 备注
无
""",
            encoding="utf-8",
        )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    content = resolve_target_module("脆弱性管理")

    assert content.startswith("模块定位结果：AMBIGUOUS")
    assert "业务保障管理系统 / 资产脆弱性管理 / 脆弱性管理" in content
    assert "业务协同管理系统 / 业务运行保障 / 脆弱性管理" in content


def test_get_fact_detail_can_resolve_module_name_from_module_archives(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "业务系统管理.md").write_text(
        """# 业务系统管理

## 基本信息
- 所属系统: 业务保障管理系统
- 所属子系统: 业务管理
- 别名: 系统管理模块

## 功能描述
维护业务系统基础信息、归属关系和状态。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看业务系统列表 | 查看业务系统清单 | 管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 系统台账 | 系统新增 | 新增业务系统 | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 业务系统列表页

## 包 / 类
- BizSystemService

## 依赖模块
- 公共字典模块

## 备注
无
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    content = get_fact_detail("业务系统管理", "description")

    assert "## 功能描述" in content
    assert "维护业务系统基础信息" in content


def test_get_fact_detail_reports_ambiguity_for_duplicate_module_names(tmp_path, monkeypatch):
    facts_root = tmp_path
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)
    for system_name in ("业务保障管理系统", "业务协同管理系统"):
        (modules_dir / f"{system_name}-脆弱性管理.md").write_text(
            f"""# 脆弱性管理

## 基本信息
- 所属系统: {system_name}
- 所属子系统: 安全运营

## 功能描述
{system_name}中的脆弱性管理模块。

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
| 查看脆弱性列表 | 查看数据 | 管理员 |

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
| 默认子模块 | 功能点A | 描述A | 已完成 |

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|

## 页面 / 原型
- 列表页

## 包 / 类
- VulnerabilityService

## 依赖模块
- 公共模块

## 备注
无
""",
            encoding="utf-8",
        )
    monkeypatch.setattr(fact_tools, "_FACTS_ROOT", facts_root)

    content = get_fact_detail("脆弱性管理", "description")

    assert content.startswith("存在多个模块匹配 target_id='脆弱性管理'")
    assert "业务保障管理系统" in content
    assert "业务协同管理系统" in content


def test_summarize_detail_prefers_module_archive_section_title():
    result = """## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|
| 云主机查询接口 | 查询云主机列表和详情 | /api/cloud-hosts | GET |
"""

    summary = _summarize_detail("mod-cloud-host", "apis", result)

    assert summary == "已加载模块档案中的「API 清单」"
