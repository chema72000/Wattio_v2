"""IEC 60205:2016 forward calculation of effective core parameters.

For a closed magnetic circuit formed by a pair of cores we model the flux
path as five series segments of length ``l_i`` and cross-section ``A_i``.
The effective parameters follow:

    C1 = Σ l_i / A_i              (mm^-1)
    C2 = Σ l_i / A_i^2            (mm^-3)
    Le = C1^2 / C2                (mm)
    Ae = C1 / C2                  (mm^2)
    Ve = C1^3 / C2^2              (mm^3)
    Amin = min(physical cross-sections)

Dimension symbols follow EN 62317-13 (and the OpenMagnetics MAS database):
``A`` (footprint long axis), ``B`` (window+flange height per half),
``C`` (footprint depth/short axis), ``D`` (window height per half),
``E`` (window outer dim / leg-to-leg dim), ``F`` (centre limb dim).
PQ adds ``G/J/L`` (centre-limb top-flat geometry); RM adds ``G`` (axial
across-flat), ``H`` (centre-pole bore), ``J`` (smaller across-flat); EFD
adds ``F2`` (centre-limb short-axis), ``K`` (centre chamfer offset), ``q``
(centre chamfer side).

All inputs are in mm.

Mapping table (Ferroxcube datasheet → EN 62317-13 / IEC 60205):

    PQ:   A→A, B→C(depth), C→G(across-flats), D2→E, D3→F,
          H1/2→B, H2/2→D
    E:    A→A, B→E(window), C→F(center leg), D→B, E→D, F→C(depth)
          (Ferroxcube convention; some 2016 sheets relabel)
    ETD:  A→A, B→C, D2→E, D3→F, E→B, F→D
    RM:   A→J, G→A, B→B, C→C, D→D, D2→E, D3→F, D4→H, E→G
    EFD:  follows EL conventions: A→A, B→B, C→C, D→D, E→E, F→F,
          F2→F2, K→K, q→q

The formulas implemented here are the "full pair" IEC 60205 forms,
i.e. l_1 = 2D etc., and areas where two parallel paths exist (two outer
legs or top+bottom back walls) are summed.  For PQ we follow the
IEC 62317-13 / OpenMagnetics MKF formulation directly: l_2 and A_2 come
from the closed-form integral over the chamfered window (no numerical
quadrature needed), and the f, K shape factors capture the flux
re-weighting in the chamfered region.

Honest accuracy:
  - E, ETD, RM, EFD: ≤ 2 % vs Ferroxcube 2016 published values when
    using midpoint-of-(nom,max) dimensions.
  - PQ:  ≤ 0.5 % vs the IEC 63093-13:2019 Table 3 published values
    when using midpoint-of-(MIN,MAX) dimensions from Table 1.

DEVIATION FROM FERROXCUBE PQ DATASHEETS: Ferroxcube's published
Ae/Le/Ve for PQ32/30, PQ35/35 and PQ40/40 differ from the IEC
63093-13 standard by 6-9 %.  TDK Electronics' datasheets for the same
cores match the IEC standard to ≤ 1 %.  Since IEC 63093-13 is the
authoritative public reference and our purely-geometric calculation
matches it to ≤ 0.5 %, we use IEC as the truth source.  Ferroxcube's
larger numbers cannot be reproduced by any closed-form extension of
the IEC §5.12 integral without breaking smaller cores or violating
the standard — see _build_core_db.py PQ block for full notes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


# ---------------------------------------------------------------------------
# public result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CoreGeometry:
    Ae: float
    Le: float
    Ve: float
    C1: float
    C2: float
    Amin: float


def _finalize(C1: float, C2: float, areas: Iterable[float]) -> CoreGeometry:
    Le = C1 ** 2 / C2
    Ae = C1 / C2
    Ve = C1 ** 3 / C2 ** 2
    return CoreGeometry(
        Ae=Ae, Le=Le, Ve=Ve,
        C1=C1, C2=C2,
        Amin=min(a for a in areas if a > 0),
    )


def _five_segment(segs):
    """Helper: compute (C1, C2) for a list of (length, area) pairs."""
    C1 = sum(L / A for L, A in segs)
    C2 = sum(L / A ** 2 for L, A in segs)
    return C1, C2


# ---------------------------------------------------------------------------
# E-cores  (IEC 60205 §5.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ECoreDims:
    """Dimensions for a pair of rectangular E-cores (EN 62317-13)."""

    A: float    # footprint long axis
    B: float    # window+flange height per half-core
    C: float    # depth (short axis)
    D: float    # window height per half-core
    E: float    # outer-leg-to-outer-leg distance (window outer dim)
    F: float    # centre-leg width (along long axis)


def compute_e_core(d: ECoreDims) -> CoreGeometry:
    pi = math.pi
    h = d.B - d.D                           # one flange thickness
    p = (d.A - d.E) / 2                     # one outer-leg width
    s = d.F / 2                             # half centre-leg width
    q = d.C                                 # depth

    # Full-pair lengths (loop traverses each segment as a top+bottom pair)
    L1 = 2 * d.D                            # outer leg, both halves
    L2 = (d.E - d.F)                        # back-wall lateral path × 2 (top+bot)
    L3 = 2 * d.D                            # centre limb, both halves
    L4 = pi / 4 * (p + h)                   # 4 outside corners → π/4(p+h)
    L5 = pi / 4 * (s + h)                   # 4 inside corners

    # Full-pair areas (parallel paths combined)
    A1 = 2 * q * p                          # both outer legs in parallel
    A2 = 2 * q * h                          # top + bottom back walls in parallel
    A3 = 2 * s * q                          # full centre-limb cross-section
    A4 = (A1 + A2) / 2
    A5 = (A2 + A3) / 2

    segs = [(L1, A1), (L2, A2), (L3, A3), (L4, A4), (L5, A5)]
    C1, C2 = _five_segment(segs)
    return _finalize(C1, C2, [A1, A2, A3, A4, A5])


# ---------------------------------------------------------------------------
# ETD / EER cores  (IEC 60205 §5.5)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ETDCoreDims:
    """Dimensions for a pair of ETD/EER cores (EN 62317-13).

    The centre limb is round (diameter ``F``); the outer legs are
    chord-cut sections of the rectangular footprint.
    """

    A: float    # footprint long axis
    B: float    # window+flange height per half-core
    C: float    # depth (short axis)
    D: float    # window height per half-core
    E: float    # outer-leg inner-face to centre-limb axis × 2
    F: float    # centre-limb diameter


def _etd_outer_leg_area(A, C, E):
    """Area of one ETD outer leg (chord-cut of the rectangular section)."""
    if E <= 0 or C >= E:
        # Degenerate; fall back to rectangular outer leg
        return C * (A - E) / 2
    theta = math.asin(C / E)
    aperture = E / 2 * math.cos(theta)
    seg = (E / 2) ** 2 / 2 * (2 * theta - math.sin(2 * theta))
    return C * (A / 2 - aperture) - seg


def compute_etd_core(d: ETDCoreDims) -> CoreGeometry:
    pi = math.pi
    h = d.B - d.D
    s = d.F / 2
    s1 = 0.5959 * s                         # IEC §5.5 effective inside-corner radius
    p_area_one = _etd_outer_leg_area(d.A, d.C, d.E)
    p_eff = p_area_one / d.C                # effective rectangular leg width

    L1 = 2 * d.D
    L2 = (d.E - d.F)
    L3 = 2 * d.D
    L4 = pi / 4 * (p_eff + h)
    L5 = pi / 4 * (2 * s1 + h)

    A1 = 2 * p_area_one
    A2 = 2 * d.C * h
    A3 = pi * s ** 2
    A4 = (A1 + A2) / 2
    A5 = (A2 + A3) / 2

    segs = [(L1, A1), (L2, A2), (L3, A3), (L4, A4), (L5, A5)]
    C1, C2 = _five_segment(segs)
    return _finalize(C1, C2, [A1, A2, A3, A4, A5])


# ---------------------------------------------------------------------------
# PQ cores  (IEC 60205 §5.12 / IEC 62317-13)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PQCoreDims:
    """Dimensions for a pair of PQ-cores (EN 62317-13)."""

    A: float    # footprint long axis (max diameter)
    B: float    # window+flange height per half-core
    C: float    # depth (= short-axis max width)
    D: float    # window height per half-core
    E: float    # leg-to-leg outer dim along long axis
    F: float    # centre-limb diameter (round portion)
    G: float    # outer-leg flat width (chamfered short-axis dim)
    J: float    # centre-limb flat-base parameter (axial)
    L: float    # centre-limb flat-base parameter (radial)


def compute_pq_core(d: PQCoreDims) -> CoreGeometry:
    """Closed-form IEC 62317-13 PQ formulas (no numerical quadrature)."""
    pi = math.pi
    A, B, C, D, E, F, G, J, L = d.A, d.B, d.C, d.D, d.E, d.F, d.G, d.J, d.L

    beta = math.acos(G / E)
    alpha = math.atan(L / J)
    I = E * math.sin(beta)

    # Centre-limb base flat shape factor (the K and f from IEC §5.12)
    a7 = (beta * E ** 2 - alpha * F ** 2 + G * L - J * I) / 8.0
    a8 = pi / 16 * (E ** 2 - F ** 2)
    K = a7 / a8
    lmin = (E - F) / 2
    lmax = math.sqrt(E ** 2 + F ** 2 - 2 * E * F * math.cos(alpha - beta)) / 2
    f = (lmin + lmax) / (2 * lmin)

    # Auxiliary back-wall areas (used for outside/inside corner area averages)
    a9 = 2 * alpha * F * (B - D)
    a10 = 2 * beta * E * (B - D)

    # Segments (IEC 62317-13, full-pair convention)
    L1 = 2 * D
    A1 = C * (A - G) - beta * E ** 2 / 2 + 0.5 * G * I

    # Back wall: closed-form integration over the radial coordinate (IEC §5.12).
    # ∫ dr / [(B - D) K f r] from F/2 to E/2 → (1/(K f (B - D))) ln(E/F)
    # so l_2 / A_2 condensed:
    A2 = pi * K * E * F * (B - D) / (E - F) * math.log(E / F)
    L2 = f * E * F / (E - F) * math.log(E / F) ** 2

    L3 = 2 * D
    A3 = pi / 4 * F ** 2

    L4 = pi / 4 * ((B - D) + A / 2 - E / 2)
    A4 = 0.5 * (A1 + a10)

    L5 = pi / 4 * ((B - D) + (1 - 1 / math.sqrt(2)) * F)
    A5 = 0.5 * (A3 + a9)

    segs = [(L1, A1), (L2, A2), (L3, A3), (L4, A4), (L5, A5)]
    C1, C2 = _five_segment(segs)
    return _finalize(C1, C2, [A1, A2, A3, A4, A5])


# ---------------------------------------------------------------------------
# RM cores  (IEC 60205 §5.7) — Type 3 (RM4/5/8/10/12/14)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RMCoreDims:
    """Dimensions for a pair of RM cores (EN 62317-13).

    The DB cores RM8/10/12/14 are all Type 3 (single chord-cut each
    corner, no slot, optional centre bore).  Type 1/2/4 differ in the
    a_7 expression and l_max definition; not implemented here.
    """

    A: float    # max footprint dimension (across the corners)
    B: float    # window+flange height per half-core
    C: float    # depth (across the windows)
    D: float    # window height per half-core
    E: float    # max footprint across the pole-to-pole axis
    F: float    # centre-pole diameter
    G: float    # axial across-flat dimension (Ferroxcube "E")
    H: float    # centre-pole bore diameter (0 if none)
    J: float    # smaller across-flat dimension (Ferroxcube "A")


def compute_rm_core(d: RMCoreDims) -> CoreGeometry:
    pi = math.pi
    A, B, C, D, E, F, G, H, J = d.A, d.B, d.C, d.D, d.E, d.F, d.G, d.H, d.J

    d2 = E
    d3 = F
    d4 = H
    a = J
    c = C
    e = G
    h = B - D                               # one flange thickness
    # Corner cut dimension (Type 3)
    p = math.sqrt(2) * J - A

    alpha = pi / 2
    gamma = pi / 2
    beta = alpha - math.asin(e / d2)

    lmin = (E - F) / 2
    lmax = e / 2 + 0.5 * (1 - math.sin(gamma / 2)) * (d2 - c)
    a7 = 0.25 * (
        beta / 2 * d2 ** 2
        - pi / 4 * d3 ** 2
        + 0.5 * c ** 2 * math.tan(alpha - beta)
    )
    a8 = alpha / 8 * (d2 ** 2 - d3 ** 2)
    f = (lmin + lmax) / (2 * lmin)
    Dconst = a7 / a8                        # IEC "D" (capital) — flux distribution

    L1 = 2 * D
    A1 = (
        0.5 * a ** 2 * (1 + math.tan(beta - pi / 4))
        - beta / 2 * d2 ** 2
        - 0.5 * p ** 2
    )

    L3 = 2 * D
    A3 = pi / 4 * (d3 ** 2 - d4 ** 2)

    L4 = pi / 4 * (h + a / 2 - d2 / 2)
    A4 = 0.5 * (A1 + 2 * beta * d2 * h)

    L5 = pi / 4 * (d3 + h - math.sqrt(0.5 * (d3 ** 2 + d4 ** 2)))
    A5 = 0.5 * (pi / 4 * (d3 ** 2 - d4 ** 2) + 2 * alpha * d3 * h)

    # Annular back-wall closed-form term (the "ring" integral)
    # ∫dl/A from r=d3/2 to d2/2: yields ln(d2/d3) × f / (D π h)
    # ∫dl/A² yields (1/d3 - 1/d2) × f / (D π h)²
    L_over_A_2 = math.log(d2 / d3) * f / (Dconst * pi * h)
    L_over_A2_2 = (1 / d3 - 1 / d2) * f / (Dconst * pi * h) ** 2

    segs = [(L1, A1), (L3, A3), (L4, A4), (L5, A5)]
    C1, C2 = _five_segment(segs)
    C1 += L_over_A_2
    C2 += L_over_A2_2

    return _finalize(C1, C2, [A1, A3, A4, A5])


# ---------------------------------------------------------------------------
# EFD cores  (IEC 60205 §5.13)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EFDCoreDims:
    """Dimensions for a pair of EFD (low-profile) cores (EN 62317-13).

    The centre limb is rectangular (F × F2) with two diagonal chamfers
    of side ``q``; ``K`` is an axial offset of the chamfer reference
    used to lengthen the inside-corner path.
    """

    A: float    # footprint long axis
    B: float    # window+flange height per half-core
    C: float    # depth (short axis)
    D: float    # window height per half-core
    E: float    # outer-leg-to-outer-leg distance
    F: float    # centre-limb long-axis dimension
    F2: float   # centre-limb short-axis dimension
    K: float    # chamfer axial offset (may be negative)
    q: float    # chamfer side


def compute_efd_core(d: EFDCoreDims) -> CoreGeometry:
    pi = math.pi
    A, B, C, D, E, F, F2, K, q = (
        d.A, d.B, d.C, d.D, d.E, d.F, d.F2, d.K, d.q,
    )

    L1 = 2 * D
    L2 = (E - F)                            # full pair (top + bottom back walls)
    L3 = 2 * D
    L4 = pi / 4 * ((A - E) / 2 + B - D)
    L5_inner = math.sqrt(((C - F2 - 2 * K) / 2) ** 2 + ((B - D) / 2) ** 2)
    L5 = pi / 2 * (F / 4 + L5_inner)

    A1 = C * (A - E)                        # both outer legs in parallel
    A2 = 2 * C * (B - D)                    # both back walls in parallel
    A3 = F * F2 - 2 * q ** 2                # centre limb minus the two chamfers
    A4 = (A1 + A2) / 2
    A5 = (A2 + A3) / 2

    segs = [(L1, A1), (L2, A2), (L3, A3), (L4, A4), (L5, A5)]
    C1, C2 = _five_segment(segs)
    return _finalize(C1, C2, [A1, A2, A3, A4, A5])


# ---------------------------------------------------------------------------
# Generic dispatcher
# ---------------------------------------------------------------------------

_SHAPE_DISPATCH = {
    "E":   (ECoreDims,   compute_e_core),
    "ETD": (ETDCoreDims, compute_etd_core),
    "EER": (ETDCoreDims, compute_etd_core),
    "PQ":  (PQCoreDims,  compute_pq_core),
    "RM":  (RMCoreDims,  compute_rm_core),
    "EFD": (EFDCoreDims, compute_efd_core),
}


def compute_core(shape_name: str, dims: dict) -> CoreGeometry:
    key = shape_name.upper()
    if key not in _SHAPE_DISPATCH:
        raise ValueError(f"unknown core shape: {shape_name!r}")
    cls, fn = _SHAPE_DISPATCH[key]
    return fn(cls(**dims))
