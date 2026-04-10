"""Tool for reading project files (.asc, .txt, .csv, images, etc.)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

# Maximum file size to read (500 KB for text, 5 MB for images)
MAX_FILE_SIZE = 512_000
MAX_IMAGE_SIZE = 5_242_880

ALLOWED_EXTENSIONS = {
    ".asc", ".txt", ".csv", ".tsv", ".log", ".md",
    ".net", ".sub", ".lib", ".plt", ".cfg", ".toml",
    ".json", ".yaml", ".yml",
}

IMAGE_EXTENSIONS = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

ALL_SUPPORTED = ALLOWED_EXTENSIONS | set(IMAGE_EXTENSIONS)


class FileReaderTool(BaseTool):
    name = "file_reader"
    description = (
        "Read the contents of a project file. Supports LTspice schematics (.asc), "
        "text files, CSV, markdown, configuration files, and images (.png, .jpg). "
        "Use this to inspect schematics, simulation settings, design notes, or screenshots. "
        "IMPORTANT: Always use list_files first to discover the exact file name — "
        "never guess file paths, especially when names contain special characters like '/'."
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
            # Try to help: list files in the parent directory
            parent = full_path.parent
            suggestions = ""
            if parent.is_dir():
                files = sorted(f.name for f in parent.iterdir() if f.is_file())[:10]
                if files:
                    suggestions = "\nFiles in that directory:\n" + "\n".join(f"  - {f}" for f in files)
            return ToolResult(
                tool_call_id="",
                content=f"Error: File not found: {rel_path}.{suggestions}\n\n"
                        f"Hint: Use `list_files` first to discover exact file names.",
                is_error=True,
            )

        suffix = full_path.suffix.lower()

        if suffix not in ALL_SUPPORTED:
            return ToolResult(
                tool_call_id="",
                content=f"Error: Unsupported file type: {suffix}. "
                        f"Supported: {', '.join(sorted(ALL_SUPPORTED))}",
                is_error=True,
            )

        # Handle image files
        if suffix in IMAGE_EXTENSIONS:
            if full_path.stat().st_size > MAX_IMAGE_SIZE:
                return ToolResult(
                    tool_call_id="",
                    content=f"Error: Image too large ({full_path.stat().st_size} bytes). Max: {MAX_IMAGE_SIZE}.",
                    is_error=True,
                )
            try:
                image_data = full_path.read_bytes()
                image_b64 = base64.b64encode(image_data).decode("ascii")
            except Exception as e:
                return ToolResult(
                    tool_call_id="", content=f"Error reading image: {e}", is_error=True
                )
            return ToolResult(
                tool_call_id="",
                content=f"Image loaded: {rel_path} ({len(image_data)} bytes)",
                image_base64=image_b64,
                image_media_type=IMAGE_EXTENSIONS[suffix],
            )

        # Handle text files
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
