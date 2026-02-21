"""Markdown diary writer — logs every interaction to wattio/diary/YYYY-MM-DD.md."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

_SIMULATION_LABELS: dict[str, str] = {
    "ltspice_run": "Simulation",
    "ltspice_sweep": "Parameter sweep",
    "ltspice_plot": "Waveform plot",
    "ltspice_edit": "Schematic edit",
}


class DiaryWriter:
    """Appends entries to today's diary file."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir
        self._diary_dir = project_dir / "wattio" / "diary"
        self._diary_dir.mkdir(parents=True, exist_ok=True)
        self._session_start = datetime.now()
        self._file = self._get_diary_path()
        self._started = False

    def _get_diary_path(self) -> Path:
        return self._diary_dir / f"{self._session_start.strftime('%Y-%m-%d')}.md"

    def _ensure_session_header(self) -> None:
        """Write session header on first entry."""
        if self._started:
            return
        self._started = True

        is_new = not self._file.exists()
        with open(self._file, "a", encoding="utf-8") as f:
            if is_new:
                f.write(f"# Wattio Session Diary — {self._session_start.strftime('%Y-%m-%d')}\n\n")
            time_str = self._session_start.strftime("%H:%M")
            f.write(f"## Session {time_str} — {self._project_dir.name}\n\n")

    def _timestamp(self) -> str:
        return datetime.now().strftime("%H:%M")

    def log_user(self, text: str) -> None:
        self._ensure_session_header()
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"### {self._timestamp()} — User\n{text}\n\n")

    def log_assistant(self, text: str) -> None:
        self._ensure_session_header()
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"### {self._timestamp()} — Wattio\n{text}\n\n")

    def log_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        self._ensure_session_header()
        args_str = json.dumps(arguments, indent=2) if arguments else ""
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"> **Tool call:** `{tool_name}`\n")
            if args_str:
                f.write("> ```json\n")
                for arg_line in args_str.splitlines():
                    f.write(f"> {arg_line}\n")
                f.write("> ```\n")
            f.write("\n")

    def log_tool_result(self, content: str, is_error: bool = False) -> None:
        self._ensure_session_header()
        label = "Error" if is_error else "Result"
        # Truncate very long results in the diary
        if len(content) > 2000:
            content = content[:2000] + "\n... (truncated)"
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"> **{label}:**\n> ```\n")
            for line in content.splitlines():
                f.write(f"> {line}\n")
            f.write("> ```\n\n")

    def log_simulation(
        self,
        tool_name: str,
        schematic: str,
        summary: str,
        params: dict[str, str] | None = None,
        traces: list[str] | None = None,
        plot_path: str | None = None,
    ) -> None:
        """Write a structured simulation entry after the raw tool result."""
        self._ensure_session_header()
        label = _SIMULATION_LABELS.get(tool_name, "Simulation")
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"#### {self._timestamp()} \u2014 {label}\n")
            f.write(f"**Schematic:** `{schematic}`\n\n")
            if params:
                param_str = ", ".join(f"`{k}={v}`" for k, v in params.items())
                f.write(f"**Parameters:** {param_str}\n\n")
            if traces:
                traces_str = ", ".join(f"`{t}`" for t in traces)
                f.write(f"**Traces:** {traces_str}\n\n")
            f.write(f"{summary}\n\n")
            if plot_path:
                f.write(f"![{label} plot]({plot_path})\n\n")

    def close_session(self) -> None:
        if not self._started:
            return
        now = datetime.now()
        duration = now - self._session_start
        minutes = int(duration.total_seconds() // 60)
        if minutes >= 60:
            duration_str = f"{minutes // 60}h{minutes % 60:02d}m"
        else:
            duration_str = f"{minutes}m"
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(f"---\n## Session ended {now.strftime('%H:%M')} (duration: {duration_str})\n\n")

        # Auto-export to docx
        self._export_docx()

    def _export_docx(self) -> None:
        """Export today's diary to .docx alongside the .md file."""
        try:
            from wattio.diary.export import export_diary
            date_str = self._session_start.strftime("%Y-%m-%d")
            export_diary(self._project_dir, date_str)
        except Exception:
            pass  # Don't let export failure break the session close
