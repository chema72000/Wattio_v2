"""Base class for all Wattio tools (the plugin contract)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from wattio.models import ToolResult


class BaseTool(ABC):
    """Every tool must inherit from this class."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for arguments

    @abstractmethod
    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        """Run the tool and return a result."""

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function-calling tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
