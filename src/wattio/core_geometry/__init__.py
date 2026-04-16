"""Core geometry — IEC 60205 effective-parameter calculations.

Forward calculation: given the geometric dimensions of a standard-shape
ferrite core, compute the effective area Ae, effective length Le, and
effective volume Ve using the IEC 60205:2016 formulas.

Supported shapes: E, ETD/EER, PQ, RM, EFD.
"""

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
    compute_core,
)
from .vendor_overrides import lookup_vendor_geometry
from .inverse import (
    InverseResult,
    invert_pq,
    invert_e_core,
    invert_etd_core,
    invert_rm_core,
    invert_efd_core,
    invert_core,
)

__all__ = [
    "CoreGeometry",
    "ECoreDims",
    "ETDCoreDims",
    "PQCoreDims",
    "RMCoreDims",
    "EFDCoreDims",
    "compute_e_core",
    "compute_etd_core",
    "compute_pq_core",
    "compute_rm_core",
    "compute_efd_core",
    "compute_core",
    "lookup_vendor_geometry",
    "InverseResult",
    "invert_pq",
    "invert_e_core",
    "invert_etd_core",
    "invert_rm_core",
    "invert_efd_core",
    "invert_core",
]
