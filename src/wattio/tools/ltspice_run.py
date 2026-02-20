"""LTspice single simulation tool — run a sim with optional parameter changes."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class LTspiceRunTool(BaseTool):
    name = "ltspice_run"
    description = (
        "Run an LTspice simulation with optional parameter changes. "
        "Copies the schematic to a working directory, applies .param changes, "
        "runs the simulation, and returns min/max/avg/rms measurements. "
        "Windows only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "schematic_path": {
                "type": "string",
                "description": "Path to the .asc schematic file (relative to project directory).",
            },
            "param_changes": {
                "type": "object",
                "description": (
                    "Dict of .param name to new value. "
                    'E.g. {"load_resistance": "8", "fsw": "200k"}.'
                ),
            },
            "traces": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    'List of traces to measure, e.g. ["V(OUT)", "I(L1)"]. '
                    "Default: all traces in the .raw file."
                ),
            },
            "tran_time": {
                "type": "string",
                "description": 'Override transient simulation time, e.g. "500m" for 500ms.',
            },
            "measure_start": {
                "type": "number",
                "description": (
                    "Start time (seconds) for measurement window. "
                    "Default: last 20%% of simulation."
                ),
            },
        },
        "required": ["schematic_path"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        from wattio.tools.ltspice_helpers import (
            check_platform,
            compute_measurements,
            create_working_copy,
            eng,
            ensure_sim_workdir,
            find_ltspice_exe,
            validate_schematic_path,
        )

        # ── Platform check ──────────────────────────────────────
        platform_err = check_platform()
        if platform_err:
            return ToolResult(tool_call_id="", content=platform_err, is_error=True)

        # ── Find LTspice ────────────────────────────────────────
        ltspice_exe = find_ltspice_exe()
        if not ltspice_exe:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: LTspice executable not found. "
                    "Install LTspice from https://www.analog.com/ltspice "
                    "or add it to your PATH."
                ),
                is_error=True,
            )

        # ── Validate schematic ──────────────────────────────────
        schematic_path = kwargs.get("schematic_path", "")
        result = validate_schematic_path(project_dir, schematic_path)
        if isinstance(result, str):
            return ToolResult(tool_call_id="", content=result, is_error=True)
        original_asc = result

        # ── Create working copy ─────────────────────────────────
        work_dir = ensure_sim_workdir(project_dir)
        work_asc = create_working_copy(original_asc, work_dir)

        # ── Apply parameter changes ─────────────────────────────
        param_changes = kwargs.get("param_changes", {})
        tran_time = kwargs.get("tran_time")

        try:
            from PyLTSpice import AscEditor
        except ImportError:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: PyLTSpice is not installed. "
                    "Install it with: pip install PyLTSpice"
                ),
                is_error=True,
            )

        try:
            editor = AscEditor(str(work_asc))

            for name, value in param_changes.items():
                editor.set_parameter(name, value)

            if tran_time:
                # Update the .tran directive
                editor.set_parameter("tran", tran_time)

            editor.write_netlist(str(work_asc))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error modifying schematic: {e}",
                is_error=True,
            )

        # ── Run simulation ──────────────────────────────────────
        try:
            proc = await asyncio.create_subprocess_exec(
                str(ltspice_exe),
                "-b",
                str(work_asc),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id="",
                content="Error: Simulation timed out after 5 minutes.",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error running LTspice: {e}",
                is_error=True,
            )

        # ── Find and parse .raw file ────────────────────────────
        raw_path = work_asc.with_suffix(".raw")
        if not raw_path.is_file():
            log_path = work_asc.with_suffix(".log")
            log_content = ""
            if log_path.is_file():
                log_content = log_path.read_text(errors="replace")[-2000:]
            return ToolResult(
                tool_call_id="",
                content=(
                    f"Error: Simulation did not produce a .raw file.\n"
                    f"Log output:\n{log_content}"
                ),
                is_error=True,
            )

        try:
            from PyLTSpice import RawRead
        except ImportError:
            return ToolResult(
                tool_call_id="",
                content="Error: PyLTSpice is not installed.",
                is_error=True,
            )

        try:
            raw = RawRead(str(raw_path))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error reading .raw file: {e}",
                is_error=True,
            )

        # ── Extract measurements ────────────────────────────────
        traces_requested = kwargs.get("traces")
        measure_start = kwargs.get("measure_start")

        available_traces = raw.get_trace_names()
        time_trace = raw.get_trace("time")
        time_data = time_trace.get_wave()

        if traces_requested:
            trace_names = [
                t for t in traces_requested if t.lower() in [a.lower() for a in available_traces]
            ]
            if not trace_names:
                return ToolResult(
                    tool_call_id="",
                    content=(
                        f"Error: None of the requested traces found.\n"
                        f"Available: {', '.join(available_traces)}"
                    ),
                    is_error=True,
                )
        else:
            # All traces except time
            trace_names = [t for t in available_traces if t.lower() != "time"]

        lines = [
            f"**Simulation complete:** `{schematic_path}`",
            f"**Raw file:** `{raw_path.relative_to(project_dir)}`",
            "",
            "| Trace | Min | Max | Avg | RMS | P-P | Final |",
            "|-------|-----|-----|-----|-----|-----|-------|",
        ]

        for trace_name in trace_names:
            try:
                trace = raw.get_trace(trace_name)
                data = trace.get_wave()
                m = compute_measurements(time_data, data, measure_start)

                # Determine unit from trace name
                unit = "V" if trace_name.upper().startswith("V") else "A"

                lines.append(
                    f"| {trace_name} "
                    f"| {eng(m['min'], unit)} "
                    f"| {eng(m['max'], unit)} "
                    f"| {eng(m['avg'], unit)} "
                    f"| {eng(m['rms'], unit)} "
                    f"| {eng(m['peak_to_peak'], unit)} "
                    f"| {eng(m['final'], unit)} |"
                )
            except Exception as e:
                lines.append(f"| {trace_name} | Error: {e} |||||")

        if param_changes:
            lines.append("")
            lines.append("**Parameters changed:**")
            for name, value in param_changes.items():
                lines.append(f"- `{name}` = `{value}`")

        return ToolResult(tool_call_id="", content="\n".join(lines))
