"""
LiteLLM 适配层 - 将现有 llm_configs.json 格式转换为 LiteLLM 参数。
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# provider → LiteLLM 前缀映射
_PROVIDER_PREFIX = {
    "deepseek": "deepseek",
    "qwen": "openai",  # QWen 使用 OpenAI 兼容格式，通过 api_base 区分
    "ollama": "ollama",
}


@dataclass
class LiteLLMModelConfig:
    """LiteLLM 可直接使用的模型配置。"""
    model: str          # 例如 "deepseek/deepseek-chat"、"openai/qwen-plus"
    api_key: str
    api_base: str
    temperature: float
    max_tokens: int


def _normalize_litellm_api_base(api_base: str, provider: str) -> str:
    """Normalize provider-specific api_base for LiteLLM."""
    normalized = api_base.strip().rstrip("/")
    if provider != "ollama":
        return normalized

    # LiteLLM's ollama provider expects the server root, not the OpenAI /v1 path.
    if normalized.endswith("/v1"):
        return normalized[:-3].rstrip("/")
    return normalized


def get_litellm_model_config() -> Optional[LiteLLMModelConfig]:
    """读取当前激活的默认 LLM 配置，返回 LiteLLM 可用的参数结构。

    Returns:
        LiteLLMModelConfig，若无可用配置则返回 None。
    """
    try:
        from llm.service import LLMConfigManager, _decrypt_key

        manager = LLMConfigManager.get_instance()
        cfg = manager.get_default()

        if cfg is None:
            logger.warning("无可用的默认 LLM 配置，请通过设置界面添加模型配置")
            return None

        prefix = _PROVIDER_PREFIX.get(cfg.provider.value, cfg.provider.value)
        litellm_model = f"{prefix}/{cfg.model_name}"

        api_key = _decrypt_key(cfg.api_key_encrypted)

        api_base = _normalize_litellm_api_base(cfg.api_base, cfg.provider.value)

        logger.debug(
            f"LiteLLM 配置: model={litellm_model}, api_base={api_base}"
        )

        return LiteLLMModelConfig(
            model=litellm_model,
            api_key=api_key,
            api_base=api_base,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    except Exception as e:
        logger.error(f"读取 LLM 配置失败: {e}")
        return None
