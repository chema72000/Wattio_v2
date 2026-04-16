"""Vendor-published Ae/Le/Ve overrides.

Default truth source is IEC 63093-13 (computed by ``compute_core``).
Some vendors publish numbers that diverge from the standard — most
notably Ferroxcube's PQ32/30, PQ35/35 and PQ40/40 datasheets, which
quote Ae values 6–9% above the IEC formula. TDK's datasheets for the
same parts match IEC. Use these overrides when a design must track a
specific vendor's documented numbers (e.g. Frenetic simulator runs
using Ferroxcube parts).
"""

from __future__ import annotations

from .shapes import CoreGeometry


def _from_published(Ae: float, Le: float, Ve: float, Amin: float) -> CoreGeometry:
    return CoreGeometry(
        Ae=Ae, Le=Le, Ve=Ve,
        C1=Le / Ae,
        C2=Le / (Ae ** 2),
        Amin=Amin,
    )


FERROXCUBE: dict[str, CoreGeometry] = {
    "PQ20/20": _from_published(Ae=62.0,  Le=45.7,  Ve=2850,  Amin=58.0),
    "PQ26/25": _from_published(Ae=120.0, Le=54.3,  Ve=6530,  Amin=118.0),
    "PQ32/30": _from_published(Ae=170.0, Le=74.7,  Ve=12700, Amin=167.0),
    "PQ35/35": _from_published(Ae=190.0, Le=86.1,  Ve=16300, Amin=185.0),
    "PQ40/40": _from_published(Ae=201.0, Le=102.0, Ve=20500, Amin=197.0),
}


VENDORS: dict[str, dict[str, CoreGeometry]] = {
    "ferroxcube": FERROXCUBE,
}


def _normalise(name: str) -> str:
    return name.strip().upper().replace(" ", "")


def lookup_vendor_geometry(name: str, vendor: str) -> CoreGeometry | None:
    """Return the vendor's published Ae/Le/Ve for ``name``, or None.

    ``name`` matching is case- and whitespace-insensitive. Returns
    ``None`` when the vendor is unknown or the part is not in the
    override table — in that case the caller should fall back to
    ``compute_core`` (IEC values).
    """
    table = VENDORS.get(vendor.strip().lower())
    if table is None:
        return None
    target = _normalise(name)
    for key, geom in table.items():
        if _normalise(key) == target:
            return geom
    return None
