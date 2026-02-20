"""LTspice parameter sweep tool — sweep a parameter and plot results."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

MAX_SWEEP_POINTS = 50


class LTspiceSweepTool(BaseTool):
    name = "ltspice_sweep"
    description = (
        "Sweep a .param parameter across a range, run an LTspice simulation "
        "for each value, extract a measurement (peak-to-peak, avg, rms, etc.), "
        "and generate a plot. Saves PNG to wattio/results/. Windows only."
    )
    parameters = {
        "type": "object",
        "properties": {
            "schematic_path": {
                "type": "string",
                "description": "Path to the .asc schematic file (relative to project directory).",
            },
            "sweep_param": {
                "type": "string",
                "description": "Name of the .param to sweep (e.g. 'fsw', 'load_resistance').",
            },
            "start": {
                "type": "number",
                "description": "Sweep start value.",
            },
            "stop": {
                "type": "number",
                "description": "Sweep stop value.",
            },
            "step": {
                "type": "number",
                "description": "Sweep step size.",
            },
            "measure_trace": {
                "type": "string",
                "description": 'Trace to measure at each sweep point, e.g. "I(L1)" or "V(OUT)".',
            },
            "measure_type": {
                "type": "string",
                "enum": ["peak_to_peak", "avg", "rms", "max", "min"],
                "description": "Measurement type. Default: peak_to_peak.",
            },
            "measure_start": {
                "type": "number",
                "description": "Start time (seconds) for measurement window. Default: last 20%%.",
            },
            "plot_title": {
                "type": "string",
                "description": "Optional plot title.",
            },
            "x_label": {
                "type": "string",
                "description": "Optional x-axis label.",
            },
            "y_label": {
                "type": "string",
                "description": "Optional y-axis label.",
            },
        },
        "required": ["schematic_path", "sweep_param", "start", "stop", "step", "measure_trace"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        from wattio.tools.ltspice_helpers import (
            check_platform,
            compute_measurements,
            create_working_copy,
            eng,
            ensure_results_dir,
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

        # ── Validate inputs ─────────────────────────────────────
        schematic_path = kwargs.get("schematic_path", "")
        result = validate_schematic_path(project_dir, schematic_path)
        if isinstance(result, str):
            return ToolResult(tool_call_id="", content=result, is_error=True)
        original_asc = result

        sweep_param = kwargs["sweep_param"]
        start = kwargs["start"]
        stop = kwargs["stop"]
        step_size = kwargs["step"]
        measure_trace = kwargs["measure_trace"]
        measure_type = kwargs.get("measure_type", "peak_to_peak")
        measure_start = kwargs.get("measure_start")

        if step_size <= 0:
            return ToolResult(
                tool_call_id="",
                content="Error: step must be positive.",
                is_error=True,
            )

        # Calculate sweep points
        num_points = int((stop - start) / step_size) + 1
        if num_points > MAX_SWEEP_POINTS:
            return ToolResult(
                tool_call_id="",
                content=(
                    f"Error: Sweep would require {num_points} points "
                    f"(max {MAX_SWEEP_POINTS}). Increase step size."
                ),
                is_error=True,
            )

        sweep_values = [start + i * step_size for i in range(num_points)]

        # ── Import dependencies ─────────────────────────────────
        try:
            from PyLTSpice import AscEditor, RawRead
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
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: matplotlib is not installed. "
                    "Install it with: pip install matplotlib"
                ),
                is_error=True,
            )

        # ── Run sweep ───────────────────────────────────────────
        work_dir = ensure_sim_workdir(project_dir)
        results_data: list[tuple[float, float | None, str]] = []  # (param_val, measurement, status)

        for idx, val in enumerate(sweep_values):
            suffix = f"_sweep_{idx:03d}"
            try:
                work_asc = create_working_copy(original_asc, work_dir, suffix)

                editor = AscEditor(str(work_asc))
                editor.set_parameter(sweep_param, str(val))
                editor.write_netlist(str(work_asc))

                proc = await asyncio.create_subprocess_exec(
                    str(ltspice_exe),
                    "-b",
                    str(work_asc),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.communicate(), timeout=300)

                raw_path = work_asc.with_suffix(".raw")
                if not raw_path.is_file():
                    results_data.append((val, None, "No .raw output"))
                    continue

                raw = RawRead(str(raw_path))
                time_trace = raw.get_trace("time")
                time_data = time_trace.get_wave()

                trace = raw.get_trace(measure_trace)
                data = trace.get_wave()

                m = compute_measurements(time_data, data, measure_start)
                measurement = m[measure_type]
                results_data.append((val, measurement, "OK"))

            except asyncio.TimeoutError:
                results_data.append((val, None, "Timeout"))
            except Exception as e:
                results_data.append((val, None, str(e)))

        # ── Generate plot ───────────────────────────────────────
        successful = [(v, m) for v, m, s in results_data if m is not None]
        if not successful:
            return ToolResult(
                tool_call_id="",
                content="Error: All sweep points failed. Check schematic and parameters.",
                is_error=True,
            )

        x_vals = [v for v, _ in successful]
        y_vals = [m for _, m in successful]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x_vals, y_vals, "o-", linewidth=2, markersize=6)

        plot_title = kwargs.get("plot_title") or (
            f"{measure_type.replace('_', ' ').title()} of {measure_trace} "
            f"vs {sweep_param}"
        )
        ax.set_title(plot_title)
        ax.set_xlabel(kwargs.get("x_label") or sweep_param)
        ax.set_ylabel(kwargs.get("y_label") or f"{measure_trace} ({measure_type})")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        results_dir = ensure_results_dir(project_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plot_filename = f"sweep_{sweep_param}_{timestamp}.png"
        plot_path = results_dir / plot_filename

        fig.savefig(str(plot_path), dpi=150, bbox_inches="tight")
        plt.close(fig)

        # ── Build result table ──────────────────────────────────
        unit = "V" if measure_trace.upper().startswith("V") else "A"

        lines = [
            f"**Sweep complete:** `{sweep_param}` from {eng(start)} to {eng(stop)}",
            f"**Measurement:** {measure_type} of `{measure_trace}`",
            f"**Plot saved:** `{plot_path.relative_to(project_dir)}`",
            "",
            f"| {sweep_param} | {measure_trace} ({measure_type}) | Status |",
            "|---|---|---|",
        ]

        for val, measurement, status in results_data:
            if measurement is not None:
                lines.append(f"| {eng(val)} | {eng(measurement, unit)} | {status} |")
            else:
                lines.append(f"| {eng(val)} | — | {status} |")

        failed_count = sum(1 for _, m, _ in results_data if m is None)
        if failed_count:
            lines.append(f"\n*{failed_count}/{len(results_data)} sweep points failed.*")

        return ToolResult(tool_call_id="", content="\n".join(lines))
