"""
Compatibility tool for local models that hallucinate a `thought` tool call.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def should_enable_thought_tool(llm_config) -> bool:
    """Enable the compatibility shim only for Ollama-backed models."""
    provider = str(getattr(llm_config, "provider", "") or "").strip().lower()
    model = str(getattr(llm_config, "model", "") or "").strip().lower()
    return provider == "ollama" or model.startswith("ollama/")


def create_thought_tool():
    """Return a no-op tool that nudges the model back to real tools."""
    call_count = 0

    async def thought() -> str:
        nonlocal call_count
        call_count += 1
        logger.warning(
            "thought tool compatibility shim invoked count=%s",
            call_count,
        )
        if call_count > 1:
            return (
                "不要重复调用 `thought`。它只是兼容性占位，不执行任何业务。"
                "请直接调用真实工具，或直接用中文回复用户。"
            )
        return (
            "`thought` 不是业务工具，只是为了兼容本地模型误调用而保留的空操作。"
            "接下来请改为调用真实工具，或直接用中文回复用户。"
        )

    return thought
