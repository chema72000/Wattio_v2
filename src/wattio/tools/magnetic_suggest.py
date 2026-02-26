"""OTS magnetic component search via magnetic-suggest subprocess."""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class MagneticSuggestTool(BaseTool):
    name = "magnetic_suggest"
    description = (
        "Search for off-the-shelf (OTS) magnetic components (inductors, transformers) "
        "that match an LTspice schematic. Analyzes the .asc file to extract inductance, "
        "turns ratio, and current requirements, then searches distributor catalogs. "
        "Requires the path to a .asc LTspice schematic file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "schematic_path": {
                "type": "string",
                "description": "Path to the LTspice .asc schematic file (relative to project directory).",
            },
            "margin": {
                "type": "number",
                "description": "Current margin multiplier (e.g., 1.3 = 30% margin). Default: 1.3.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of suggestions per component. Default: 3.",
            },
            "topology": {
                "type": "string",
                "description": "Transformer topology override (e.g., 'flyback', 'forward'). Default: 'auto'.",
            },
        },
        "required": ["schematic_path"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        schematic_path = kwargs.get("schematic_path", "")
        margin = kwargs.get("margin", 1.3)
        limit = kwargs.get("limit", 3)
        topology = kwargs.get("topology", "auto")

        if not schematic_path:
            return ToolResult(
                tool_call_id="",
                content="Error: schematic_path is required.",
                is_error=True,
            )

        full_path = (project_dir / schematic_path).resolve()

        # Security: don't allow access outside project dir
        if not str(full_path).startswith(str(project_dir.resolve())):
            return ToolResult(
                tool_call_id="",
                content="Error: Cannot access files outside the project directory.",
                is_error=True,
            )

        if not full_path.is_file():
            return ToolResult(
                tool_call_id="",
                content=f"Error: Schematic file not found: {schematic_path}",
                is_error=True,
            )

        if not full_path.suffix.lower() == ".asc":
            return ToolResult(
                tool_call_id="",
                content="Error: File must be an LTspice schematic (.asc).",
                is_error=True,
            )

        # Find magnetic-suggest: check the running venv first, then PATH
        venv_scripts = Path(sys.executable).parent
        binary = shutil.which("magnetic-suggest", path=str(venv_scripts))
        if not binary:
            binary = shutil.which("magnetic-suggest")

        if binary:
            cmd = [
                binary,
                str(full_path),
                "--margin", str(margin),
                "--limit", str(limit),
                "--topology", topology,
            ]
        else:
            # Fall back to running as a module with the current interpreter
            cmd = [
                sys.executable, "-m", "magnetic_suggest.cli",
                str(full_path),
                "--margin", str(margin),
                "--limit", str(limit),
                "--topology", topology,
            ]

        # Force UTF-8 so rich doesn't choke on emoji via the legacy
        # Windows console renderer (cp1252 can't encode them).
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id="",
                content="Error: magnetic-suggest timed out after 60 seconds.",
                is_error=True,
            )
        except FileNotFoundError:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: magnetic-suggest is not installed. "
                    "Install it with: pip install magnetic-suggest"
                ),
                is_error=True,
            )

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace").strip()
            return ToolResult(
                tool_call_id="",
                content=f"Error running magnetic-suggest (exit code {proc.returncode}):\n{error_msg}",
                is_error=True,
            )

        output = stdout.decode(errors="replace").strip()
        if not output:
            output = "No matching components found."

        return ToolResult(tool_call_id="", content=output)
