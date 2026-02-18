"""Tool for reading project files (.asc, .txt, .csv, etc.)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

# Maximum file size to read (500 KB)
MAX_FILE_SIZE = 512_000

ALLOWED_EXTENSIONS = {
    ".asc", ".txt", ".csv", ".tsv", ".log", ".md",
    ".net", ".sub", ".lib", ".plt", ".cfg", ".toml",
    ".json", ".yaml", ".yml",
}


class FileReaderTool(BaseTool):
    name = "file_reader"
    description = (
        "Read the contents of a project file. Supports LTspice schematics (.asc), "
        "text files, CSV, markdown, and configuration files. "
        "Use this to inspect schematics, simulation settings, or design notes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file (relative to the project directory).",
            },
        },
        "required": ["file_path"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        rel_path = kwargs.get("file_path", "")
        if not rel_path:
            return ToolResult(
                tool_call_id="", content="Error: file_path is required.", is_error=True
            )

        full_path = (project_dir / rel_path).resolve()

        # Security: don't allow reading outside project dir
        if not str(full_path).startswith(str(project_dir.resolve())):
            return ToolResult(
                tool_call_id="",
                content="Error: Cannot read files outside the project directory.",
                is_error=True,
            )

        if not full_path.is_file():
            return ToolResult(
                tool_call_id="",
                content=f"Error: File not found: {rel_path}",
                is_error=True,
            )

        if full_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return ToolResult(
                tool_call_id="",
                content=f"Error: Unsupported file type: {full_path.suffix}. "
                        f"Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                is_error=True,
            )

        if full_path.stat().st_size > MAX_FILE_SIZE:
            return ToolResult(
                tool_call_id="",
                content=f"Error: File too large ({full_path.stat().st_size} bytes). Max: {MAX_FILE_SIZE}.",
                is_error=True,
            )

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(
                tool_call_id="", content=f"Error reading file: {e}", is_error=True
            )

        return ToolResult(
            tool_call_id="",
            content=f"Contents of {rel_path}:\n\n{content}",
        )
