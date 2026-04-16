# Custom Core Geometry Workflow

## When to use this guide
The user is designing a transformer or inductor with a **non-standard core geometry** — i.e., starting from a catalog core (e.g., PQ20/20) and modifying one or more dimensions (typically H1 the total pair height, or H2 the total window height), or asking the agent to propose dimensions for a target Ae/Le.

For standard catalog cores with no dimensional modifications, use the Frenetic core-selection guide instead.

## Available tools

- `compute_core(shape, dims)` — IEC 60205 / IEC 63093-13 forward calculation. Takes a dict of dimensions in mm, returns `Ae`, `Le`, `Ve`, `Amin`. Implemented for E, ETD/EER, PQ, RM, EFD.
- `lookup_vendor_geometry(name, vendor)` — returns the vendor's published Ae/Le/Ve for catalog parts (currently `vendor="ferroxcube"`, PQ family). Use only for unmodified catalog cores.
- `invert_core(shape, base, target_Ae=..., target_Le=...)` — inverse problem (also `invert_pq`, `invert_e_core`, `invert_etd_core`, `invert_rm_core`, `invert_efd_core`). Given a base catalog core and target Ae and/or Le, returns the modified `H1, H2` (= `2B, 2D`) that hits the target. Footprint dims (A, C, F, …) stay fixed by default. Returns an `InverseResult` with `dims`, achieved Ae/Le, signed `relative_error` per target, and a `success` flag (True iff every target is within ±1%). Pass `free=("B", "D", "F")` (or any subset of the shape's dimension names) to vary additional dims.

## CRITICAL — IEC vs Frenetic divergence (always disclose to the user)

The IEC 60205 closed-form formula and Frenetic's simulator can give **different Ae values for the same custom geometry — up to ±10% in either direction.** Le agreement is much better (within ±3%).

The disagreement is largest for PQ cores when the geometry is far from catalog proportions (very thick or very thin flanges, very short or very tall windows). It is not reducible to a single-variable correction; Frenetic appears to use FEM-style flux integration that captures 3D field effects the IEC closed-form formula misses.

**Tolerance rule for the agent:**
- **|Frenetic − IEC| ≤ 10% on Ae** → acceptable. Proceed with the design and use Frenetic's numbers as the trusted reference.
- **|Frenetic − IEC| > 10% on Ae** → escalate. The geometry is in a regime where neither tool is reliable on its own. Recommend one of:
  1. Try a different base core (one whose proportions are closer to catalog)
  2. Re-check the dimensions entered in Frenetic for typos
  3. Report the case to the Frenetic team for verification

**This means**: any custom-geometry estimate the agent provides is a *starting point*, not the design's final number. The user must verify in Frenetic before locking the design.

## Standard workflow for custom geometry

1. **Get the user's target.** Either:
   - A target Ae/Le (e.g., "I need Ae ≈ 80 mm² and Le ≈ 50 mm to fit a specific Lmag at fewer turns"), or
   - A modification to a catalog core ("take PQ20/20 and change H1 to 15 mm").

2. **Compute IEC values for the proposed geometry.** Call `compute_core("PQ", dims)` (or whichever shape).

3. **Present the result with the divergence disclosure.** Format:
   > *"Based on the IEC 60205 formula, this geometry gives Ae ≈ X mm² and Le ≈ Y mm. **Note that Frenetic's simulator can differ from IEC values by up to 10% on Ae** (Le agreement is typically within 3%) for non-catalog geometries. Please enter these dimensions in Frenetic and share the Ae and Le it reports — I'll iterate if needed."*

4. **When the user reports Frenetic's numbers**, treat those as the ground truth. If they're close enough to the target, accept the geometry. If not, propose a small dimensional adjustment and repeat.

5. **Before recommending a final design**, also check:
   - **Amin** (minimum cross-section) — flux density is `B = V·t / (N · Amin)`, not Ae. Saturation depends on Amin.
   - **Flange thickness** (B − D) — if it drops below ~2 mm the back wall becomes the saturation bottleneck and the design is fragile.
   - **Manufacturing feasibility** — non-catalog dimensions mean a custom or trimmed core. Confirm with the user that this is acceptable (custom tooling cost, lead time).

## Things to watch for

- **Centre-limb area is dominant for Ae but does not scale with H1/H2.** Shrinking the core mostly shrinks Le and Ve, leaving Ae nearly constant. This is useful for designs that are core-loss-limited (Ve↓ helps) but not for designs that need more Ae.
- **Per-turn inductance L/N² = μ·Ae/Le.** If you shrink H2 (Le drops faster than Ae), per-turn inductance goes UP — fewer turns needed for the same Lmag, but Bpeak rises proportionally. May push the design into the upper-Bmax range (see PSFB guide on Bpeak > 200 mT).
- **Vendor disagreement on catalog cores is also real**: Ferroxcube's published Ae for PQ32/30, PQ35/35, PQ40/40 deviates from IEC by 6–9%. TDK matches IEC. Use `lookup_vendor_geometry("PQ40/40", "ferroxcube")` if the user has selected Ferroxcube parts and wants the vendor's documented numbers.
