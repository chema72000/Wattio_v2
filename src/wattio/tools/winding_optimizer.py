"""Tool for calculating litz wire strand optimization to reduce winding losses."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

# Standard litz strand diameters available (mm), sorted descending
STANDARD_DIAMETERS = [0.5, 0.4, 0.355, 0.315, 0.28, 0.25, 0.224, 0.2, 0.18,
                      0.16, 0.14, 0.125, 0.112, 0.1, 0.09, 0.08, 0.071,
                      0.063, 0.05]

# Minimum strand diameter (mm) — below this is very expensive
MIN_STRAND_DIAMETER = 0.05


def _strand_area(diameter_mm: float) -> float:
    """Cross-sectional area of a single strand in mm²."""
    return math.pi * (diameter_mm / 2) ** 2


def _calculate_new_strands(
    current_diameter: float,
    current_strands: int,
    new_diameter: float,
) -> int:
    """Calculate new number of strands to keep the same total copper area.

    Same copper area = same current density at the same current.
    n_new = n_old × (d_old / d_new)²
    """
    ratio_sq = (current_diameter / new_diameter) ** 2
    return math.ceil(current_strands * ratio_sq)


def _propose_diameters(
    current_diameter: float,
    frequency_khz: float,
) -> list[float]:
    """Propose candidate strand diameters based on frequency.

    For fsw > 99 kHz: go directly to 0.05 mm (optimal for HF).
    For fsw ≤ 99 kHz: propose stepwise reductions through standard sizes.
    """
    if frequency_khz > 99:
        # High frequency: jump directly to minimum
        return [MIN_STRAND_DIAMETER]

    # Lower frequency: propose decreasing steps from standard sizes
    candidates = [d for d in STANDARD_DIAMETERS if d < current_diameter]
    return candidates


class WindingOptimizerTool(BaseTool):
    """Calculate optimized litz wire strand diameter and number of strands."""

    name = "winding_optimizer"
    description = (
        "Calculate optimized litz wire parameters to reduce winding losses. "
        "Given the current strand diameter, number of strands, and switching frequency, "
        "proposes a smaller strand diameter and calculates the new number of strands "
        "to maintain the same current density (same total copper area). "
        "For frequencies above 99 kHz, proposes 0.05 mm directly. "
        "For lower frequencies, proposes stepwise reductions. "
        "Use this during design optimization (Step 5 Phase 3) when winding losses "
        "are too high relative to the target loss balance."
    )
    parameters = {
        "type": "object",
        "properties": {
            "current_diameter_mm": {
                "type": "number",
                "description": "Current litz strand diameter in mm (e.g., 0.2).",
            },
            "current_strands": {
                "type": "integer",
                "description": "Current number of strands per winding.",
            },
            "frequency_khz": {
                "type": "number",
                "description": "Switching frequency in kHz.",
            },
            "winding_name": {
                "type": "string",
                "description": "Name of the winding being optimized (e.g., 'primary', 'secondary').",
            },
        },
        "required": ["current_diameter_mm", "current_strands", "frequency_khz"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        current_d = kwargs.get("current_diameter_mm")
        current_n = kwargs.get("current_strands")
        freq = kwargs.get("frequency_khz")
        winding_name = kwargs.get("winding_name", "winding")

        if not current_d or current_d <= 0:
            return ToolResult(
                tool_call_id="",
                content="Error: current_diameter_mm must be a positive number.",
                is_error=True,
            )
        if not current_n or current_n <= 0:
            return ToolResult(
                tool_call_id="",
                content="Error: current_strands must be a positive integer.",
                is_error=True,
            )
        if not freq or freq <= 0:
            return ToolResult(
                tool_call_id="",
                content="Error: frequency_khz must be a positive number.",
                is_error=True,
            )

        current_area = _strand_area(current_d)
        total_copper_area = current_n * current_area

        proposals = _propose_diameters(current_d, freq)

        if not proposals:
            return ToolResult(
                tool_call_id="",
                content=(
                    f"Current strand diameter ({current_d} mm) is already at or below "
                    f"the minimum available size. No further reduction possible."
                ),
            )

        lines = [
            f"## Winding Optimization — {winding_name}",
            f"**Current configuration:**",
            f"- Strand diameter: {current_d} mm",
            f"- Number of strands: {current_n}",
            f"- Area per strand: {current_area:.6f} mm²",
            f"- Total copper area: {total_copper_area:.4f} mm²",
            f"- Switching frequency: {freq:.0f} kHz",
            "",
        ]

        if freq > 99:
            lines.append(
                f"**Frequency > 99 kHz** → go directly to {MIN_STRAND_DIAMETER} mm "
                f"strand diameter for optimal skin effect reduction."
            )
            lines.append("")

            new_d = MIN_STRAND_DIAMETER
            new_n = _calculate_new_strands(current_d, current_n, new_d)
            new_area = _strand_area(new_d)
            new_total = new_n * new_area

            lines.append(f"**Proposed configuration:**")
            lines.append(f"- Strand diameter: {new_d} mm")
            lines.append(f"- Number of strands: {new_n}")
            lines.append(f"- Area per strand: {new_area:.6f} mm²")
            lines.append(f"- Total copper area: {new_total:.4f} mm² "
                         f"(was {total_copper_area:.4f} mm²)")
            lines.append("")
            lines.append(
                f"**Calculation:** n_new = {current_n} × ({current_d} / {new_d})² "
                f"= {current_n} × {(current_d / new_d) ** 2:.1f} "
                f"= {new_n} strands (rounded up)"
            )
            lines.append("")
            lines.append(
                f"**⚠️ Note:** 0.05 mm strands are expensive. "
                f"This is the minimum available diameter."
            )
            lines.append("")
            lines.append(
                f"**Action:** Ask the user to change the {winding_name} to "
                f"{new_n} strands of {new_d} mm in Frenetic's Winding tab, "
                f"then report the new winding losses and window occupation %."
            )
        else:
            lines.append(
                f"**Frequency ≤ 99 kHz** → propose stepwise reductions. "
                f"Try each diameter and check skin/proximity losses until optimal."
            )
            lines.append("")
            lines.append(
                f"| Strand Ø (mm) | Strands needed | Area/strand (mm²) | "
                f"Total copper (mm²) | Calculation |"
            )
            lines.append(
                f"|---------------|---------------|-------------------|"
                f"-------------------|-------------|"
            )

            for new_d in proposals:
                new_n = _calculate_new_strands(current_d, current_n, new_d)
                new_area = _strand_area(new_d)
                new_total = new_n * new_area
                ratio_sq = (current_d / new_d) ** 2
                lines.append(
                    f"| {new_d} | {new_n} | {new_area:.6f} | "
                    f"{new_total:.4f} | "
                    f"{current_n} × ({current_d}/{new_d})² = "
                    f"{current_n} × {ratio_sq:.1f} |"
                )

            lines.append("")
            lines.append(
                f"**Action:** Start with the first reduction (one step smaller). "
                f"Ask the user to apply it in Frenetic and report: "
                f"winding losses, skin losses, proximity losses, and window occupation %. "
                f"If proximity losses are still high, the issue is interleaving, not strand diameter. "
                f"If skin losses decrease, continue to the next smaller diameter."
            )

        return ToolResult(
            tool_call_id="",
            content="\n".join(lines),
        )
