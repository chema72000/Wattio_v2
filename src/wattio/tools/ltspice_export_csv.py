"""LTspice CSV export tool — export waveforms to Frenetic-compatible CSV."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool


class LTspiceExportCsvTool(BaseTool):
    name = "ltspice_export_csv"
    description = (
        "Export LTspice simulation waveforms (current and voltage) to a CSV file "
        "compatible with Frenetic (frenetic.ai) magnetic design tool. "
        "Exports current/voltage pairs per winding or inductor.\n\n"
        "Two modes:\n"
        "- **components**: simple list like [\"L1\"] — works when V(L1) exists "
        "(e.g. transformer windings).\n"
        "- **signals**: explicit trace mapping — required when V(component) is not "
        "available (e.g. inductors in a buck/boost). Each entry specifies the "
        "current trace and one or two voltage node traces. When two voltage nodes "
        "are given the exported voltage is V(positive) − V(negative).\n\n"
        "Use `ltspice_plot` first to identify available trace names if unsure."
    )
    parameters = {
        "type": "object",
        "properties": {
            "raw_path": {
                "type": "string",
                "description": "Path to the .raw file (relative to project directory).",
            },
            "components": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    'Component references for simple export, e.g. ["L1"] or ["L1", "L2"]. '
                    "For each component, I(component) and V(component) are exported. "
                    "Use this when V(component) exists (typically transformer windings). "
                    "Mutually exclusive with signals."
                ),
            },
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "current": {
                            "type": "string",
                            "description": 'Current trace name, e.g. "I(L1)".',
                        },
                        "voltage_positive": {
                            "type": "string",
                            "description": (
                                "Voltage node trace for the positive terminal, "
                                'e.g. "V(sw)". If voltage_negative is omitted, '
                                "this is used directly as the voltage."
                            ),
                        },
                        "voltage_negative": {
                            "type": "string",
                            "description": (
                                "Optional voltage node trace for the negative terminal, "
                                'e.g. "V(out)". When provided, the exported voltage '
                                "is V(positive) − V(negative)."
                            ),
                        },
                    },
                    "required": ["current", "voltage_positive"],
                },
                "description": (
                    "Explicit trace definitions for each winding/inductor. "
                    "Use this when V(component) is not available — e.g. for inductors "
                    "in buck/boost converters where the voltage must be computed from "
                    "node voltages. Mutually exclusive with components."
                ),
            },
            "time_range": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Optional [start, end] time range in seconds to crop the export.",
            },
            "step": {
                "type": "integer",
                "description": "For stepped sims, which step to export (0-indexed, default 0).",
            },
        },
        "required": ["raw_path"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        from wattio.tools.ltspice_helpers import ensure_results_dir

        raw_path_str = kwargs.get("raw_path", "")
        components = kwargs.get("components")
        signals = kwargs.get("signals")
        time_range = kwargs.get("time_range")
        step_idx = kwargs.get("step", 0)

        if not raw_path_str:
            return ToolResult(
                tool_call_id="",
                content="Error: raw_path is required.",
                is_error=True,
            )

        if not components and not signals:
            return ToolResult(
                tool_call_id="",
                content="Error: either components or signals is required.",
                is_error=True,
            )

        if components and signals:
            return ToolResult(
                tool_call_id="",
                content="Error: components and signals are mutually exclusive — use one or the other.",
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
            import numpy as np
        except ImportError:
            return ToolResult(
                tool_call_id="",
                content=(
                    "Error: numpy is not installed. "
                    "Install it with: pip install numpy"
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
        available_lower = {t.lower(): t for t in available_traces}

        time_trace = raw.get_trace("time")
        time_data = np.real(np.asarray(time_trace.get_wave(step_idx)))

        def _find_trace(name: str) -> str | None:
            """Case-insensitive trace lookup."""
            return available_lower.get(name.lower())

        def _get_wave(trace_name: str) -> Any:
            return np.real(np.asarray(raw.get_trace(trace_name).get_wave(step_idx)))

        # ── Resolve trace pairs ─────────────────────────────────
        # Each entry becomes (current_data, voltage_data)
        pair_data: list[tuple[Any, Any]] = []
        labels: list[str] = []

        if components:
            for comp in components:
                i_match = _find_trace(f"I({comp})")
                v_match = _find_trace(f"V({comp})")

                if i_match is None:
                    return ToolResult(
                        tool_call_id="",
                        content=(
                            f"Error: Current trace I({comp}) not found.\n"
                            f"Available: {', '.join(available_traces)}"
                        ),
                        is_error=True,
                    )
                if v_match is None:
                    # Build a helpful suggestion
                    node_traces = [t for t in available_traces if t.upper().startswith("V(")]
                    return ToolResult(
                        tool_call_id="",
                        content=(
                            f"Error: Voltage trace V({comp}) not found.\n"
                            f"Available node voltages: {', '.join(node_traces)}\n\n"
                            f"Hint: For inductors, use the **signals** parameter instead "
                            f"to specify the voltage across the component from node "
                            f"voltages. Example:\n"
                            f'  signals: [{{"current": "I({comp})", '
                            f'"voltage_positive": "V(node+)", '
                            f'"voltage_negative": "V(node-)"}}]'
                        ),
                        is_error=True,
                    )

                pair_data.append((_get_wave(i_match), _get_wave(v_match)))
                labels.append(comp)

        else:  # signals
            for idx, sig in enumerate(signals):
                i_name = sig.get("current", "")
                v_pos_name = sig.get("voltage_positive", "")
                v_neg_name = sig.get("voltage_negative")

                if not i_name or not v_pos_name:
                    return ToolResult(
                        tool_call_id="",
                        content=f"Error: signal #{idx} must have 'current' and 'voltage_positive'.",
                        is_error=True,
                    )

                i_match = _find_trace(i_name)
                if i_match is None:
                    return ToolResult(
                        tool_call_id="",
                        content=(
                            f"Error: Trace '{i_name}' not found.\n"
                            f"Available: {', '.join(available_traces)}"
                        ),
                        is_error=True,
                    )

                v_pos_match = _find_trace(v_pos_name)
                if v_pos_match is None:
                    return ToolResult(
                        tool_call_id="",
                        content=(
                            f"Error: Trace '{v_pos_name}' not found.\n"
                            f"Available: {', '.join(available_traces)}"
                        ),
                        is_error=True,
                    )

                v_data = _get_wave(v_pos_match)

                if v_neg_name:
                    v_neg_match = _find_trace(v_neg_name)
                    if v_neg_match is None:
                        return ToolResult(
                            tool_call_id="",
                            content=(
                                f"Error: Trace '{v_neg_name}' not found.\n"
                                f"Available: {', '.join(available_traces)}"
                            ),
                            is_error=True,
                        )
                    v_data = v_data - _get_wave(v_neg_match)

                pair_data.append((_get_wave(i_match), v_data))
                labels.append(i_name)

        # ── Apply time range filter ─────────────────────────────
        if time_range and len(time_range) == 2:
            mask = (time_data >= time_range[0]) & (time_data <= time_range[1])
        else:
            mask = np.ones_like(time_data, dtype=bool)

        time_data = time_data[mask]
        pair_data = [(i[mask], v[mask]) for i, v in pair_data]

        # ── Build CSV ───────────────────────────────────────────
        header_parts = ["time"]
        for idx in range(len(pair_data)):
            header_parts.append(f"current_{idx}")
            header_parts.append(f"voltage_{idx}")
        header = ",".join(header_parts)

        # Stack columns: time, current_0, voltage_0, current_1, voltage_1, ...
        data_cols = [time_data]
        for i_data, v_data in pair_data:
            data_cols.append(i_data)
            data_cols.append(v_data)
        data = np.column_stack(data_cols)

        # ── Write file ──────────────────────────────────────────
        results_dir = ensure_results_dir(project_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = Path(raw_path_str).stem
        csv_filename = f"frenetic_{stem}_{timestamp}.csv"
        csv_path = results_dir / csv_filename

        lines = [header]
        for row in data:
            parts = []
            for j, val in enumerate(row):
                if j == 0:
                    # Time column — always scientific notation
                    parts.append(f"{val:.8e}")
                else:
                    # Data columns — use repr-style (scientific for large/small,
                    # decimal for mid-range, matching the example file)
                    parts.append(str(val))
            lines.append(",".join(parts))

        csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        rel_path = csv_path.relative_to(project_dir)
        label_str = ", ".join(labels)
        return ToolResult(
            tool_call_id="",
            content=(
                f"**CSV exported:** `{rel_path}`\n\n"
                f"Signals: {label_str}\n"
                f"Rows: {len(time_data)}\n"
                f"Format: Frenetic-compatible (time, current/voltage pairs)"
            ),
        )
