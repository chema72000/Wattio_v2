"""Auto-discovers all BaseTool subclasses in the tools/ package."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from wattio.tools.base import BaseTool


class ToolRegistry:
    """Finds and holds all available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    @property
    def all_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_openai_schemas(self) -> list[dict]:
        return [t.to_openai_schema() for t in self._tools.values()]

    @classmethod
    def auto_discover(cls) -> ToolRegistry:
        """Import all modules in wattio.tools and register BaseTool subclasses."""
        registry = cls()
        package_path = Path(__file__).parent

        for module_info in pkgutil.iter_modules([str(package_path)]):
            if module_info.name in ("base", "registry", "__init__"):
                continue
            module = importlib.import_module(f"wattio.tools.{module_info.name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseTool)
                    and attr is not BaseTool
                ):
                    registry.register(attr())

        return registry
