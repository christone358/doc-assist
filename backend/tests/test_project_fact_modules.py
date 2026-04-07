import json

from agent.context_loader import load_context, resolve_module_id
from project_fact_modules import ModuleArchiveRepository, ensure_generated_views


MODULE_TEMPLATE = """# {title}

## 基本信息
- 所属系统: 测试系统
- 所属子系统: {subsystem}
- 模块状态: 进行中
{aliases}

## 功能描述
{description}

## 用例信息
| 用例 | 描述 | 参与角色 |
|---|---|---|
{usecase_rows}

## 功能点
| 子模块 | 功能点 | 描述 | 状态 |
|---|---|---|---|
{function_rows}

## API 清单
| API 名称 | 说明 | 路径 | 方法 |
|---|---|---|---|
{api_rows}

## 页面 / 原型
{prototype_rows}

## 包 / 类
{class_rows}

## 依赖模块
{dependency_rows}

## 备注
{remarks}
"""


def _write_module(
    path,
    title,
    *,
    aliases="",
    subsystem="",
    description="模块描述",
    usecase_rows="| 查看资产列表 | 查看资产列表数据 | 资产管理员 |",
    function_rows="| 默认子模块 | 功能列表 | 展示功能列表 | 已完成 |",
    api_rows="| 查询接口 | 查询数据 | /api/items | GET |",
    prototype_rows="- 列表页",
    class_rows="- ItemService",
    dependency_rows="- 公共模块",
    remarks="待补充",
):
    alias_line = f"- 别名: {aliases}" if aliases else ""
    path.write_text(
        MODULE_TEMPLATE.format(
            title=title,
            subsystem=subsystem,
            aliases=alias_line,
            description=description,
            usecase_rows=usecase_rows,
            function_rows=function_rows,
            api_rows=api_rows,
            prototype_rows=prototype_rows,
            class_rows=class_rows,
            dependency_rows=dependency_rows,
            remarks=remarks,
        ),
        encoding="utf-8",
    )


def test_ensure_generated_views_creates_indexes_and_matches_prototype_pages(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    prototype_dir = facts_root / "prototypes" / "axure-export"
    modules_dir.mkdir(parents=True)
    prototype_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "云主机资产管理.md",
        "云主机资产管理",
        aliases="云主机管理",
        prototype_rows="- 云主机列表页\n- 云主机详情页",
    )
    (prototype_dir / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")
    (prototype_dir / "云主机列表页.html").write_text("<html><body>list</body></html>", encoding="utf-8")
    (prototype_dir / "云主机详情页.html").write_text("<html><body>detail</body></html>", encoding="utf-8")

    generated = ensure_generated_views(facts_root)

    pages = generated["page_index"]["pages"]
    assert any(page["name"] == "云主机列表页" and page["path"] == "axure-export/云主机列表页.html" for page in pages)
    assert any(page["name"] == "云主机详情页" and page["path"] == "axure-export/云主机详情页.html" for page in pages)

    repo = ModuleArchiveRepository(facts_root)
    module = repo.get_module(repo.archives[0].module_id)
    assert module is not None
    assert module["prototype_pages"] == [
        {"name": "云主机列表页", "path": "axure-export/云主机列表页.html"},
        {"name": "云主机详情页", "path": "axure-export/云主机详情页.html"},
    ]

    module_index = json.loads((facts_root / "generated" / "module-index.json").read_text(encoding="utf-8"))
    assert module_index["modules"][0]["name"] == "云主机资产管理"
    assert module_index["modules"][0]["subsystem"] == ""


def test_module_identity_registry_keeps_same_id_after_rename_with_alias(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    original_path = modules_dir / "云主机资产管理.md"
    _write_module(original_path, "云主机资产管理")
    first = ensure_generated_views(facts_root)
    first_id = first["module_index"]["modules"][0]["id"]

    renamed_path = modules_dir / "云资源资产管理.md"
    original_path.rename(renamed_path)
    _write_module(renamed_path, "云资源资产管理", aliases="云主机资产管理")

    second = ensure_generated_views(facts_root)
    second_id = second["module_index"]["modules"][0]["id"]

    assert first_id == second_id

    identity_map = json.loads((facts_root / "generated" / "module-id-map.json").read_text(encoding="utf-8"))
    assert identity_map["modules"][0]["name"] == "云资源资产管理"
    assert "云主机资产管理" in identity_map["modules"][0]["aliases"]


def test_context_loader_and_module_resolution_use_generated_module_archives(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "云主机资产管理.md",
        "云主机资产管理",
        aliases="云主机管理",
        api_rows="| 云主机查询接口 | 查询云主机列表和详情 | /api/cloud-hosts | GET |",
        prototype_rows="- 云主机列表页",
        class_rows="- CloudHostService",
    )

    modules_view = load_context("modules", None, facts_root)[0]
    assert "## 云主机资产管理" in modules_view

    module_id, module_map = resolve_module_id("请补充云主机管理的接口说明", modules_view)
    assert module_id is not None
    assert module_map["云主机资产管理"] == module_id
    assert module_map["云主机管理"] == module_id

    interfaces = load_context("interfaces", module_id, facts_root)
    usecases = load_context("usecases", module_id, facts_root)
    prototypes = load_context("prototypes", module_id, facts_root)
    classes = load_context("classes", module_id, facts_root)
    function_points = load_context("function_points", module_id, facts_root)
    module_detail = load_context("module", module_id, facts_root)

    assert "云主机查询接口" in interfaces[0]
    assert "查看资产列表" in usecases[0]
    assert "云主机列表页" in prototypes[0]
    assert "CloudHostService" in classes[0]
    assert "查看资产列表" in module_detail[0]
    assert "## 功能点" in function_points[0]
    assert "# 云主机资产管理" in module_detail[0]


def test_repository_resolves_module_reference_by_name_alias_and_embedded_id(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "业务系统管理.md",
        "业务系统管理",
        aliases="系统管理模块",
    )

    repo = ModuleArchiveRepository(facts_root)
    module_id = repo.archives[0].module_id

    resolved_by_name, candidates_by_name = repo.resolve_module_reference("业务系统管理")
    resolved_by_alias, candidates_by_alias = repo.resolve_module_reference("系统管理模块")
    resolved_by_suffix, candidates_by_suffix = repo.resolve_module_reference("业务系统管理模块")
    resolved_by_embedded_id, candidates_by_embedded_id = repo.resolve_module_reference(
        f"业务系统管理({module_id})"
    )

    assert resolved_by_name == module_id
    assert candidates_by_name == []
    assert resolved_by_alias == module_id
    assert candidates_by_alias == []
    assert resolved_by_suffix == module_id
    assert candidates_by_suffix == []
    assert resolved_by_embedded_id == module_id
    assert candidates_by_embedded_id == []


def test_repository_resolve_module_reference_reports_ambiguity(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "系统A-脆弱性管理.md",
        "脆弱性管理",
        subsystem="系统A子系统",
        description="系统A的脆弱性管理模块",
    )
    _write_module(
        modules_dir / "系统B-脆弱性管理.md",
        "脆弱性管理",
        subsystem="系统B子系统",
        description="系统B的脆弱性管理模块",
    )

    repo = ModuleArchiveRepository(facts_root)
    resolved, candidates = repo.resolve_module_reference("脆弱性管理")

    assert resolved is None
    assert len(candidates) == 2
    assert {item["subsystem"] for item in candidates} == {"系统A子系统", "系统B子系统"}


def test_repository_resolve_module_reference_supports_scoped_reference(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "系统A-脆弱性管理.md",
        "脆弱性管理",
        subsystem="资产脆弱性管理",
        description="系统A中的脆弱性管理模块",
    )
    _write_module(
        modules_dir / "系统B-脆弱性管理.md",
        "脆弱性管理",
        subsystem="业务运行保障",
        description="系统B中的脆弱性管理模块",
    )

    repo = ModuleArchiveRepository(facts_root)
    resolved, candidates = repo.resolve_module_reference("测试系统/资产脆弱性管理/脆弱性管理模块")

    assert resolved is not None
    assert candidates == []
    module = repo.get_module(resolved)
    assert module is not None
    assert module["subsystem"] == "资产脆弱性管理"


def test_context_loader_supports_system_and_subsystem_overviews(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(modules_dir / "模块A.md", "模块A", subsystem="资产管理子系统")
    _write_module(modules_dir / "模块B.md", "模块B", subsystem="运维子系统")

    systems = load_context("systems", None, facts_root)
    subsystems = load_context("subsystems", None, facts_root)

    assert "## 测试系统" in systems[0]
    assert "### 资产管理子系统" in subsystems[0]
    assert "### 运维子系统" in subsystems[0]


def test_repository_supports_subsystem_parse_and_filter(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(modules_dir / "模块A.md", "模块A", subsystem="资产管理子系统")
    _write_module(modules_dir / "模块B.md", "模块B", subsystem="运维子系统")

    repo = ModuleArchiveRepository(facts_root)

    asset_items = repo.list_modules(subsystem="资产管理子系统")
    assert len(asset_items) == 1
    assert asset_items[0]["name"] == "模块A"
    assert asset_items[0]["subsystem"] == "资产管理子系统"

    module_detail = repo.get_module(asset_items[0]["id"])
    assert module_detail is not None
    assert module_detail["subsystem"] == "资产管理子系统"


def test_repository_extracts_submodules_and_groups_function_points(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "模块A.md",
        "模块A",
        function_rows=(
            "| 子模块一 | 功能点A | 描述A | 已完成 |\n"
            "| 子模块一 | 功能点B | 描述B | 进行中 |\n"
            "| 子模块二 | 功能点C | 描述C | 待补充 |"
        ),
    )

    repo = ModuleArchiveRepository(facts_root)
    item = repo.list_modules()[0]
    assert item["counts"]["submodules"] == 2
    assert item["submodules"] == ["子模块一", "子模块二"]

    detail = repo.get_module(item["id"])
    assert detail is not None
    assert detail["submodules"] == ["子模块一", "子模块二"]
    assert detail["function_points"][0]["子模块"] == "子模块一"


def test_repository_parses_usecases_and_counts_them(tmp_path):
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    modules_dir.mkdir(parents=True)

    _write_module(
        modules_dir / "模块A.md",
        "模块A",
        usecase_rows=(
            "| 查看资产列表 | 查看资产列表数据 | 资产管理员 |\n"
            "| 导出资产清单 | 导出筛选后的资产清单 | 资产管理员 |"
        ),
    )

    repo = ModuleArchiveRepository(facts_root)
    item = repo.list_modules()[0]
    assert item["counts"]["usecases"] == 2
    assert item["usecases"] == ["查看资产列表", "导出资产清单"]

    detail = repo.get_module(item["id"])
    assert detail is not None
    assert detail["usecases"][0]["用例"] == "查看资产列表"
    assert detail["usecases"][0]["参与角色"] == "资产管理员"
