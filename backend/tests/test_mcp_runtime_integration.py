import asyncio
import importlib
import sys
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

from agent.adk.mcp_tools import create_internal_skill_mcp_tools, create_public_mcp_tools
from agent.adk.runner_adapter import ConversationContext
from doc_version_service import DocumentVersionService
from mcp_runtime.docs_namespace import DocsNamespace
from mcp_runtime.facts_namespace import FactsNamespace
from mcp_runtime.prototypes_namespace import PrototypesNamespace
from mcp_runtime.server import MCPRuntimeServer


def _install_fake_google_modules(monkeypatch):
    google = ModuleType("google")
    adk = ModuleType("google.adk")
    agents = ModuleType("google.adk.agents")
    agents_run_config = ModuleType("google.adk.agents.run_config")
    models = ModuleType("google.adk.models")
    lite_llm = ModuleType("google.adk.models.lite_llm")
    tools = ModuleType("google.adk.tools")
    runners = ModuleType("google.adk.runners")
    sessions = ModuleType("google.adk.sessions")
    genai = ModuleType("google.genai")
    genai_types = ModuleType("google.genai.types")

    class FakeLlmAgent:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeLiteLlm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeToolContext:
        pass

    class FakeRunner:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class FakeInMemorySessionService:
        async def create_session(self, *args, **kwargs):
            return None

    class FakeRunConfig:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class FakeStreamingMode:
        SSE = "SSE"

    class Part:
        def __init__(self, text=None):
            self.text = text

    class Content:
        def __init__(self, role=None, parts=None):
            self.role = role
            self.parts = parts or []

    agents.LlmAgent = FakeLlmAgent
    lite_llm.LiteLlm = FakeLiteLlm
    tools.ToolContext = FakeToolContext
    runners.Runner = FakeRunner
    sessions.InMemorySessionService = FakeInMemorySessionService
    agents_run_config.RunConfig = FakeRunConfig
    agents_run_config.StreamingMode = FakeStreamingMode
    genai_types.Content = Content
    genai_types.Part = Part
    genai.types = genai_types

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.adk", adk)
    monkeypatch.setitem(sys.modules, "google.adk.agents", agents)
    monkeypatch.setitem(sys.modules, "google.adk.agents.run_config", agents_run_config)
    monkeypatch.setitem(sys.modules, "google.adk.models", models)
    monkeypatch.setitem(sys.modules, "google.adk.models.lite_llm", lite_llm)
    monkeypatch.setitem(sys.modules, "google.adk.tools", tools)
    monkeypatch.setitem(sys.modules, "google.adk.runners", runners)
    monkeypatch.setitem(sys.modules, "google.adk.sessions", sessions)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", genai_types)


def _load_module_with_fake_google(monkeypatch, module_name: str):
    _install_fake_google_modules(monkeypatch)
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _make_conversation_ctx() -> ConversationContext:
    return ConversationContext(
        conversation_id="conv-mcp-int",
        ws_sender=AsyncMock(),
        conversation_manager=SimpleNamespace(),
    )


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
            """
        ).strip(),
        encoding="utf-8",
    )


def _build_runtime_with_facts_and_docs(tmp_path: Path) -> tuple[MCPRuntimeServer, DocumentVersionService]:
    facts_root = tmp_path / "project-facts"
    modules_dir = facts_root / "modules"
    prototypes_dir = facts_root / "prototypes" / "axure-export"
    modules_dir.mkdir(parents=True)
    prototypes_dir.mkdir(parents=True)
    _write_module_archive(modules_dir / "资产管理.md", "资产管理")
    (prototypes_dir / "index.html").write_text("<html><body>index</body></html>", encoding="utf-8")
    (prototypes_dir / "资产管理页面.html").write_text(
        "<html><head><title>资产管理</title></head><body><button>查询</button></body></html>",
        encoding="utf-8",
    )

    docs_service = DocumentVersionService(
        docs_root=tmp_path / "doc_output",
        legacy_docs_roots=[tmp_path / "legacy_docs"],
    )
    asyncio.run(
        docs_service.save_document(
            "# 资产管理用户手册\n\n正式版本正文",
            doc_type="user-manual",
            doc_name="资产管理用户手册",
            force_date="2026-04-02",
        )
    )

    runtime = MCPRuntimeServer()
    runtime.register_public_tool("facts.list_modules", FactsNamespace(facts_root).list_modules)
    runtime.register_public_tool("facts.get_module", FactsNamespace(facts_root).get_module)
    runtime.register_public_tool("prototypes.list_pages", PrototypesNamespace(facts_root).list_pages)
    runtime.register_public_tool("prototypes.get_page", PrototypesNamespace(facts_root).get_page)
    runtime.register_public_tool("docs.list_saved", DocsNamespace(docs_service).list_saved)
    runtime.register_public_tool("docs.load_saved", DocsNamespace(docs_service).load_saved)
    return runtime, docs_service


def test_runtime_build_fastmcp_registers_public_and_internal_tools(monkeypatch):
    server_module = importlib.import_module("mcp_runtime.server")

    class FakeFastMCP:
        def __init__(self, name, **kwargs):
            self.name = name
            self.kwargs = kwargs
            self.registered = []

        def tool(self, name=None):
            def decorator(handler):
                self.registered.append(name or handler.__name__)
                return handler

            return decorator

    monkeypatch.setattr(server_module, "FastMCP", FakeFastMCP)

    runtime = server_module.MCPRuntimeServer()

    async def public_tool():
        return {}

    async def internal_tool():
        return {}

    runtime.register_public_tool("facts.list_modules", public_tool)
    runtime.register_internal_tool("skill.run_script", internal_tool)

    public_server = runtime.build_fastmcp()
    full_server = runtime.build_fastmcp(include_internal=True)

    assert public_server.name == "doc-assist-mcp"
    assert public_server.kwargs["host"] == "127.0.0.1"
    assert public_server.kwargs["port"] == 8765
    assert public_server.kwargs["streamable_http_path"] == "/mcp"
    assert public_server.registered == ["facts.list_modules"]
    assert set(full_server.registered) == {"facts.list_modules", "skill.run_script"}


def test_mcp_server_main_supports_stdio_and_streamable_http(monkeypatch):
    server_entry = importlib.import_module("mcp_server")
    calls = []
    include_internal_values = []

    class FakeServer:
        def run(self, **kwargs):
            calls.append(kwargs)

    class FakeRuntime:
        def build_fastmcp(self, include_internal=False):
            include_internal_values.append(include_internal)
            return FakeServer()

    monkeypatch.setattr(server_entry, "create_default_runtime_server", lambda settings=None: FakeRuntime())
    monkeypatch.setattr(
        server_entry,
        "get_mcp_server_settings",
        lambda: SimpleNamespace(host="127.0.0.1", port=8765, enable_internal_tools=False),
    )

    monkeypatch.setattr(sys, "argv", ["mcp_server.py", "--transport", "stdio"])
    server_entry.main()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp_server.py",
            "--transport",
            "streamable-http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--include-internal",
        ],
    )
    server_entry.main()

    assert calls[0] == {}
    assert calls[1] == {"transport": "streamable-http"}
    assert include_internal_values == [False, True]


def test_build_document_agent_registers_mcp_public_tools(monkeypatch):
    document_agent = _load_module_with_fake_google(monkeypatch, "agent.adk.document_agent")
    llm_adapter = importlib.import_module("agent.adk.llm_adapter")
    monkeypatch.setattr(
        llm_adapter,
        "get_litellm_model_config",
        lambda: SimpleNamespace(
            model="mock-model",
            api_key="k",
            api_base="http://llm",
            temperature=0.3,
            max_tokens=1024,
            top_p=0.85,
        ),
    )

    ctx = _make_conversation_ctx()
    skill = SimpleNamespace(
        id="user-manual-writter",
        name="用户手册 Skill",
        description="写用户手册",
        type="user-manual",
        skill_md_path="",
        resources=[],
    )

    agent = document_agent.build_document_agent(ctx, [skill], has_draft=False, has_saved=False)
    tool_names = [tool.__name__ for tool in agent.tools]

    assert tool_names == [
        "facts_list_modules",
        "facts_get_module",
        "prototypes_list_pages",
        "prototypes_get_page",
        "docs_list_saved",
        "docs_load_saved",
        "execute_skill",
        "ask_user",
    ]
    assert "facts_list_modules" in agent.instruction
    assert "prototypes_list_pages" in agent.instruction
    assert "docs_load_saved" in agent.instruction
    assert "主 Agent 不负责替子 Agent 决定草稿来源" in agent.instruction
    assert "get_current_draft" not in agent.instruction
    assert "load_saved_document" not in agent.instruction
    assert "get_fact_overview" not in agent.instruction
    assert agent.model.temperature == 0.3
    assert agent.model.max_tokens == 1024
    assert agent.model.top_p == 0.85


def test_build_document_agent_adds_thought_compat_tool_for_ollama(monkeypatch):
    document_agent = _load_module_with_fake_google(monkeypatch, "agent.adk.document_agent")
    llm_adapter = importlib.import_module("agent.adk.llm_adapter")
    monkeypatch.setattr(
        llm_adapter,
        "get_litellm_model_config",
        lambda: SimpleNamespace(
            model="ollama/mock-local",
            api_key="k",
            api_base="http://llm",
            temperature=0.2,
            max_tokens=768,
            top_p=0.9,
        ),
    )

    ctx = _make_conversation_ctx()
    agent = document_agent.build_document_agent(ctx, [], has_draft=False, has_saved=False)
    tool_names = [tool.__name__ for tool in agent.tools]

    assert tool_names[-1] == "thought"
    assert "thought` 不是工具" in agent.instruction


def test_build_skill_subagent_registers_mcp_tools(monkeypatch):
    execute_skill_tool = _load_module_with_fake_google(monkeypatch, "agent.adk.execute_skill_tool")

    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter"
    skill = SimpleNamespace(
        id="user-manual-writter",
        name="用户手册 Skill",
        description="写用户手册",
        type="user-manual",
        skill_md_path=str(skill_dir / "SKILL.md"),
        resources=[],
    )
    ctx = _make_conversation_ctx()
    sub_ctx = execute_skill_tool._build_subagent_context(ctx)

    agent = execute_skill_tool._build_skill_subagent(
        skill,
        sub_ctx,
        SimpleNamespace(
            model="mock-model",
            api_key="k",
            api_base="http://llm",
            temperature=0.4,
            max_tokens=1536,
            top_p=0.88,
        ),
    )
    tool_names = [tool.__name__ for tool in agent.tools]

    assert tool_names == [
        "get_current_draft",
        "docs_list_saved",
        "docs_load_saved",
        "facts_list_modules",
        "facts_get_module",
        "prototypes_list_pages",
        "prototypes_get_page",
        "skill_list_resources",
        "skill_read_resource",
        "skill_run_script",
        "write_document",
        "ask_user",
    ]
    assert "facts_get_module" in agent.instruction
    assert "skill_read_resource" in agent.instruction
    assert "草稿来源判断、历史版本选择、事实加载顺序" in agent.instruction
    assert "get_current_draft" in agent.instruction
    assert "resolve_target_module" not in agent.instruction
    assert "load_saved_document" not in agent.instruction
    assert agent.model.temperature == 0.4
    assert agent.model.max_tokens == 1536
    assert agent.model.top_p == 0.88


def test_build_skill_subagent_adds_thought_compat_tool_for_ollama(monkeypatch):
    execute_skill_tool = _load_module_with_fake_google(monkeypatch, "agent.adk.execute_skill_tool")

    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter"
    skill = SimpleNamespace(
        id="user-manual-writter",
        name="用户手册 Skill",
        description="写用户手册",
        type="user-manual",
        skill_md_path=str(skill_dir / "SKILL.md"),
        resources=[],
    )
    ctx = _make_conversation_ctx()
    sub_ctx = execute_skill_tool._build_subagent_context(ctx)

    agent = execute_skill_tool._build_skill_subagent(
        skill,
        sub_ctx,
        SimpleNamespace(
            model="ollama/mock-local",
            api_key="k",
            api_base="http://llm",
            temperature=0.2,
            max_tokens=1024,
            top_p=0.9,
        ),
    )
    tool_names = [tool.__name__ for tool in agent.tools]

    assert tool_names[-1] == "thought"
    assert "不要调用 `thought`" in agent.instruction


def test_real_skill_resources_and_saved_docs_flow_into_write_document_prompt(tmp_path, monkeypatch):
    write_document_tool = _load_module_with_fake_google(monkeypatch, "agent.adk.write_document_tool")
    llm_adapter = importlib.import_module("agent.adk.llm_adapter")
    monkeypatch.setattr(
        llm_adapter,
        "get_litellm_model_config",
        lambda: SimpleNamespace(
            model="mock-model",
            api_key="k",
            api_base="http://llm",
            temperature=0.1,
            max_tokens=256,
            top_p=0.75,
        ),
    )

    captured_calls = []

    class FakeChunk:
        def __init__(self, text):
            self.choices = [SimpleNamespace(delta=SimpleNamespace(content=text))]
            self.usage = None

    class FakeStream:
        def __init__(self, texts):
            self.texts = texts

        def __aiter__(self):
            self._iter = iter(self.texts)
            return self

        async def __anext__(self):
            try:
                return FakeChunk(next(self._iter))
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    fake_litellm = ModuleType("litellm")

    async def acompletion(**kwargs):
        captured_calls.append(kwargs)
        return FakeStream(["第一段", "第二段"])

    fake_litellm.acompletion = acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    runtime, _docs_service = _build_runtime_with_facts_and_docs(tmp_path)
    ctx = _make_conversation_ctx()
    public_tools = create_public_mcp_tools(ctx, runtime=runtime)
    facts_get_module = public_tools[1]
    docs_load_saved = public_tools[5]

    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter"
    skill = SimpleNamespace(
        id="user-manual-writter",
        name="用户手册 Skill",
        description="写用户手册",
        type="user-manual",
        skill_md_path=str(skill_dir / "SKILL.md"),
        resources=[],
    )
    skill_tools = create_internal_skill_mcp_tools(ctx, skill)
    skill_read_resource = skill_tools[1]

    module_text = asyncio.run(facts_get_module("资产管理"))
    load_summary = asyncio.run(docs_load_saved("user-manual", "资产管理"))
    structure_text = asyncio.run(skill_read_resource("references/structure/module-manual.md"))

    create_write_document_tool = write_document_tool.create_write_document_tool
    write_document = create_write_document_tool(ctx, {skill.id: skill})
    tool_context = SimpleNamespace(state={})

    summary = asyncio.run(
        write_document(
            skill_id=skill.id,
            module_name="资产管理",
            context="",
            user_intent="为资产管理模块编写用户手册",
            tool_context=tool_context,
        )
    )

    prompt = captured_calls[0]["messages"][1]["content"]
    structure_source = (skill_dir / "references" / "structure" / "module-manual.md").read_text(encoding="utf-8")

    assert "## 功能描述" in module_text
    assert "已加载 资产管理" in load_summary
    assert structure_text.startswith("[reference] references/structure/module-manual.md")
    assert "正式版本正文" in prompt
    assert "## 功能描述" in prompt
    assert structure_source[:80].strip() in prompt
    assert captured_calls[0]["top_p"] == 0.75
    assert tool_context.state["draft_content"] == "第一段第二段"
    assert summary.startswith("文档已生成，共")


def test_write_document_prefers_unsaved_draft_over_loaded_saved_doc(tmp_path, monkeypatch):
    write_document_tool = _load_module_with_fake_google(monkeypatch, "agent.adk.write_document_tool")
    llm_adapter = importlib.import_module("agent.adk.llm_adapter")
    monkeypatch.setattr(
        llm_adapter,
        "get_litellm_model_config",
        lambda: SimpleNamespace(
            model="mock-model",
            api_key="k",
            api_base="http://llm",
            temperature=0.1,
            max_tokens=256,
            top_p=0.7,
        ),
    )

    captured_calls = []
    fake_litellm = ModuleType("litellm")

    class FakeChunk:
        def __init__(self, text):
            self.choices = [SimpleNamespace(delta=SimpleNamespace(content=text))]
            self.usage = None

    class FakeStream:
        def __aiter__(self):
            self.done = False
            return self

        async def __anext__(self):
            if self.done:
                raise StopAsyncIteration
            self.done = True
            return FakeChunk("正文")

    async def acompletion(**kwargs):
        captured_calls.append(kwargs)
        return FakeStream()

    fake_litellm.acompletion = acompletion
    monkeypatch.setitem(sys.modules, "litellm", fake_litellm)

    ctx = _make_conversation_ctx()
    ctx.loaded_base_draft = "这是已保存正式版本"
    skill_dir = Path(__file__).resolve().parents[2] / "skills" / "user-manual-writter"
    skill = SimpleNamespace(
        id="user-manual-writter",
        name="用户手册 Skill",
        description="写用户手册",
        type="user-manual",
        skill_md_path=str(skill_dir / "SKILL.md"),
        resources=[],
    )

    write_document = write_document_tool.create_write_document_tool(ctx, {skill.id: skill})
    tool_context = SimpleNamespace(state={})

    asyncio.run(
        write_document(
            skill_id=skill.id,
            module_name="资产管理",
            context="这是当前未保存草稿",
            user_intent="继续修改资产管理模块用户手册",
            tool_context=tool_context,
        )
    )

    prompt = captured_calls[0]["messages"][1]["content"]
    assert "这是当前未保存草稿" in prompt
    assert "这是已保存正式版本" not in prompt
