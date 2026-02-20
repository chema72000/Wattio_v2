"""Shared helpers for LTspice tools.

NOT a BaseTool subclass — will not be auto-discovered by the registry.
"""

from __future__ import annotations

import math
import os
import platform
import re
import shutil
from pathlib import Path

# ── Platform & exe discovery ────────────────────────────────────────


def check_platform() -> str | None:
    """Return an error message if not on Windows, else None."""
    if platform.system() != "Windows":
        return (
            "LTspice simulation tools require Windows. "
            "LTspice does not support command-line batch mode on macOS."
        )
    return None


def find_ltspice_exe() -> Path | None:
    """Find LTspice executable on Windows.

    Checks PATH first, then standard install locations.
    Returns None if not found.
    """
    # Check PATH
    which = shutil.which("XVIIx64.exe") or shutil.which("ltspice.exe")
    if which:
        return Path(which)

    # Standard install locations
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))
        / "ADI"
        / "LTspice"
        / "LTspice.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "ADI"
        / "LTspice"
        / "LTspice.exe",
        Path("C:\\Program Files\\LTC\\LTspiceXVII\\XVIIx64.exe"),
        Path("C:\\Program Files (x86)\\LTC\\LTspiceXVII\\XVIIx86.exe"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


# ── Path validation ─────────────────────────────────────────────────


def validate_schematic_path(project_dir: Path, schematic_path: str) -> Path | str:
    """Resolve and validate a schematic path.

    Returns the resolved Path on success, or an error string on failure.
    """
    full_path = (project_dir / schematic_path).resolve()

    # Security: don't allow access outside project dir
    if not str(full_path).startswith(str(project_dir.resolve())):
        return "Error: Cannot access files outside the project directory."

    if not full_path.is_file():
        return f"Error: Schematic file not found: {schematic_path}"

    if full_path.suffix.lower() != ".asc":
        return "Error: File must be an LTspice schematic (.asc)."

    return full_path


# ── Directory helpers ───────────────────────────────────────────────


def ensure_results_dir(project_dir: Path) -> Path:
    """Create and return wattio/results/ directory."""
    results_dir = project_dir / "wattio" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return results_dir


def ensure_sim_workdir(project_dir: Path) -> Path:
    """Create and return wattio/sim_work/ directory."""
    sim_dir = project_dir / "wattio" / "sim_work"
    sim_dir.mkdir(parents=True, exist_ok=True)
    return sim_dir


# ── Working copy ────────────────────────────────────────────────────


def create_working_copy(
    original: Path, work_dir: Path, suffix: str = ""
) -> Path:
    """Copy an .asc file (+ supporting .asy/.sub/.lib) to the work directory.

    Args:
        original: Path to the original .asc file.
        work_dir: Destination directory (e.g. wattio/sim_work/).
        suffix: Optional suffix before extension (e.g. "_sweep_003").

    Returns:
        Path to the copied .asc file in work_dir.
    """
    stem = original.stem + suffix
    dest = work_dir / (stem + ".asc")
    shutil.copy2(original, dest)

    # Also copy supporting files from the same directory
    for ext in (".asy", ".sub", ".lib", ".inc"):
        for support_file in original.parent.glob(f"*{ext}"):
            support_dest = work_dir / support_file.name
            if not support_dest.exists():
                shutil.copy2(support_file, support_dest)

    return dest


# ── .asc parameter parsing ─────────────────────────────────────────


def extract_parameters_from_asc(content: str) -> dict[str, str]:
    """Parse .param directives from LTspice .asc TEXT elements.

    Handles formats like:
        .param load_resistance 10
        .param fsw=100k
        .param Vin 48 Vout=12
        .param Cin {100n}

    Returns dict of name → value.
    """
    params: dict[str, str] = {}

    # Find all .param lines (may appear inside TEXT blocks or as directives)
    for line in content.splitlines():
        stripped = line.strip()
        # In .asc files, SPICE directives inside TEXT elements have "!" prefix
        # Handle both "!.param" and ".param"
        lower = stripped.lower()
        if lower.startswith("!.param"):
            rest_start = 7
        elif lower.startswith(".param"):
            rest_start = 6
        else:
            # Also check for ".param" anywhere in the line (TEXT element prefix)
            idx = lower.find(".param")
            if idx == -1:
                idx = lower.find("!.param")
                if idx == -1:
                    continue
                rest_start = idx + 7
            else:
                # Check for "!" just before ".param"
                if idx > 0 and stripped[idx - 1] == "!":
                    rest_start = idx + 7
                else:
                    rest_start = idx + 6

        rest = stripped[rest_start:].strip()
        if not rest:
            continue

        # Parse name=value or name value pairs
        # Regex: word followed by optional = then value (possibly in braces)
        pattern = r"(\w+)\s*=?\s*\{?([^}\s,]+)\}?"
        for match in re.finditer(pattern, rest):
            name, value = match.group(1), match.group(2)
            params[name] = value

    return params


# ── Engineering notation ────────────────────────────────────────────

_ENG_PREFIXES = [
    (1e-15, "f"),
    (1e-12, "p"),
    (1e-9, "n"),
    (1e-6, "\u00b5"),  # µ
    (1e-3, "m"),
    (1e0, ""),
    (1e3, "k"),
    (1e6, "M"),
    (1e9, "G"),
]


def eng(value: float, unit: str = "", digits: int = 3) -> str:
    """Format a number in engineering notation.

    Examples:
        eng(560e-6, "H") → "560µH"
        eng(0.0023, "A") → "2.3mA"
        eng(100000, "Hz") → "100kHz"
    """
    if value == 0:
        return f"0{unit}"

    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    for threshold, prefix in _ENG_PREFIXES:
        if abs_val < threshold * 1000:
            scaled = value / threshold
            # Format with appropriate precision
            if abs(scaled) >= 100:
                formatted = f"{scaled:.{max(0, digits - 3)}f}"
            elif abs(scaled) >= 10:
                formatted = f"{scaled:.{max(0, digits - 2)}f}"
            else:
                formatted = f"{scaled:.{max(0, digits - 1)}f}"
            # Strip trailing zeros after decimal point
            if "." in formatted:
                formatted = formatted.rstrip("0").rstrip(".")
            return f"{formatted}{prefix}{unit}"

    # Fallback for very large numbers
    return f"{sign}{abs_val:.{digits}g}{unit}"


# ── Measurement helpers ─────────────────────────────────────────────


def compute_measurements(
    time_array: list[float] | object,
    data_array: list[float] | object,
    measure_start: float | None = None,
) -> dict[str, float]:
    """Compute min/max/avg/rms/peak_to_peak/final for a waveform.

    Args:
        time_array: Time values (numpy array or list).
        data_array: Signal values (numpy array or list).
        measure_start: Start time for measurement window.
                       Default: last 20% of simulation.

    Returns:
        Dict with keys: min, max, avg, rms, peak_to_peak, final.
    """
    import numpy as np

    t = np.asarray(time_array, dtype=float)
    d = np.asarray(data_array, dtype=float)

    if measure_start is None:
        measure_start = t[-1] * 0.8

    mask = t >= measure_start
    if not np.any(mask):
        mask = np.ones_like(t, dtype=bool)  # fallback: use all data

    d_window = d[mask]

    return {
        "min": float(np.min(d_window)),
        "max": float(np.max(d_window)),
        "avg": float(np.mean(d_window)),
        "rms": float(np.sqrt(np.mean(d_window**2))),
        "peak_to_peak": float(np.max(d_window) - np.min(d_window)),
        "final": float(d_window[-1]),
    }
