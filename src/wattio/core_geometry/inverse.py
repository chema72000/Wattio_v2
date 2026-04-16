"""Inverse problem — derive core geometry that meets target Ae/Le/Ve.

Given a starting (catalog) core and one or more target effective
parameters, find the dimensions that come closest to the target while
keeping the geometry physically valid.

Default behaviour for all shapes: vary only ``B`` (= H1/2, half pair
height) and ``D`` (= H2/2, half window height) — the footprint
dimensions are usually fixed by manufacturing. The user can override
``free`` to vary additional dimensions.

The result is an IEC 60205 estimate. Per ``custom-core-geometry.md``,
the user must verify in Frenetic before locking the design — Frenetic
can disagree with IEC by up to ~10% on Ae.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Iterable

from scipy.optimize import minimize

from .shapes import (
    CoreGeometry,
    ECoreDims,
    ETDCoreDims,
    PQCoreDims,
    RMCoreDims,
    EFDCoreDims,
    compute_e_core,
    compute_etd_core,
    compute_pq_core,
    compute_rm_core,
    compute_efd_core,
)


# Physical sanity defaults (per half-core, mm)
_DEFAULT_FLANGE_MIN = 1.5
_DEFAULT_WINDOW_MIN = 1.0
_REGULARISATION = 0.01


@dataclass(frozen=True)
class InverseResult:
    dims: object            # shape-specific dataclass instance
    geometry: CoreGeometry
    targets: dict           # {"Ae": ..., "Le": ...}
    achieved: dict          # {"Ae": ..., "Le": ...}
    relative_error: dict    # signed fraction per target
    free_dims: tuple
    converged: bool
    success: bool           # all targets within ±1 %


# Shape registry: dims class + compute function + default-bounds builder.
def _default_bounds_for(dims_class, base_dict):
    """Per-shape sensible bounds (5 mm to 2× catalog, with shape quirks)."""
    name = dims_class.__name__
    common = {
        "A": (5.0, base_dict["A"] * 2),
        "B": (_DEFAULT_WINDOW_MIN + _DEFAULT_FLANGE_MIN, base_dict["B"] * 2),
        "C": (5.0, base_dict["C"] * 2),
        "D": (_DEFAULT_WINDOW_MIN, base_dict["B"] * 2 - _DEFAULT_FLANGE_MIN),
    }
    if name == "ECoreDims":
        common.update({
            "E": (base_dict["F"] + 1, base_dict["E"] * 2),
            "F": (1.0, base_dict["F"] * 2),
        })
    elif name == "ETDCoreDims":
        common.update({
            "E": (base_dict["F"] + 1, base_dict["E"] * 2),
            "F": (1.0, base_dict["F"] * 2),
        })
    elif name == "PQCoreDims":
        common.update({
            "E": (base_dict["F"] + 1, base_dict["E"] * 2),
            "F": (1.0, base_dict["F"] * 2),
            "G": (1.0, base_dict["G"] * 2),
            "J": (0.5, base_dict["J"] * 2),
            "L": (0.5, base_dict["L"] * 2),
        })
    elif name == "RMCoreDims":
        common.update({
            "E": (base_dict["F"] + 1, base_dict["E"] * 2),
            "F": (1.0, base_dict["F"] * 2),
            "G": (1.0, base_dict["G"] * 2),
            "H": (0.0, max(base_dict["H"], base_dict["F"] - 1)),
            "J": (1.0, base_dict["J"] * 2),
        })
    elif name == "EFDCoreDims":
        common.update({
            "E": (base_dict["F"] + 1, base_dict["E"] * 2),
            "F":  (1.0, base_dict["F"] * 2),
            "F2": (1.0, base_dict["F2"] * 2),
            "K":  (-base_dict["F"], base_dict["F"]),    # K may be negative
            "q":  (0.0, max(base_dict["q"] * 2, 1.0)),
        })
    return common


_SHAPE_INVERSE = {
    "E":   (ECoreDims,   compute_e_core),
    "ETD": (ETDCoreDims, compute_etd_core),
    "EER": (ETDCoreDims, compute_etd_core),
    "PQ":  (PQCoreDims,  compute_pq_core),
    "RM":  (RMCoreDims,  compute_rm_core),
    "EFD": (EFDCoreDims, compute_efd_core),
}


def _invert(
    dims_class,
    compute_fn,
    base,
    target_Ae: float | None = None,
    target_Le: float | None = None,
    target_Ve: float | None = None,
    free: Iterable[str] = ("B", "D"),
    bounds: dict | None = None,
    flange_min: float = _DEFAULT_FLANGE_MIN,
    window_min: float = _DEFAULT_WINDOW_MIN,
) -> InverseResult:
    targets: dict[str, float] = {}
    if target_Ae is not None: targets["Ae"] = target_Ae
    if target_Le is not None: targets["Le"] = target_Le
    if target_Ve is not None: targets["Ve"] = target_Ve
    if not targets:
        raise ValueError("at least one of target_Ae, target_Le, target_Ve required")

    free = tuple(free)
    if not isinstance(base, dims_class):
        raise TypeError(
            f"base must be {dims_class.__name__}, got {type(base).__name__}"
        )

    base_dict = {f.name: getattr(base, f.name) for f in fields(base)}
    for k in free:
        if k not in base_dict:
            raise ValueError(
                f"unknown free dim '{k}' for {dims_class.__name__}; "
                f"valid: {list(base_dict)}"
            )

    default_bounds = _default_bounds_for(dims_class, base_dict)
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
            g = compute_fn(dims_class(**_dims_from(x)))
        except Exception:
            return 1e9
        r = 0.0
        for k, tgt in targets.items():
            actual = getattr(g, k)
            r += ((actual - tgt) / tgt) ** 2
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
    result = minimize(
        _objective, x0,
        bounds=bnds, constraints=constraints, method="SLSQP",
    )

    final = dims_class(**_dims_from(result.x))
    geom = compute_fn(final)
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


# ---------------------------------------------------------------------------
# Per-shape thin wrappers
# ---------------------------------------------------------------------------

def invert_e_core(base: ECoreDims, **kwargs) -> InverseResult:
    return _invert(ECoreDims, compute_e_core, base, **kwargs)


def invert_etd_core(base: ETDCoreDims, **kwargs) -> InverseResult:
    return _invert(ETDCoreDims, compute_etd_core, base, **kwargs)


def invert_pq(base: PQCoreDims, **kwargs) -> InverseResult:
    return _invert(PQCoreDims, compute_pq_core, base, **kwargs)


def invert_rm_core(base: RMCoreDims, **kwargs) -> InverseResult:
    return _invert(RMCoreDims, compute_rm_core, base, **kwargs)


def invert_efd_core(base: EFDCoreDims, **kwargs) -> InverseResult:
    return _invert(EFDCoreDims, compute_efd_core, base, **kwargs)


def invert_core(shape_name: str, base, **kwargs) -> InverseResult:
    """Generic dispatcher — picks the right inverse for the named shape."""
    key = shape_name.upper()
    if key not in _SHAPE_INVERSE:
        raise ValueError(
            f"unknown shape '{shape_name}'; valid: {list(_SHAPE_INVERSE)}"
        )
    dims_class, compute_fn = _SHAPE_INVERSE[key]
    return _invert(dims_class, compute_fn, base, **kwargs)
