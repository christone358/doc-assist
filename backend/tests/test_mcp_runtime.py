import asyncio
import textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agent.adk.execute_skill_tool import _build_subagent_context
from agent.adk.mcp_tools import create_internal_skill_mcp_tools, create_public_mcp_tools
from agent.adk.tool_catalog import (
    build_main_agent_tool_view,
    build_mcp_tool_catalog,
    build_skill_subagent_tool_view,
    render_tool_section,
)
from agent.adk.runner_adapter import ConversationContext
from doc_version_service import DocumentVersionService
from mcp_runtime.artifacts_namespace import ArtifactsNamespace
from mcp_runtime.docs_namespace import DocsNamespace
from mcp_runtime.errors import MCPRuntimeError
from mcp_runtime.facts_namespace import FactsNamespace
from mcp_runtime.prototypes_namespace import PrototypesNamespace
from mcp_runtime.server import MCPRuntimeServer


def _write_module_archive(path: Path, name: str) -> None:
    path.write_text(
        textwrap.dedent(
            f"""
            # {name}

            ## 基本信息
            - 所属系统: 业务保障管理系统
            - 所属子系统: 业务协同
            - 别名: {name}别名

            ## 功能描述
            面向终端用户，提供{name}能力。

            ## 用例信息
            | 用例 | 描述 | 参与角色 |
            |---|---|---|
            | 查看{name} | 查看{name}信息 | 用户 |

            ## 功能点
            | 子模块 | 功能点 | 描述 | 状态 |
            |---|---|---|---|
            | 核心能力 | 查看{name}列表 | 展示列表 | 已完成 |

            ## API 清单
            | API 名称 | 说明 | 路径 | 方法 |
            |---|---|---|---|
            | 查询{name} | 查询{name} | /api/{name} | GET |

            ## 页面 / 原型
            - {name}页面

            ## 包 / 类
            - {name}Service

            ## 依赖模块
            - 无

            ## 备注
            测试数据
            """
        ).strip(),
        encoding="utf-8",
    )


@pytest.fixture
def facts_root(tmp_path):
    root = tmp_path / "project-facts"
    modules_dir = root / "modules"
    prototype_dir = root / "prototypes" / "axure-export"
    modules_dir.mkdir(parents=True)
    prototype_dir.mkdir(parents=True)
    _write_module_archive(modules_dir / "资产管理.md", "资产管理")
    _write_module_archive(modules_dir / "日志管理.md", "日志管理")
    (prototype_dir / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")
    (prototype_dir / "资产管理页面.html").write_text(
        "<html><head><title>资产管理</title></head><body><button>查询</button><a href='详情页.html'>详情</a></body></html>",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def docs_service(tmp_path):
    service = DocumentVersionService(
        docs_root=tmp_path / "doc_output",
        legacy_docs_roots=[tmp_path / "legacy_docs"],
    )
    asyncio.run(
        service.save_document(
            "# 资产管理用户手册\n\n正文",
            doc_type="user-manual",
            doc_name="资产管理用户手册",
            force_date="2026-04-02",
        )
    )
    return service


@pytest.fixture
def conversation_ctx():
    return ConversationContext(
        conversation_id="conv-mcp",
        ws_sender=AsyncMock(),
        conversation_manager=SimpleNamespace(),
    )


def test_facts_namespace_list_and_get_module(facts_root):
    namespace = FactsNamespace(facts_root=facts_root)

    listing = asyncio.run(namespace.list_modules())
    module_result = asyncio.run(namespace.get_module("资产管理"))

    assert listing["count"] == 2
    assert any(item["name"] == "资产管理" for item in listing["modules"])
    assert module_result["module"]["name"] == "资产管理"
    assert "## 功能描述" in module_result["content"]


def test_facts_namespace_returns_structured_errors(facts_root, tmp_path):
    namespace = FactsNamespace(facts_root=facts_root)

    with pytest.raises(MCPRuntimeError) as missing_exc:
        asyncio.run(namespace.get_module("不存在的模块"))
    assert missing_exc.value.error_type == "module_not_found"

    ambiguous_root = tmp_path / "ambiguous-project-facts"
    modules_dir = ambiguous_root / "modules"
    modules_dir.mkdir(parents=True)
    (modules_dir / "模块A.md").write_text(
        textwrap.dedent(
            """
            # 模块A

            ## 基本信息
            - 所属系统: 系统A
            - 所属子系统: 子系统A
            - 别名: 公共模块
            """
        ).strip(),
        encoding="utf-8",
    )
    (modules_dir / "模块B.md").write_text(
        textwrap.dedent(
            """
            # 模块B

            ## 基本信息
            - 所属系统: 系统B
            - 所属子系统: 子系统B
            - 别名: 公共模块
            """
        ).strip(),
        encoding="utf-8",
    )
    ambiguous_namespace = FactsNamespace(facts_root=ambiguous_root)
    with pytest.raises(MCPRuntimeError) as ambiguous_exc:
        asyncio.run(ambiguous_namespace.get_module("公共模块"))
    assert ambiguous_exc.value.error_type == "ambiguous_module_ref"
    assert ambiguous_exc.value.details["candidates"]


def test_docs_namespace_list_and_load_saved(docs_service):
    namespace = DocsNamespace(service=docs_service)

    listing = asyncio.run(namespace.list_saved("user-manual"))
    loaded = asyncio.run(namespace.load_saved("user-manual", "资产管理"))

    assert listing["count"] == 1
    assert listing["documents"][0]["doc_name"] == "资产管理"
    assert loaded["doc_name"] == "资产管理"
    assert loaded["content"].startswith("# 资产管理用户手册")


def test_docs_namespace_returns_not_found_errors(docs_service):
    namespace = DocsNamespace(service=docs_service)

    with pytest.raises(MCPRuntimeError) as missing_exc:
        asyncio.run(namespace.load_saved("user-manual", "不存在"))
    assert missing_exc.value.error_type == "document_not_found"

    with pytest.raises(MCPRuntimeError) as missing_version_exc:
        asyncio.run(namespace.load_saved("user-manual", "资产管理", version="9.9.9"))
    assert missing_version_exc.value.error_type == "document_version_not_found"


def test_artifacts_namespace_read_and_write_file(tmp_path):
    namespace = ArtifactsNamespace(root=tmp_path)

    write_result = asyncio.run(
        namespace.write_file("runtime-output/result.md", "# 标题\n\n这是运行时产物。")
    )
    read_result = asyncio.run(
        namespace.read_file("runtime-output/result.md")
    )

    assert write_result["created"] is True
    assert write_result["file"]["path"] == "runtime-output/result.md"
    assert read_result["file"]["is_text"] is True
    assert "这是运行时产物" in read_result["content"]


def test_artifacts_namespace_rejects_out_of_scope_paths(tmp_path):
    namespace = ArtifactsNamespace(root=tmp_path)

    with pytest.raises(MCPRuntimeError) as exc:
        asyncio.run(namespace.read_file("../secret.txt"))
    assert exc.value.error_type == "path_out_of_scope"


def test_prototypes_namespace_list_and_get_page(facts_root):
    namespace = PrototypesNamespace(facts_root=facts_root)

    listing = asyncio.run(namespace.list_pages("资产管理"))
    page = asyncio.run(namespace.get_page("资产管理页面"))

    assert listing["count"] == 1
    assert listing["pages"][0]["page_name"] == "资产管理页面"
    assert "资产管理" in listing["llm_summary"]
    assert page["page"]["page_name"] == "资产管理页面"
    assert page["fact"]["elements"]["buttons"] == ["查询"]
    assert "详情" in page["llm_summary"]


def test_public_mcp_tools_update_layered_context(facts_root, docs_service, conversation_ctx):
    runtime = MCPRuntimeServer()
    runtime.register_public_tool("facts.list_modules", FactsNamespace(facts_root).list_modules)
    runtime.register_public_tool("facts.get_module", FactsNamespace(facts_root).get_module)
    runtime.register_public_tool("prototypes.list_pages", PrototypesNamespace(facts_root).list_pages)
    runtime.register_public_tool("prototypes.get_page", PrototypesNamespace(facts_root).get_page)
    runtime.register_public_tool("docs.list_saved", DocsNamespace(docs_service).list_saved)
    runtime.register_public_tool("docs.load_saved", DocsNamespace(docs_service).load_saved)
    runtime.register_public_tool("artifacts.read_file", ArtifactsNamespace(facts_root).read_file)
    runtime.register_public_tool("artifacts.write_file", ArtifactsNamespace(facts_root).write_file)

    (
        facts_list_modules,
        facts_get_module,
        prototypes_list_pages,
        prototypes_get_page,
        docs_list_saved,
        docs_load_saved,
        artifacts_read_file,
        artifacts_write_file,
    ) = create_public_mcp_tools(
        conversation_ctx,
        runtime=runtime,
    )

    modules_text = asyncio.run(facts_list_modules())
    module_text = asyncio.run(facts_get_module("资产管理"))
    pages_text = asyncio.run(prototypes_list_pages("资产管理"))
    page_text = asyncio.run(prototypes_get_page("资产管理页面"))
    docs_text = asyncio.run(docs_list_saved("user-manual"))
    load_summary = asyncio.run(docs_load_saved("user-manual", "资产管理"))
    write_summary = asyncio.run(
        artifacts_write_file("artifacts/result.txt", "runtime result")
    )
    artifact_text = asyncio.run(
        artifacts_read_file("artifacts/result.txt")
    )

    assert facts_list_modules.__name__ == "facts_list_modules"
    assert facts_get_module.__name__ == "facts_get_module"
    assert prototypes_list_pages.__name__ == "prototypes_list_pages"
    assert prototypes_get_page.__name__ == "prototypes_get_page"
    assert artifacts_read_file.__name__ == "artifacts_read_file"
    assert artifacts_write_file.__name__ == "artifacts_write_file"
    assert getattr(facts_list_modules, "logical_name") == "facts.list_modules"
    assert getattr(facts_get_module, "logical_name") == "facts.get_module"
    assert getattr(prototypes_list_pages, "logical_name") == "prototypes.list_pages"
    assert getattr(prototypes_get_page, "logical_name") == "prototypes.get_page"
    assert getattr(artifacts_read_file, "logical_name") == "artifacts.read_file"
    assert getattr(artifacts_write_file, "logical_name") == "artifacts.write_file"
    assert "资产管理" in modules_text
    assert "## 功能描述" in module_text
    assert "资产管理页面" in pages_text
    assert "elements" in page_text
    assert "历史已保存文档清单" in docs_text
    assert "已加载 资产管理" in load_summary
    assert "已创建本地文件" in write_summary
    assert "runtime result" in artifact_text
    assert conversation_ctx.loaded_facts_parts
    assert conversation_ctx.loaded_docs_parts
    assert conversation_ctx.loaded_base_draft


def test_public_mcp_tool_wrappers_preserve_parameter_annotations(facts_root, conversation_ctx):
    runtime = MCPRuntimeServer()
    runtime.register_public_tool("facts.get_module", FactsNamespace(facts_root).get_module)
    runtime.register_public_tool("prototypes.list_pages", PrototypesNamespace(facts_root).list_pages)

    facts_get_module, prototypes_list_pages = create_public_mcp_tools(
        conversation_ctx,
        runtime=runtime,
    )

    assert facts_get_module.__annotations__["module_ref"] == "str"
    assert facts_get_module.__annotations__["return"] is str
    assert prototypes_list_pages.__annotations__["module_ref"] == "str"
    assert prototypes_list_pages.__annotations__["return"] is str


def test_build_subagent_context_keeps_only_minimal_handoff(conversation_ctx):
    conversation_ctx.loaded_facts_parts.append("facts")
    conversation_ctx.loaded_skill_resource_parts.append("skill")
    conversation_ctx.loaded_docs_parts.append("docs")
    conversation_ctx.loaded_base_draft = "draft"
    conversation_ctx.loaded_base_doc_name = "资产管理用户手册"
    conversation_ctx.loaded_base_module_id = "mod-assets"
    conversation_ctx.current_module_id = "mod-assets"
    conversation_ctx.current_module_name = "资产管理"
    conversation_ctx.current_system_name = "业务保障管理系统"
    conversation_ctx.current_subsystem_name = "业务协同"
    conversation_ctx.last_skill_execution_summary = "上轮摘要"
    conversation_ctx.conversation_has_draft = True
    conversation_ctx.clarification_context.append("Q: 文档类型？\nA: 用户手册")

    sub_ctx = _build_subagent_context(conversation_ctx)

    assert sub_ctx is not conversation_ctx
    assert sub_ctx.loaded_facts_parts == []
    assert sub_ctx.loaded_skill_resource_parts == []
    assert sub_ctx.loaded_docs_parts == []
    assert sub_ctx.loaded_base_draft is None
    assert sub_ctx.loaded_base_doc_name == "资产管理用户手册"
    assert sub_ctx.loaded_base_module_id == "mod-assets"
    assert sub_ctx.current_module_name == "资产管理"
    assert sub_ctx.last_skill_execution_summary == "上轮摘要"
    assert sub_ctx.conversation_has_draft is True
    assert sub_ctx.user_input_queue is conversation_ctx.user_input_queue
    assert sub_ctx.execution_events is conversation_ctx.execution_events
    assert sub_ctx.clarification_context is conversation_ctx.clarification_context


def test_tool_catalog_builds_role_specific_views(conversation_ctx):
    skill_md_path = (
        Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter" / "SKILL.md"
    )
    skill = SimpleNamespace(
        id="write-user-manual",
        name="用户手册写作",
        description="测试 skill",
        type="user-manual",
        skill_md_path=str(skill_md_path),
        resources=[],
    )
    skills_map = {skill.id: skill}

    catalog = build_mcp_tool_catalog(conversation_ctx, skill=skill)
    main_view = build_main_agent_tool_view(conversation_ctx, skills_map)
    sub_view = build_skill_subagent_tool_view(conversation_ctx, skill, skills_map)

    assert "facts.list_modules" in catalog
    assert "docs.load_saved" in catalog
    assert "artifacts.read_file" in catalog
    assert "skill.read_resource" in catalog
    assert catalog["skill.read_resource"].visibility == "internal"
    assert "artifacts.read_file" in main_view.tool_ids
    assert "execute_skill" in main_view.tool_ids
    assert "ask_user" in main_view.tool_ids
    assert "artifacts.write_file" in sub_view.tool_ids
    assert "write_document" in sub_view.tool_ids
    assert "get_current_draft" in sub_view.tool_ids


def test_dynamic_public_tool_auto_enters_catalog_and_tool_view(conversation_ctx):
    runtime = MCPRuntimeServer()

    async def facts_list_modules():
        return {"modules": [], "count": 0, "overview_markdown": ""}

    async def facts_search_modules(keyword: str = ""):
        return {"keyword": keyword, "matches": []}

    async def skill_run_script(relative_path: str):
        return {"path": relative_path}

    runtime.register_public_tool("facts.list_modules", facts_list_modules)
    runtime.register_public_tool("facts.search_modules", facts_search_modules)
    runtime.register_internal_tool("skill.run_script", skill_run_script)

    catalog = build_mcp_tool_catalog(conversation_ctx, runtime=runtime)
    main_view = build_main_agent_tool_view(conversation_ctx, {}, runtime=runtime)

    assert "facts.search_modules" in catalog
    assert catalog["facts.search_modules"].schema_metadata["params"] == ["keyword?"]
    assert "facts.search_modules" in main_view.tool_ids
    assert "skill.run_script" not in main_view.tool_ids


def test_render_tool_section_matches_visible_tool_view(conversation_ctx):
    skill_md_path = (
        Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter" / "SKILL.md"
    )
    skill = SimpleNamespace(
        id="write-user-manual",
        name="用户手册写作",
        description="测试 skill",
        type="user-manual",
        skill_md_path=str(skill_md_path),
        resources=[],
    )
    skills_map = {skill.id: skill}

    main_view = build_main_agent_tool_view(conversation_ctx, skills_map)
    sub_view = build_skill_subagent_tool_view(conversation_ctx, skill, skills_map)

    main_section = render_tool_section(main_view, "## 可用工具")
    sub_section = render_tool_section(sub_view, "### 可用通用工具")

    for tool_id in main_view.tool_ids:
        assert main_view.catalog[tool_id].runtime_name in main_section
    for tool_id in sub_view.tool_ids:
        assert sub_view.catalog[tool_id].runtime_name in sub_section
    assert "load_saved_document" not in main_section
    assert "get_fact_overview" not in sub_section


def test_skill_namespace_tools_are_internal_and_bound_to_skill_root(tmp_path, conversation_ctx):
    skill_dir = tmp_path / "demo-skill"
    (skill_dir / "references").mkdir(parents=True)
    (skill_dir / "scripts").mkdir(parents=True)
    skill_md = skill_dir / "skill.md"
    skill_md.write_text(
        textwrap.dedent(
            """
            ---
            name: demo-skill
            description: 测试 skill
            type: general
            ---
            """
        ).strip(),
        encoding="utf-8",
    )
    (skill_dir / "references" / "guide.md").write_text("# guide", encoding="utf-8")
    (skill_dir / "scripts" / "main.py").write_text(
        textwrap.dedent(
            """
            async def handle_request(context):
                return {"echo": context.get("name", "unknown")}
            """
        ).strip(),
        encoding="utf-8",
    )

    skill = SimpleNamespace(
        id="demo-skill",
        name="demo-skill",
        description="测试 skill",
        type="general",
        skill_md_path=str(skill_md),
        resources=[],
    )
    skill_list_resources, skill_read_resource, skill_run_script = create_internal_skill_mcp_tools(
        conversation_ctx,
        skill,
    )

    resources_text = asyncio.run(skill_list_resources())
    resource_text = asyncio.run(skill_read_resource("references/guide.md"))
    script_text = asyncio.run(skill_run_script("scripts/main.py", {"name": "doc-assist"}))

    assert skill_list_resources.__name__ == "skill_list_resources"
    assert skill_read_resource.__name__ == "skill_read_resource"
    assert skill_run_script.__name__ == "skill_run_script"
    assert "references/guide.md" in resources_text
    assert "# guide" in resource_text
    assert "doc-assist" in script_text
    assert conversation_ctx.loaded_skill_resource_parts


def test_skill_namespace_rejects_out_of_scope_and_missing_resources(tmp_path, conversation_ctx):
    skill_dir = tmp_path / "demo-skill"
    (skill_dir / "references").mkdir(parents=True)
    skill_md = skill_dir / "skill.md"
    skill_md.write_text(
        textwrap.dedent(
            """
            ---
            name: demo-skill
            description: 测试 skill
            type: general
            ---
            """
        ).strip(),
        encoding="utf-8",
    )
    (skill_dir / "references" / "guide.md").write_text("# guide", encoding="utf-8")
    skill = SimpleNamespace(
        id="demo-skill",
        name="demo-skill",
        description="测试 skill",
        type="general",
        skill_md_path=str(skill_md),
        resources=[],
    )
    _, skill_read_resource, skill_run_script = create_internal_skill_mcp_tools(
        conversation_ctx,
        skill,
    )

    missing_message = asyncio.run(skill_read_resource("references/missing.md"))
    outside_message = asyncio.run(skill_read_resource("../secret.txt"))
    wrong_script_type = asyncio.run(skill_run_script("references/guide.md"))

    assert "未找到 Skill 资源" in missing_message
    assert "禁止访问 Skill 根目录之外的路径" in outside_message
    assert "未找到 Skill 资源" in wrong_script_type or "仅支持执行 Python 脚本" in wrong_script_type


def test_skill_namespace_reports_script_timeout(tmp_path, conversation_ctx, monkeypatch):
    skill_dir = tmp_path / "demo-skill"
    (skill_dir / "scripts").mkdir(parents=True)
    skill_md = skill_dir / "skill.md"
    skill_md.write_text(
        textwrap.dedent(
            """
            ---
            name: demo-skill
            description: 测试 skill
            type: general
            ---
            """
        ).strip(),
        encoding="utf-8",
    )
    (skill_dir / "scripts" / "slow.py").write_text(
        textwrap.dedent(
            """
            import asyncio

            async def handle_request(context):
                await asyncio.sleep(1)
                return "done"
            """
        ).strip(),
        encoding="utf-8",
    )
    skill = SimpleNamespace(
        id="demo-skill",
        name="demo-skill",
        description="测试 skill",
        type="general",
        skill_md_path=str(skill_md),
        resources=[],
    )
    monkeypatch.setattr("mcp_runtime.skill_namespace.SkillNamespace.SCRIPT_TIMEOUT_SECONDS", 0.01)
    _, _, skill_run_script = create_internal_skill_mcp_tools(conversation_ctx, skill)

    timeout_message = asyncio.run(skill_run_script("scripts/slow.py"))

    assert "执行超时" in timeout_message
