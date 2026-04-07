"""Helpers for loading prompt templates from standalone text files."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent / "prompt_templates"


def load_prompt_template(name: str, slots: Mapping[str, str] | None = None) -> str:
    """Load a prompt template and replace ``{{slot}}`` placeholders."""
    template_path = PROMPT_TEMPLATE_DIR / name
    content = template_path.read_text(encoding="utf-8")

    rendered = content
    for key, value in (slots or {}).items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)

    return rendered
