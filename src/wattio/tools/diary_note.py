"""Tool for adding explicit notes and decisions to the session diary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class DiaryNoteTool(BaseTool):
    name = "diary_note"
    description = (
        "Add an explicit note, decision, or action item to the session diary. "
        "Use this when the engineer wants to record a decision, a TODO, "
        "a recommendation, or any important note for future reference. "
        "The diary is stored in wattio/diary/YYYY-MM-DD.md."
    )
    parameters = {
        "type": "object",
        "properties": {
            "note": {
                "type": "string",
                "description": "The note or decision to record.",
            },
            "category": {
                "type": "string",
                "description": "Category: 'decision', 'todo', 'recommendation', or 'note'. Default: 'note'.",
                "enum": ["decision", "todo", "recommendation", "note"],
            },
        },
        "required": ["note"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        note = kwargs.get("note", "")
        category = kwargs.get("category", "note")

        if not note:
            return ToolResult(
                tool_call_id="",
                content="Error: note is required.",
                is_error=True,
            )

        # Import here to avoid circular dependency
        from wattio.diary.writer import DiaryWriter

        writer = DiaryWriter(project_dir)
        writer._ensure_session_header()

        icons = {
            "decision": "\u2705",       # checkmark
            "todo": "\u2610",           # ballot box
            "recommendation": "\u2b50", # star
            "note": "\U0001F4CC",       # pin 📌
        }
        icon = icons.get(category, "\U0001F4CC")
        label = category.upper()

        with open(writer._file, "a", encoding="utf-8") as f:
            f.write(f"### {writer._timestamp()} — {icon} {label}\n{note}\n\n")

        return ToolResult(
            tool_call_id="",
            content=f"Recorded {category} in diary: {note}",
        )
