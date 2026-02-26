"""LTspice waveform plotting tool — plot traces from .raw files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class LTspicePlotTool(BaseTool):
    name = "ltspice_plot"
    description = (
        "Plot waveforms from an LTspice .raw simulation output file. "
        "Voltage traces go on the left y-axis, current traces on the right (dashed). "
        "Saves a PNG plot to wattio/results/. Windows only for simulation, "
        "but plotting works on any platform if a .raw file is available."
    )
    parameters = {
        "type": "object",
        "properties": {
            "raw_path": {
                "type": "string",
                "description": "Path to the .raw file (relative to project directory).",
            },
            "traces": {
                "type": "array",
                "items": {"type": "string"},
                "description": 'List of traces to plot, e.g. ["V(OUT)", "I(L1)"].',
            },
            "time_range": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Optional [start, end] time range in seconds to zoom in.",
            },
            "title": {
                "type": "string",
                "description": "Optional plot title.",
            },
            "step": {
                "type": "integer",
                "description": "For stepped sims, which step to plot (0-indexed).",
            },
        },
        "required": ["raw_path", "traces"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        from wattio.tools.ltspice_helpers import eng, ensure_results_dir

        raw_path_str = kwargs.get("raw_path", "")
        traces_requested = kwargs.get("traces", [])
        time_range = kwargs.get("time_range")
        title = kwargs.get("title", "")
        step_idx = kwargs.get("step", 0)

        if not raw_path_str:
            return ToolResult(
                tool_call_id="",
                content="Error: raw_path is required.",
                is_error=True,
            )

        if not traces_requested:
            return ToolResult(
                tool_call_id="",
                content="Error: traces list is required and cannot be empty.",
                is_error=True,
            )

        full_path = (project_dir / raw_path_str).resolve()

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
                content=f"Error: Raw file not found: {raw_path_str}",
                is_error=True,
            )

        # ── Import dependencies ─────────────────────────────────
        try:
            from PyLTSpice import RawRead
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

            matplotlib.use("Agg")  # Non-interactive backend
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

        # ── Read .raw file ──────────────────────────────────────
        try:
            raw = RawRead(str(full_path))
        except Exception as e:
            return ToolResult(
                tool_call_id="",
                content=f"Error reading .raw file: {e}",
                is_error=True,
            )

        available_traces = raw.get_trace_names()
        time_trace = raw.get_trace("time")
        time_data = np.real(np.asarray(time_trace.get_wave(step_idx)))

        # Separate voltage and current traces
        voltage_traces = []
        current_traces = []
        for name in traces_requested:
            # Case-insensitive match against available traces
            matched = None
            for avail in available_traces:
                if avail.lower() == name.lower():
                    matched = avail
                    break
            if matched is None:
                return ToolResult(
                    tool_call_id="",
                    content=(
                        f"Error: Trace '{name}' not found.\n"
                        f"Available: {', '.join(available_traces)}"
                    ),
                    is_error=True,
                )
            if matched.upper().startswith("I"):
                current_traces.append(matched)
            else:
                voltage_traces.append(matched)

        # ── Apply time range filter ─────────────────────────────
        if time_range and len(time_range) == 2:
            mask = (time_data >= time_range[0]) & (time_data <= time_range[1])
        else:
            mask = np.ones_like(time_data, dtype=bool)

        t_plot = time_data[mask]

        # ── Create plot ─────────────────────────────────────────
        fig, ax1 = plt.subplots(figsize=(10, 5))

        has_right_axis = bool(current_traces)

        # Plot voltages on left axis
        colors_v = plt.cm.tab10(np.linspace(0, 0.4, max(len(voltage_traces), 1)))
        for i, trace_name in enumerate(voltage_traces):
            trace = raw.get_trace(trace_name)
            data = np.real(np.asarray(trace.get_wave(step_idx)))[mask]
            ax1.plot(t_plot, data, label=trace_name, color=colors_v[i])

        if voltage_traces:
            ax1.set_ylabel("Voltage (V)", color="tab:blue")
            ax1.tick_params(axis="y", labelcolor="tab:blue")
        ax1.set_xlabel("Time (s)")

        # Plot currents on right axis (dashed)
        if current_traces:
            ax2 = ax1.twinx()
            colors_i = plt.cm.tab10(np.linspace(0.5, 0.9, len(current_traces)))
            for i, trace_name in enumerate(current_traces):
                trace = raw.get_trace(trace_name)
                data = np.real(np.asarray(trace.get_wave(step_idx)))[mask]
                ax2.plot(
                    t_plot, data, label=trace_name, color=colors_i[i], linestyle="--"
                )
            ax2.set_ylabel("Current (A)", color="tab:red")
            ax2.tick_params(axis="y", labelcolor="tab:red")

        # Title and legend
        if not title:
            title = f"Waveforms — {Path(raw_path_str).stem}"
        fig.suptitle(title)

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        if has_right_axis:
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
        elif voltage_traces:
            ax1.legend(loc="upper right")

        ax1.grid(True, alpha=0.3)
        fig.tight_layout()

        # ── Save plot ───────────────────────────────────────────
        results_dir = ensure_results_dir(project_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(raw_path_str).stem
        plot_filename = f"plot_{stem}_{timestamp}.png"
        plot_path = results_dir / plot_filename

        fig.savefig(str(plot_path), dpi=150, bbox_inches="tight")
        plt.close(fig)

        rel_path = plot_path.relative_to(project_dir)
        return ToolResult(
            tool_call_id="",
            content=(
                f"**Plot saved:** `{rel_path}`\n\n"
                f"Traces plotted: {', '.join(traces_requested)}"
            ),
        )
