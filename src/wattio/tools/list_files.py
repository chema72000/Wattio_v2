"""Tool for listing files in the project directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class ListFilesTool(BaseTool):
    name = "list_files"
    description = (
        "List files and directories in the project. Use this to discover what files "
        "exist before trying to read them. Can list a specific subdirectory or search "
        "for files by extension (e.g., '*.asc' to find LTspice schematics)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": (
                    "Directory to list, relative to the project root. "
                    "Use '.' or omit for the project root."
                ),
            },
            "pattern": {
                "type": "string",
                "description": (
                    "Optional glob pattern to filter files (e.g., '*.asc', '**/*.asc'). "
                    "Use '**/*.asc' to search recursively for all .asc files."
                ),
            },
        },
        "required": [],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        rel_dir = kwargs.get("directory", ".") or "."
        pattern = kwargs.get("pattern", "")

        target = (project_dir / rel_dir).resolve()

        # Security: stay inside project
        if not str(target).startswith(str(project_dir.resolve())):
            return ToolResult(
                tool_call_id="",
                content="Error: Cannot list files outside the project directory.",
                is_error=True,
            )

        if not target.is_dir():
            return ToolResult(
                tool_call_id="",
                content=f"Error: Directory not found: {rel_dir}",
                is_error=True,
            )

        if pattern:
            # Glob search
            matches = sorted(target.glob(pattern))
            if not matches:
                return ToolResult(
                    tool_call_id="",
                    content=f"No files matching '{pattern}' in {rel_dir}/",
                )
            lines = []
            for m in matches[:50]:  # Limit to 50 results
                try:
                    rel = m.relative_to(project_dir)
                except ValueError:
                    continue
                suffix = "/" if m.is_dir() else ""
                lines.append(f"  {rel}{suffix}")
            result = f"Files matching '{pattern}' in {rel_dir}/:\n" + "\n".join(lines)
            if len(matches) > 50:
                result += f"\n  ... and {len(matches) - 50} more"
            return ToolResult(tool_call_id="", content=result)

        # Regular directory listing
        try:
            entries = sorted(target.iterdir())
        except PermissionError:
            return ToolResult(
                tool_call_id="",
                content=f"Error: Permission denied: {rel_dir}",
                is_error=True,
            )

        lines = []
        for entry in entries:
            if entry.name.startswith("."):
                continue  # Skip hidden files
            try:
                rel = entry.relative_to(project_dir)
            except ValueError:
                continue
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"  {rel}{suffix}")

        if not lines:
            return ToolResult(
                tool_call_id="", content=f"Directory {rel_dir}/ is empty."
            )

        return ToolResult(
            tool_call_id="",
            content=f"Contents of {rel_dir}/:\n" + "\n".join(lines),
        )
