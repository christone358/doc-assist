"""
单元测试 - LLM 配置管理
"""
import pytest
import json
import uuid
from pathlib import Path
from llm.service import (
    LLMConfigManager, LLMConfig, LLMProvider,
    _encrypt_key, _decrypt_key,
)


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
