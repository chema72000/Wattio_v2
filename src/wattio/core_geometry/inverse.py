"""Inverse problem — derive core geometry that meets target Ae/Le/Ve.

Given a starting (catalog) core and one or more target effective
parameters, find the dimensions that come closest to the target while
keeping the geometry physically valid.

Default behaviour for PQ cores: vary only ``B`` (= H1/2, half pair
height) and ``D`` (= H2/2, half window height) — the footprint
dimensions ``A``, ``C``, ``F`` are usually fixed by manufacturing.
The user can override ``free`` to vary additional dimensions.

The result is an IEC 60205 estimate. Per ``custom-core-geometry.md``,
the user must verify in Frenetic before locking the design — Frenetic
can disagree with IEC by up to ~10% on Ae.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterable

from scipy.optimize import minimize

from .shapes import CoreGeometry, PQCoreDims, compute_pq_core


# Physical sanity defaults
_DEFAULT_FLANGE_MIN = 1.5    # mm — minimum back-wall thickness per half
_DEFAULT_WINDOW_MIN = 1.0    # mm — minimum window height per half
_REGULARISATION = 0.01       # weight pulling the solution toward the base dims


@dataclass(frozen=True)
class InverseResult:
    dims: PQCoreDims
    geometry: CoreGeometry
    targets: dict           # {"Ae": ..., "Le": ...}
    achieved: dict          # {"Ae": ..., "Le": ...}
    relative_error: dict    # {"Ae": +0.003, "Le": -0.012}  (signed, fraction)
    free_dims: tuple
    converged: bool         # optimizer converged
    success: bool           # all targets within ±1 %


def invert_pq(
    base: PQCoreDims,
    target_Ae: float | None = None,
    target_Le: float | None = None,
    target_Ve: float | None = None,
    free: Iterable[str] = ("B", "D"),
    bounds: dict | None = None,
    flange_min: float = _DEFAULT_FLANGE_MIN,
    window_min: float = _DEFAULT_WINDOW_MIN,
) -> InverseResult:
    """Find PQ dimensions that hit the requested Ae/Le/Ve targets.

    Parameters
    ----------
    base
        Starting catalog core — provides the fixed dimensions and the
        initial guess for the free ones.
    target_Ae, target_Le, target_Ve
        Targets in mm², mm, mm³. At least one must be supplied.
    free
        Tuple of dimension names that may be varied (default H1/2 and
        H2/2). Any subset of the PQCoreDims field names is accepted.
    bounds
        Optional ``{name: (lo, hi)}`` overrides. Names not in the dict
        fall back to sensible defaults (5 mm to 2× catalog).
    flange_min, window_min
        Lower limits for back-wall thickness and window height (each
        per-half). The optimiser is constrained to respect them when
        both ``B`` and ``D`` are free.
    """
    targets: dict[str, float] = {}
    if target_Ae is not None: targets["Ae"] = target_Ae
    if target_Le is not None: targets["Le"] = target_Le
    if target_Ve is not None: targets["Ve"] = target_Ve
    if not targets:
        raise ValueError("at least one of target_Ae, target_Le, target_Ve required")

    free = tuple(free)
    base_dict = {f.name: getattr(base, f.name) for f in fields(base)}
    for k in free:
        if k not in base_dict:
            raise ValueError(f"unknown free dim '{k}' for PQ; valid: {list(base_dict)}")

    default_bounds = {
        "A": (5.0, base_dict["A"] * 2),
        "B": (window_min + flange_min, base_dict["B"] * 2),
        "C": (5.0, base_dict["C"] * 2),
        "D": (window_min, base_dict["B"] * 2 - flange_min),
        "E": (base_dict["F"] + 1, base_dict["E"] * 2),
        "F": (1.0, base_dict["F"] * 2),
        "G": (1.0, base_dict["G"] * 2),
        "J": (0.5, base_dict["J"] * 2),
        "L": (0.5, base_dict["L"] * 2),
    }
    if bounds:
        default_bounds.update(bounds)
    bnds = [default_bounds[k] for k in free]

    def _dims_from(x):
        out = base_dict.copy()
        for k, v in zip(free, x):
            out[k] = v
        return out

    def _objective(x):
        try:
            g = compute_pq_core(PQCoreDims(**_dims_from(x)))
        except Exception:
            return 1e9
        r = 0.0
        for k, tgt in targets.items():
            actual = getattr(g, k)
            r += ((actual - tgt) / tgt) ** 2
        # gentle pull toward the base — only matters when targets are
        # under-determined (one target, multiple free dims)
        for k, v in zip(free, x):
            r += _REGULARISATION * ((v - base_dict[k]) / max(base_dict[k], 1.0)) ** 2
        return r

    constraints: list[dict] = []
    if "B" in free and "D" in free:
        iB, iD = free.index("B"), free.index("D")
        constraints.append({
            "type": "ineq",
            "fun": lambda x, iB=iB, iD=iD: x[iB] - x[iD] - flange_min,
        })

    x0 = [base_dict[k] for k in free]
    result = minimize(_objective, x0, bounds=bnds, constraints=constraints, method="SLSQP")

    final = PQCoreDims(**_dims_from(result.x))
    geom = compute_pq_core(final)
    achieved = {k: getattr(geom, k) for k in targets}
    rel_err = {k: (achieved[k] - targets[k]) / targets[k] for k in targets}
    success = all(abs(v) <= 0.01 for v in rel_err.values())

    return InverseResult(
        dims=final,
        geometry=geom,
        targets=targets,
        achieved=achieved,
        relative_error=rel_err,
        free_dims=free,
        converged=bool(result.success),
        success=success,
    )
