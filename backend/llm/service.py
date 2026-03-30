"""
LLM Service - Manages LLM model configurations and provides unified API.

Supports DeepSeek, QWen, and Ollama models with configuration management,
retry logic, and automatic fallback.
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncIterator
from dataclasses import dataclass, asdict, field
from enum import Enum
import hashlib
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

LLM_CONFIG_FILE = Path(__file__).parent.parent / "llm_configs.json"


# =============================================================================
# Data Models
# =============================================================================

class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for a single LLM model."""
    id: str
    name: str                         # User-friendly name, e.g. "生产环境 DeepSeek"
    provider: LLMProvider
    model_name: str                   # e.g. "deepseek-chat", "qwen-max"
    api_base: str                     # API endpoint base URL
    api_key_encrypted: str            # Encrypted API key (never plain text at rest)
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    extra_params: Dict[str, Any] = field(default_factory=dict)
    is_default: bool = False
    is_active: bool = True


@dataclass
class LLMMessage:
    role: str       # "system", "user", "assistant"
    content: str


# =============================================================================
# API Key Security
# =============================================================================

def _encrypt_key(plain_key: str) -> str:
    """Simple reversible obfuscation (use proper encryption in production)."""
    import base64
    return base64.b64encode(plain_key.encode()).decode()


def _decrypt_key(encrypted_key: str) -> str:
    """Reverse the obfuscation."""
    import base64
    return base64.b64decode(encrypted_key.encode()).decode()


def _normalize_api_base(api_base: str, provider: LLMProvider) -> str:
    """Normalize provider-specific base URLs."""
    normalized = api_base.strip().rstrip("/")
    if provider != LLMProvider.OLLAMA:
        return normalized

    parsed = urlsplit(normalized)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        return normalized

    # Ollama's OpenAI-compatible endpoint lives under /v1, but users often
    # paste the server root (for example http://host:11434/).
    path = f"{path}/v1" if path else "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


# =============================================================================
# Provider Clients
# =============================================================================

class DeepSeekClient:
    """Client for DeepSeek API (OpenAI-compatible)."""

    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model

    async def complete(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> tuple[str, Optional[dict]]:
        """Send a completion request. Returns (text, usage | None)."""
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            raw = data.get("usage") or {}
            usage = {
                "prompt_tokens": raw.get("prompt_tokens", 0),
                "completion_tokens": raw.get("completion_tokens", 0),
                "total_tokens": raw.get("total_tokens", 0),
            } if raw else None
            return text, usage

    async def stream(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str | dict]:
        """Stream a completion response. Yields text strings, then final {"usage": ...} dict."""
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            **kwargs,
        }

        usage = None
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(chunk)
                            # Capture usage from final chunk
                            if data.get("usage"):
                                raw = data["usage"]
                                usage = {
                                    "prompt_tokens": raw.get("prompt_tokens", 0),
                                    "completion_tokens": raw.get("completion_tokens", 0),
                                    "total_tokens": raw.get("total_tokens", 0),
                                }
                            delta = data["choices"][0].get("delta", {}) if data.get("choices") else {}
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue
        yield {"usage": usage}


class OllamaClient(DeepSeekClient):
    """Client for Ollama's OpenAI-compatible API."""

    def __init__(self, api_key: str, api_base: str, model: str):
        super().__init__(api_key, _normalize_api_base(api_base, LLMProvider.OLLAMA), model)


class QWenClient:
    """Client for QWen (Alibaba Cloud) API."""

    def __init__(self, api_key: str, api_base: str, model: str):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model

    async def complete(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> tuple[str, Optional[dict]]:
        """Send a completion request (OpenAI-compatible endpoint). Returns (text, usage | None)."""
        import httpx

        payload = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            },
        }

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.api_base}/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["output"]["text"]
            raw = data.get("usage") or {}
            # QWen uses input_tokens / output_tokens
            usage = {
                "prompt_tokens": raw.get("input_tokens", raw.get("prompt_tokens", 0)),
                "completion_tokens": raw.get("output_tokens", raw.get("completion_tokens", 0)),
                "total_tokens": raw.get("total_tokens", 0),
            } if raw else None
            return text, usage

    async def stream(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str | dict]:
        """Stream via SSE. Yields text strings, then final {"usage": ...} dict."""
        import httpx

        payload = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "incremental_output": True,
                **kwargs,
            },
        }

        usage = None
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.api_base}/api/v1/services/aigc/text-generation/generation",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-DashScope-SSE": "enable",
                },
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        chunk = line[5:].strip()
                        try:
                            data = json.loads(chunk)
                            # Capture usage if present
                            if data.get("usage"):
                                raw = data["usage"]
                                usage = {
                                    "prompt_tokens": raw.get("input_tokens", raw.get("prompt_tokens", 0)),
                                    "completion_tokens": raw.get("output_tokens", raw.get("completion_tokens", 0)),
                                    "total_tokens": raw.get("total_tokens", 0),
                                }
                            text = data.get("output", {}).get("text", "")
                            if text:
                                yield text
                        except json.JSONDecodeError:
                            continue
        yield {"usage": usage}


# =============================================================================
# Configuration Manager
# =============================================================================

class LLMConfigManager:
    """Manages LLM model configurations with persistence."""

    _instance: Optional["LLMConfigManager"] = None

    def __init__(self, config_file: Path = LLM_CONFIG_FILE):
        self.config_file = config_file
        self._configs: Dict[str, LLMConfig] = {}
        self._load()

    @classmethod
    def get_instance(cls) -> "LLMConfigManager":
        """Return the process-wide singleton (default config file)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self) -> None:
        if not self.config_file.exists():
            return
        try:
            data = json.loads(self.config_file.read_text())
            for item in data.get("configs", []):
                item["provider"] = LLMProvider(item["provider"])
                cfg = LLMConfig(**item)
                self._configs[cfg.id] = cfg
        except Exception as e:
            logger.error(f"Failed to load LLM configs: {e}")

    def _save(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"configs": [asdict(c) for c in self._configs.values()]}
        self.config_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )

    def add(self, config: LLMConfig) -> None:
        self._configs[config.id] = config
        self._save()

    def update(self, config: LLMConfig) -> bool:
        if config.id not in self._configs:
            return False
        self._configs[config.id] = config
        self._save()
        return True

    def delete(self, config_id: str) -> bool:
        if config_id not in self._configs:
            return False
        del self._configs[config_id]
        self._save()
        return True

    def get(self, config_id: str) -> Optional[LLMConfig]:
        return self._configs.get(config_id)

    def list_all(self) -> List[LLMConfig]:
        return list(self._configs.values())

    def get_default(self) -> Optional[LLMConfig]:
        for cfg in self._configs.values():
            if cfg.is_default and cfg.is_active:
                return cfg
        # Fallback: first active config
        for cfg in self._configs.values():
            if cfg.is_active:
                return cfg
        return None

    def set_default(self, config_id: str) -> bool:
        if config_id not in self._configs:
            return False
        for cfg in self._configs.values():
            cfg.is_default = cfg.id == config_id
        self._save()
        return True


# =============================================================================
# Unified LLM Service
# =============================================================================

class LLMService:
    """Unified service for calling LLMs with retry and fallback."""

    def __init__(self):
        self.config_manager = LLMConfigManager.get_instance()
        self._max_retries = 3
        self._retry_delay = 1.0

    async def initialize(self) -> None:
        cfg = self.config_manager.get_default()
        if cfg:
            logger.info(f"LLM Service ready. Default model: {cfg.name} ({cfg.model_name})")
        else:
            logger.warning("LLM Service: no model configured. Use /api/v1/llm/configs to add one.")

    def _make_client(self, config: LLMConfig):
        """Create the appropriate client for the provider."""
        api_base = config.api_base.strip()
        if not api_base or not api_base.startswith(("http://", "https://")):
            raise ValueError(f"api_base 无效（当前值：'{config.api_base}'）。请在 LLM 配置中填写完整的 URL，例如 https://api.deepseek.com")
        if not config.model_name:
            raise ValueError("model_name 不能为空，请在 LLM 配置中填写模型名称，例如 deepseek-chat")
        key = _decrypt_key(config.api_key_encrypted)
        if config.provider == LLMProvider.DEEPSEEK:
            return DeepSeekClient(key, api_base, config.model_name)
        elif config.provider == LLMProvider.QWEN:
            return QWenClient(key, api_base, config.model_name)
        elif config.provider == LLMProvider.OLLAMA:
            return OllamaClient(key, api_base, config.model_name)
        raise ValueError(f"Unsupported provider: {config.provider}")

    def _build_messages(
        self,
        system_prompt: str,
        messages: List[dict],
        user_message: str,
    ) -> List[dict]:
        result = [{"role": "system", "content": system_prompt}]
        result.extend(messages)
        result.append({"role": "user", "content": user_message})
        return result

    async def complete(
        self,
        system_prompt: str,
        messages: List[dict],
        user_message: str,
        config_id: Optional[str] = None,
    ) -> tuple[str, Optional[dict]]:
        """Complete a conversation. Returns (text, usage | None)."""
        cfg = (
            self.config_manager.get(config_id)
            if config_id
            else self.config_manager.get_default()
        )

        if not cfg:
            return "⚠️ 未配置 LLM 模型。请在系统设置中添加 DeepSeek、QWen 或 Ollama 模型配置。", None

        client = self._make_client(cfg)
        msgs = self._build_messages(system_prompt, messages, user_message)

        for attempt in range(self._max_retries):
            try:
                return await client.complete(
                    msgs,
                    temperature=cfg.temperature,
                    max_tokens=cfg.max_tokens,
                )
            except Exception as e:
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                else:
                    logger.error(f"All {self._max_retries} attempts failed")
                    return f"⚠️ LLM 调用失败：{str(e)}", None

    async def stream_complete(
        self,
        system_prompt: str,
        messages: List[dict],
        user_message: str,
        config_id: Optional[str] = None,
    ) -> AsyncIterator[str | dict]:
        """Stream a completion response. Yields text strings, then final {"usage": ...} dict."""
        cfg = (
            self.config_manager.get(config_id)
            if config_id
            else self.config_manager.get_default()
        )

        if not cfg:
            yield "⚠️ 未配置 LLM 模型。请在系统设置中添加 DeepSeek、QWen 或 Ollama 模型配置。"
            yield {"usage": None}
            return

        client = self._make_client(cfg)
        msgs = self._build_messages(system_prompt, messages, user_message)

        try:
            async for chunk in client.stream(
                msgs,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"\n⚠️ 流式输出中断：{str(e)}"
            yield {"usage": None}
