"""Tool for searching the power density reference database."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattio.models import ToolResult
from wattio.tools.base import BaseTool

EXCEL_FILENAME = "POWER DENSITY.xlsx"

# Column names from the Excel file
COL_SOURCE = "SOURCE"
COL_REFERENCE = "REFERENCE"
COL_MAG_TYPE = "MAGNETIC TYPE"
COL_TOPOLOGY = "TOPOLOGY"
COL_POWER = "POWER RATIO (kw) O INDUCTANCE"
COL_FREQUENCY = "SW FREQUENCY"
COL_RATIO = "RATIO"
COL_COOLING = "COOLING"
COL_CORE = "CORE"
COL_STACKS = "stacks"
COL_TECHNOLOGY = "TECHNOLOGY "  # trailing space in the Excel header
COL_VOL_EFF = "Volumen effective(l)"
COL_POWER_DENSITY = "POWER DENSITY (kw/l)"
COL_EFFICIENCY = "efficiency "  # trailing space in the Excel header
COL_TOTAL_LOSSES = "total magnetic losses"
COL_WINDING_LOSSES = "winding"
COL_CORE_LOSSES = "core"
COL_SIMULATOR = "simulator"


def _find_excel(project_dir: Path) -> Path:
    """Locate the power density Excel file."""
    for candidate in [
        project_dir / EXCEL_FILENAME,
        project_dir.parent / EXCEL_FILENAME,
        Path(__file__).parent.parent.parent.parent / EXCEL_FILENAME,
    ]:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Cannot find '{EXCEL_FILENAME}'. Place it in the project directory."
    )


def _load_and_search(
    project_dir: Path,
    topology: str,
    magnetic_type: str,
) -> list[dict]:
    """Load Excel and find all matching designs."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required. Install with: uv add openpyxl")

    excel_path = _find_excel(project_dir)
    wb = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
    ws = wb.active

    # Parse header
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    col = {name: idx for idx, name in enumerate(headers) if name is not None}

    results: list[dict] = []
    topology_lower = topology.lower()
    mag_type_lower = magnetic_type.lower()

    for row in ws.iter_rows(min_row=2, values_only=True):
        row_topology = str(row[col.get(COL_TOPOLOGY, 3)] or "").lower()
        row_mag_type = str(row[col.get(COL_MAG_TYPE, 2)] or "").lower()

        if topology_lower not in row_topology:
            continue
        if mag_type_lower not in row_mag_type:
            continue

        power_kw = row[col.get(COL_POWER, 4)] or 0
        freq_khz = row[col.get(COL_FREQUENCY, 5)] or 0
        power_density = row[col.get(COL_POWER_DENSITY, 12)] or 0

        results.append({
            "source": row[col.get(COL_SOURCE, 0)] or "",
            "reference": row[col.get(COL_REFERENCE, 1)] or "",
            "topology": row[col.get(COL_TOPOLOGY, 3)] or "",
            "power_kw": round(float(power_kw), 2),
            "frequency_khz": round(float(freq_khz), 1),
            "turns_ratio": row[col.get(COL_RATIO, 6)] or "",
            "cooling": row[col.get(COL_COOLING, 7)] or "",
            "core": row[col.get(COL_CORE, 8)] or "",
            "stacks": row[col.get(COL_STACKS, 9)] or 1,
            "technology": str(row[col.get(COL_TECHNOLOGY, 10)] or "").strip(),
            "vol_effective_l": round(float(row[col.get(COL_VOL_EFF, 11)] or 0), 6),
            "power_density_kw_l": round(float(power_density), 1),
            "efficiency_pct": row[col.get(COL_EFFICIENCY, 15)] or "",
            "total_losses_w": row[col.get(COL_TOTAL_LOSSES, 16)] or "",
            "winding_losses_w": row[col.get(COL_WINDING_LOSSES, 17)] or "",
            "core_losses_w": row[col.get(COL_CORE_LOSSES, 18)] or "",
            "simulator_link": row[col.get(COL_SIMULATOR, 19)] or "",
        })

    wb.close()

    # Sort by power density descending (best first)
    results.sort(key=lambda r: r["power_density_kw_l"], reverse=True)
    return results


class PowerDensitySearchTool(BaseTool):
    """Search the power density reference database for similar designs."""

    name = "power_density_search"
    description = (
        "Search the power density reference database (Excel) to find real-world designs "
        "with similar topology and magnetic type. Returns power density benchmarks from "
        "academic papers and application notes, including core used, frequency, cooling, "
        "losses breakdown, and efficiency. Use this in Step 4 to give the engineer a "
        "reference point for achievable power density before starting viability screening."
    )
    parameters = {
        "type": "object",
        "properties": {
            "topology": {
                "type": "string",
                "description": "Converter topology to search for (e.g., 'PSFB', 'LLC', 'DAB').",
            },
            "magnetic_type": {
                "type": "string",
                "enum": ["transformer", "inductor"],
                "description": "Type of magnetic component.",
            },
        },
        "required": ["topology", "magnetic_type"],
    }

    async def execute(self, project_dir: Path, **kwargs: Any) -> ToolResult:
        topology = kwargs.get("topology", "")
        magnetic_type = kwargs.get("magnetic_type", "transformer")

        if not topology:
            return ToolResult(
                tool_call_id="",
                content="Error: topology is required.",
                is_error=True,
            )

        try:
            results = _load_and_search(
                project_dir=project_dir,
                topology=topology,
                magnetic_type=magnetic_type,
            )
        except FileNotFoundError as e:
            return ToolResult(tool_call_id="", content=f"Error: {e}", is_error=True)
        except Exception as e:
            return ToolResult(
                tool_call_id="", content=f"Error searching database: {e}", is_error=True
            )

        if not results:
            return ToolResult(
                tool_call_id="",
                content=(
                    f"No reference designs found for topology '{topology}' "
                    f"with magnetic type '{magnetic_type}'. "
                    f"The database may not have entries for this combination yet."
                ),
            )

        # Format results
        lines = [
            f"## Power Density Reference Designs",
            f"**Search:** {magnetic_type} designs for {topology} topology",
            f"**Found:** {len(results)} reference design(s)",
            "",
        ]

        for i, r in enumerate(results, 1):
            power_w = r["power_kw"] * 1000
            lines.append(
                f"### {i}. {r['source']}: {r['topology']} {power_w:.0f} W @ "
                f"{r['frequency_khz']:.0f} kHz"
            )
            lines.append("")
            lines.append(f"| Parameter | Value |")
            lines.append(f"|-----------|-------|")
            lines.append(f"| Source | {r['source']} |")
            lines.append(f"| Reference | {r['reference']} |")
            lines.append(f"| Power | {power_w:.0f} W ({r['power_kw']} kW) |")
            lines.append(f"| Frequency | {r['frequency_khz']:.0f} kHz |")
            lines.append(f"| Turns ratio | {r['turns_ratio']} |")
            lines.append(f"| Cooling | {r['cooling']} |")
            lines.append(f"| Core | {r['core']} (×{r['stacks']}) |")
            lines.append(f"| Technology | {r['technology']} |")
            lines.append(f"| Effective volume | {r['vol_effective_l']} L |")
            lines.append(f"| **Power density** | **{r['power_density_kw_l']:.1f} kW/L** |")
            lines.append(f"| Efficiency | {r['efficiency_pct']}% |")
            lines.append(f"| Total magnetic losses | {r['total_losses_w']} W |")
            lines.append(f"| Winding losses | {r['winding_losses_w']} W |")
            lines.append(f"| Core losses | {r['core_losses_w']} W |")
            if r["simulator_link"]:
                lines.append(f"| Frenetic simulation | {r['simulator_link']} |")
            lines.append("")

        lines.append(
            "**How to use:** Compare your design's target power and frequency with these references. "
            "The power density (kW/L) gives you a benchmark for what's achievable with similar "
            "topologies. If a reference design uses a similar power level and frequency, its core "
            "choice and loss distribution can inform your own design targets."
        )

        return ToolResult(
            tool_call_id="",
            content="\n".join(lines),
        )
