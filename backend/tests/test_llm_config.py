"""
单元测试 - LLM 配置管理
"""
import asyncio
import pytest
import json
import uuid
from pathlib import Path
from llm.service import (
    LLMConfigManager, LLMConfig, LLMProvider,
    _encrypt_key, _decrypt_key,
    _normalize_api_base, _build_json_headers, _merge_openai_compatible_payload, LLMService,
    normalize_reasoning_mode, build_reasoning_request_kwargs,
)
from agent.adk.llm_adapter import (
    LiteLLMModelConfig,
    _normalize_litellm_api_base,
    _resolve_litellm_api_key,
    build_adk_litellm_model,
)
from agent.adk.thought_tool import should_enable_thought_tool


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "llm_configs.json"


@pytest.fixture
def mgr(config_path):
    return LLMConfigManager(config_file=config_path)


def make_config(**kwargs) -> LLMConfig:
    defaults = dict(
        id=str(uuid.uuid4())[:8],
        name="测试配置",
        provider=LLMProvider.DEEPSEEK,
        model_name="deepseek-chat",
        api_base="https://api.deepseek.com/v1",
        api_key_encrypted=_encrypt_key("test-key"),
    )
    defaults.update(kwargs)
    return LLMConfig(**defaults)


# --- 加解密 ---

def test_encrypt_decrypt_roundtrip():
    plain = "my-secret-api-key-xyz"
    encrypted = _encrypt_key(plain)
    assert encrypted != plain
    assert _decrypt_key(encrypted) == plain


# --- CRUD ---

def test_add_and_get(mgr):
    cfg = make_config(name="DeepSeek测试")
    mgr.add(cfg)
    loaded = mgr.get(cfg.id)
    assert loaded is not None
    assert loaded.name == "DeepSeek测试"


def test_list_all(mgr):
    mgr.add(make_config())
    mgr.add(make_config())
    assert len(mgr.list_all()) == 2


def test_update(mgr):
    cfg = make_config(name="旧名称")
    mgr.add(cfg)
    cfg.name = "新名称"
    result = mgr.update(cfg)
    assert result is True
    assert mgr.get(cfg.id).name == "新名称"


def test_update_nonexistent(mgr):
    cfg = make_config()
    result = mgr.update(cfg)
    assert result is False


def test_delete(mgr):
    cfg = make_config()
    mgr.add(cfg)
    result = mgr.delete(cfg.id)
    assert result is True
    assert mgr.get(cfg.id) is None


def test_delete_nonexistent(mgr):
    result = mgr.delete("nonexistent-id")
    assert result is False


# --- 默认配置 ---

def test_set_and_get_default(mgr):
    cfg = make_config()
    mgr.add(cfg)
    mgr.set_default(cfg.id)
    default = mgr.get_default()
    assert default is not None
    assert default.id == cfg.id


def test_default_fallback_to_first_active(mgr):
    cfg = make_config(is_default=False)
    mgr.add(cfg)
    default = mgr.get_default()
    assert default is not None
    assert default.id == cfg.id


def test_get_default_none_when_empty(mgr):
    assert mgr.get_default() is None


# --- 持久化 ---

def test_persistence(config_path):
    mgr1 = LLMConfigManager(config_file=config_path)
    cfg = make_config(name="持久化测试")
    mgr1.add(cfg)
    mgr1.set_default(cfg.id)

    # 重新加载
    mgr2 = LLMConfigManager(config_file=config_path)
    loaded = mgr2.get(cfg.id)
    assert loaded is not None
    assert loaded.name == "持久化测试"
    assert loaded.is_default is True


def test_api_key_not_stored_in_plain(config_path):
    mgr = LLMConfigManager(config_file=config_path)
    cfg = make_config()
    mgr.add(cfg)

    with open(config_path) as f:
        raw = json.load(f)
    items = raw["configs"]
    assert all("test-key" not in str(item.get("api_key_encrypted", "")) for item in items)


def test_normalize_ollama_api_base_appends_v1():
    assert (
        _normalize_api_base("http://192.168.5.162:11434/", LLMProvider.OLLAMA)
        == "http://192.168.5.162:11434/v1"
    )
    assert (
        _normalize_api_base("http://192.168.5.162:11434/v1", LLMProvider.OLLAMA)
        == "http://192.168.5.162:11434/v1"
    )


def test_make_client_normalizes_ollama_api_base():
    svc = LLMService()
    cfg = make_config(
        provider=LLMProvider.OLLAMA,
        model_name="qwen2.5-coder:14b-instruct-q5_K_S",
        api_base="http://192.168.5.162:11434/",
    )

    client = svc._make_client(cfg)

    assert client.api_base == "http://192.168.5.162:11434/v1"
    assert client.model == "qwen2.5-coder:14b-instruct-q5_K_S"


def test_build_json_headers_omits_authorization_for_blank_key():
    assert _build_json_headers("") == {"Content-Type": "application/json"}
    assert _build_json_headers("  ", {"X-Test": "1"}) == {
        "Content-Type": "application/json",
        "X-Test": "1",
    }


def test_merge_openai_compatible_payload_flattens_extra_body():
    payload = _merge_openai_compatible_payload(
        {"model": "qwen3-32b-fp8"},
        {
            "extra_body": {
                "chat_template_kwargs": {"enable_thinking": False},
            },
            "temperature": 0.2,
        },
    )

    assert payload == {
        "model": "qwen3-32b-fp8",
        "chat_template_kwargs": {"enable_thinking": False},
        "temperature": 0.2,
    }


def test_normalize_litellm_ollama_api_base_appends_v1():
    assert (
        _normalize_litellm_api_base("http://192.168.5.162:11434/", "ollama")
        == "http://192.168.5.162:11434/v1"
    )
    assert (
        _normalize_litellm_api_base("http://192.168.5.162:11434/v1/", "ollama")
        == "http://192.168.5.162:11434/v1"
    )


def test_normalize_reasoning_mode_defaults_unknown_values():
    assert normalize_reasoning_mode(None) == "default"
    assert normalize_reasoning_mode("NON-THINKING") == "non-thinking"
    assert normalize_reasoning_mode("weird") == "default"


def test_build_reasoning_request_kwargs_for_qwen_non_thinking():
    assert build_reasoning_request_kwargs(
        LLMProvider.QWEN,
        "https://dashscope.aliyuncs.com/api/v1",
        "non-thinking",
    ) == {"enable_thinking": False}


def test_build_reasoning_request_kwargs_for_ollama_non_thinking():
    assert build_reasoning_request_kwargs(
        LLMProvider.OLLAMA,
        "http://127.0.0.1:11434",
        "non-thinking",
    ) == {
        "extra_body": {
            "chat_template_kwargs": {
                "enable_thinking": False,
            }
        }
    }


def test_reasoning_mode_persists(config_path):
    mgr1 = LLMConfigManager(config_file=config_path)
    cfg = make_config(reasoning_mode="non-thinking")
    mgr1.add(cfg)

    mgr2 = LLMConfigManager(config_file=config_path)
    loaded = mgr2.get(cfg.id)

    assert loaded is not None
    assert loaded.reasoning_mode == "non-thinking"


def test_make_client_requires_api_key_for_cloud_models():
    svc = LLMService()
    cfg = make_config(api_key_encrypted="")

    with pytest.raises(ValueError, match="api_key 不能为空"):
        svc._make_client(cfg)


def test_make_client_allows_empty_key_for_local_models():
    svc = LLMService()
    cfg = make_config(
        provider=LLMProvider.OLLAMA,
        api_base="http://192.168.5.162:11434/",
        api_key_encrypted="",
    )

    client = svc._make_client(cfg)

    assert client.api_key == ""
    assert client.api_base == "http://192.168.5.162:11434/v1"


def test_resolve_litellm_api_key_uses_placeholder_for_local_openai_compatible():
    assert _resolve_litellm_api_key("ollama", "") == "local-openai-compatible"
    assert _resolve_litellm_api_key("deepseek", "") == ""


def test_build_adk_litellm_model_passes_placeholder_api_key(monkeypatch):
    captured = {}
    pytest.importorskip("google.adk")
    import google.adk.models.lite_llm as lite_llm_module

    class DummyLiteLlm:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(lite_llm_module, "LiteLlm", DummyLiteLlm)

    build_adk_litellm_model(
        LiteLLMModelConfig(
            model="openai/qwen3-32b-fp8",
            provider="ollama",
            api_key="local-openai-compatible",
            api_base="http://192.168.2.66:8010/v1",
            temperature=0.7,
            max_tokens=4096,
            top_p=0.9,
            request_kwargs={},
            model_kwargs={},
        )
    )

    assert captured["model"] == "openai/qwen3-32b-fp8"
    assert captured["api_base"] == "http://192.168.2.66:8010/v1"
    assert captured["api_key"] == "local-openai-compatible"


def test_thought_tool_stays_enabled_for_local_openai_compatible_models():
    cfg = LiteLLMModelConfig(
        model="openai/qwen3-32b-fp8",
        provider="ollama",
        api_key="",
        api_base="http://192.168.2.66:8010/v1",
        temperature=0.7,
        max_tokens=4096,
        top_p=0.9,
        request_kwargs={},
        model_kwargs={},
    )

    assert should_enable_thought_tool(cfg) is True


def test_test_connection_handles_complete_tuple(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("pydantic")
    from llm import routes
    import llm.service as llm_service

    cfg = make_config(id="ollama-test", provider=LLMProvider.OLLAMA)

    class DummyManager:
        def get(self, config_id):
            return cfg if config_id == cfg.id else None

    async def fake_complete(self, system_prompt, messages, user_message, config_id=None):
        return "OK", {"total_tokens": 1}

    monkeypatch.setattr(routes, "_manager", DummyManager())
    monkeypatch.setattr(llm_service.LLMService, "complete", fake_complete)

    result = asyncio.run(routes.test_connection(cfg.id))

    assert result["success"] is True
    assert result["response"] == "OK"


def test_update_config_applies_provider_and_default(monkeypatch, config_path):
    pytest.importorskip("fastapi")
    pytest.importorskip("pydantic")
    from llm import routes

    manager = LLMConfigManager(config_file=config_path)
    cfg1 = make_config(id="cfg-1", name="DeepSeek", is_default=True)
    cfg2 = make_config(id="cfg-2", name="QWen", is_default=False)
    manager.add(cfg1)
    manager.add(cfg2)

    monkeypatch.setattr(routes, "_manager", manager)

    result = asyncio.run(
        routes.update_config(
            "cfg-2",
            routes.LLMConfigUpdate(provider=LLMProvider.OLLAMA, is_default=True),
        )
    )

    updated = manager.get("cfg-2")
    original = manager.get("cfg-1")

    assert updated is not None
    assert updated.provider == LLMProvider.OLLAMA
    assert updated.is_default is True
    assert updated.reasoning_mode == "default"
    assert original is not None
    assert original.is_default is False
    assert result.provider == "ollama"
    assert result.is_default is True
    assert result.reasoning_mode == "default"
