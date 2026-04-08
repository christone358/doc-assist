"""
LiteLLM 适配层 - 将现有 llm_configs.json 格式转换为 LiteLLM 参数。
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# provider → LiteLLM 前缀映射
_PROVIDER_PREFIX = {
    "deepseek": "deepseek",
    "qwen": "openai",  # QWen 使用 OpenAI 兼容格式，通过 api_base 区分
    "ollama": "openai",  # 本地模型统一走 OpenAI 兼容接口，兼容 vLLM 与 Ollama /v1
}


@dataclass
class LiteLLMModelConfig:
    """LiteLLM 可直接使用的模型配置。"""
    model: str          # 例如 "deepseek/deepseek-chat"、"openai/qwen-plus"
    provider: str
    api_key: str
    api_base: str
    temperature: float
    max_tokens: int
    top_p: float
    request_kwargs: Dict[str, Any]
    model_kwargs: Dict[str, Any]


def _normalize_litellm_api_base(api_base: str, provider: str) -> str:
    """Normalize provider-specific api_base for LiteLLM."""
    from llm.service import _normalize_api_base, LLMProvider

    normalized = api_base.strip().rstrip("/")
    if provider != "ollama":
        return normalized

    return _normalize_api_base(normalized, LLMProvider.OLLAMA)


def _resolve_litellm_api_key(provider: str, api_key: Optional[str]) -> str:
    """Return a LiteLLM/OpenAI-client-safe API key value."""
    normalized = str(api_key or "").strip()
    if normalized:
        return normalized

    if provider == "ollama":
        # The OpenAI SDK refuses empty api_key values even for local servers.
        # vLLM/Ollama-compatible endpoints usually ignore the header value.
        return "local-openai-compatible"

    return ""


def _build_litellm_reasoning_kwargs(provider: str, reasoning_mode: str) -> Dict[str, Any]:
    """Build provider-specific kwargs for LiteLLM/OpenAI-compatible calls."""
    if reasoning_mode != "non-thinking":
        return {}

    if provider == "qwen":
        return {
            "extra_body": {
                "enable_thinking": False,
            }
        }

    if provider == "ollama":
        return {
            "extra_body": {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            }
        }

    return {}


def build_adk_litellm_model(llm_config: LiteLLMModelConfig):
    """Create an ADK LiteLlm model, with a safe fallback for unknown kwargs."""
    from google.adk.models.lite_llm import LiteLlm

    base_kwargs = {
        "model": llm_config.model,
        "api_base": llm_config.api_base,
    }
    if str(llm_config.api_key or "").strip():
        base_kwargs["api_key"] = llm_config.api_key
    try_kwargs = {**base_kwargs, **llm_config.model_kwargs}

    try:
        return LiteLlm(**try_kwargs)
    except TypeError:
        if llm_config.model_kwargs:
            logger.warning(
                "LiteLlm 不接受额外模型参数，已回退到基础初始化: model=%s, extra=%s",
                llm_config.model,
                list(llm_config.model_kwargs.keys()),
            )
        return LiteLlm(**base_kwargs)


def get_litellm_model_config() -> Optional[LiteLLMModelConfig]:
    """读取当前激活的默认 LLM 配置，返回 LiteLLM 可用的参数结构。

    Returns:
        LiteLLMModelConfig，若无可用配置则返回 None。
    """
    try:
        from llm.service import (
            LLMConfigManager,
            _decrypt_key,
            normalize_reasoning_mode,
        )

        manager = LLMConfigManager.get_instance()
        cfg = manager.get_default()

        if cfg is None:
            logger.warning("无可用的默认 LLM 配置，请通过设置界面添加模型配置")
            return None

        prefix = _PROVIDER_PREFIX.get(cfg.provider.value, cfg.provider.value)
        litellm_model = f"{prefix}/{cfg.model_name}"

        api_key = _resolve_litellm_api_key(
            cfg.provider.value,
            _decrypt_key(cfg.api_key_encrypted),
        )

        api_base = _normalize_litellm_api_base(cfg.api_base, cfg.provider.value)
        reasoning_mode = normalize_reasoning_mode(cfg.reasoning_mode)
        request_kwargs = _build_litellm_reasoning_kwargs(
            cfg.provider.value,
            reasoning_mode,
        )

        logger.debug(
            f"LiteLLM 配置: model={litellm_model}, api_base={api_base}"
        )

        return LiteLLMModelConfig(
            model=litellm_model,
            provider=cfg.provider.value,
            api_key=api_key,
            api_base=api_base,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            top_p=cfg.top_p,
            request_kwargs=request_kwargs,
            model_kwargs=request_kwargs.copy(),
        )

    except Exception as e:
        logger.error(f"读取 LLM 配置失败: {e}")
        return None
