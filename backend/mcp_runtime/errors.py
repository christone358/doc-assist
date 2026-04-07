"""Standardized MCP runtime errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class MCPRuntimeError(Exception):
    """Structured runtime error used by namespace adapters."""

    error_type: str
    message: str
    target: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message

    def to_result(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "message": self.message,
            "target": self.target,
            "details": self.details,
        }
