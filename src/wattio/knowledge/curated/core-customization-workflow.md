# Core Customization Workflow

## When to use this guide

Use this guide for the **end-to-end process of offering and executing custom-core design** within the magnetic design workflow. This is the orchestration layer. For the mechanics of the IEC calculation itself (forward, inverse, ±10% IEC-vs-Frenetic handling), use `custom-core-geometry.md`.

Trigger this guide when:
- A standard-core search returns no candidate that satisfies the user's stated constraints, **or** one or more stated constraints are borderline.
- The user directly asks to customize a core (e.g., for testing / R&D), even if a standard core would fit.

## Golden principles

- **Flag, don't gate.** The user is always the final arbiter. Surface the customization offer whenever a potential problem appears; never block the user from accepting an out-of-constraint standard core.
- **One step at a time.** Per the system's golden rule — show one proposal, wait for the user, iterate. Never list all steps upfront.
- **Trust IEC, use Frenetic to validate.** The IEC 60205 calculation is the authoritative geometry model. Frenetic is the validation and deliverable environment. When they disagree, adjust Frenetic dimensions (not the IEC spec) to make Frenetic report the IEC-calculated Ae/Le.
- **v1 scope is bounded.** Customization means **modifying dimensions of a standard shape** (PQ, E, ETD, RM, EFD). Arbitrary parametric geometries are out of scope.
- **Never guess Ae/Le/Ve or outer dimensions from memory.** Always call a tool: `core_envelope` for outer dims, `compute_core` for IEC Ae/Le/Ve, `lookup_vendor_geometry` for catalog vendor numbers. Phrases like "Ae ≈ 125 mm² (est.)" are forbidden — they mislead the user.
- **Minimum-change strategy — do NOT proportionally scale every dimension.** Identify only the dimension(s) that block the binding constraint and adjust those. All other dimensions stay at their standard-catalog values. Example: if the constraint is width 39 mm and the standard core has A = 40 mm, adjust only A (40 → 39); do not scale B, C, D, E, F by 0.975. Proportional scaling changes magnetic properties unnecessarily and breaks the loss balance.
- **No "unexpected but OK" language.** If Frenetic's Ae or Le differs meaningfully from the IEC-calculated target, that is **not** a result to accept — it is a trigger to iterate. See Step 7.

## Step 1 — Constraint intake (early, before core selection)

Ask the user for mechanical, thermal, and power-density constraints as a **single structured block**. Every field is optional; the user fills only what matters.

| Field | Unit | Notes |
|---|---|---|
| Max height | mm | z-axis / board clearance |
| Max footprint | mm × mm | x/y envelope |
| Max weight | g | |
| Max volume | cm³ | alternative to footprint + height |
| Power density target | W/cm³ or W/kg (user picks) | |
| Max temperature rise | °C | thermal budget |
| Cooling method | natural / forced / conduction | affects thermal budget interpretation |

**v1 treatment:** flat — no hard vs. soft distinction. Any stated limit is treated uniformly; a borderline miss triggers the customization offer the same as a clean miss.

## Step 2 — Standard-core search

Run core selection as normal (per the topology's Frenetic guide), filtered by electrical sizing + the intake constraints.

**Envelope filtering — use the `core_envelope` tool.** It returns the outer bounding-box of any catalog core (E, ETD, PQ, RM, EFD). You can call it in three ways:
- `core_envelope(max_dims=[H, W, D])` — list all catalog cores that fit the envelope.
- `core_envelope(names=[...])` — get envelopes for specific cores to compare.
- `core_envelope(max_dims=[...], family="PQ")` — filter by family too.

**Orientation-agnostic matching (important — dimension names do not matter).**
The labels "height / depth / width" are arbitrary mounting conventions. What matters is whether the three numeric constraints can be mapped to the three outer dimensions of the core in **any orientation**. The `core_envelope` tool does this by sorting both sides descending and comparing element-wise, so:
- 1 constraint value → treated as max-height; the core's *smallest* axis must fit (i.e., lay it flat).
- 2 values → treated as max-footprint; the two largest axes must fit.
- 3 values → full envelope; all three axes must fit in some orientation.
Do **not** reject a core because a dimension labeled "A" in the datasheet exceeds the user's "max width" — always compare numerically, orientation-agnostic.

## Step 3 — Flag any potential problem

If **every** stated constraint is cleanly satisfied by at least one standard core → proceed with that core; **still** mention that customization is available on request (in case the user wants it for testing).

If **any** stated constraint is missed or borderline by the best candidates:
1. Present the best standard candidate(s) with the misses explicitly named ("this fits all electrical specs but is 14 mm tall — you said max 12 mm").
2. Offer the customization path alongside it.
3. Let the user pick — **they may still accept a standard core that misses a constraint.** That is allowed; don't re-argue.

## Step 3.5 — Complete the baseline design first (constraint-miss path only)

**When this applies:** the user has chosen to address a constraint miss via customization (not just accept the out-of-constraint standard core).

**What to do *before* touching any core dimensions:** finish the full design on the closest-matching standard candidate from Step 3.
1. Size the windings (turns, wire/litz selection) on that standard core.
2. Compute the loss breakdown (Pcu + Pfe) and the thermal estimate.
3. Produce the concrete, quantified gap vs. each stated goal — e.g., *"height 14 mm vs. 12 mm limit; total loss 28 W vs. 24 W budget; ΔT 62 °C vs. 50 °C target"*. This baseline anchors the customization: the agent now optimizes against measured numbers, not against the abstract "you missed a constraint" flag.

Present the baseline design to the user, then ask whether they want to proceed into customization to close that gap. Only after they confirm do you move to Step 4.

**When this is SKIPPED:** the user-initiated customization path (testing / R&D — no failed constraint). Go straight to Step 4.

## Step 4 — Starting-core selection for customization

Once the user accepts customization:
1. **Constraint-miss path (came through Step 3.5):** the starting core **is** the one used in the Step 3.5 baseline — you already have its winding design, loss breakdown, and thermal numbers. Do not re-pick.
2. **User-initiated path (skipped Step 3.5):** the agent suggests a starting standard core based on electrical sizing.
3. In both cases, **user can override** and pick a different standard core as the starting point. Accept their choice without pushback (on the constraint-miss path, override means re-running the baseline on the new core before continuing).

## Step 5 — Pick the optimization objective

Ask which objective the agent should optimize for:

- **Minimize total losses** (Pcu + Pfe) — default when the design is efficiency-driven.
- **Minimize temperature rise** — when the binding concern is thermal; requires iterating through Frenetic simulation for thermal evaluation.

You may **infer** the objective from the binding constraint (thermal limit missed → temp-rise objective; otherwise → total-loss) and **confirm with the user before iterating**. Never assume silently.

Do **not** optimize for power density. Power density is only a constraint (pass/fail) from the intake, never a target of the optimizer.

Do **not** use the Pcu ≈ Pfe heuristic as the objective. It is superseded by explicit thermal optimization through Frenetic when thermal matters.

## Step 6 — Propose geometry changes, one at a time

All dimensional parameters of the chosen standard shape are modifiable. Changes must follow a **minimum-change strategy driven by the binding constraint and the chosen objective** — never proportional scaling of every dimension.

**Procedure for each candidate:**

1. **Identify the binding dimension(s).** Compare the standard core's outer envelope (from `core_envelope`) to the user's constraint. Only the dimensions that *exceed* the constraint need to change. Every other dimension stays at its standard-catalog value.
2. **Propose the change.** Start by setting the binding dimension(s) to the constraint value (or just inside it). Leave everything else alone unless the objective (total loss / temp rise) is broken and re-balancing demands it.
3. **Compute IEC Ae/Le/Ve for the proposed geometry** using `compute_core(shape, base_core="...", overrides={...})` — **before** the user enters anything in Frenetic. These are the **target** values that Frenetic must match. Also compute the standard core's IEC baseline the same way (no overrides) for comparison.
4. **Translate IEC labels → Frenetic input fields before instructing the user.** Frenetic uses Ferroxcube-style labels (A, B, C, D2, D3, E, F) which differ from IEC (A, B, C, D, E, F). See `custom-core-geometry.md` for the per-family mapping table. Tell the user which *physical* dimension goes in each Frenetic field (e.g., "put the centre-leg diameter in field F", not just "put F = 12.5"). Do **not** repeatedly ask the user what Frenetic's fields mean — the mapping is known.
5. **Show the user:** the dimension table, the IEC-calculated Ae/Le/Ve for the proposal, the standard core's IEC baseline (from `compute_core`, not memory), and the expected impact on losses / temp rise.
6. **Wait** for the user's reaction. If the user tweaks any dimension, incorporate and regenerate the next candidate.

Example of the binding-dimension discipline: constraint is 39 × 39 × 13 mm; standard ETD39 envelope from `core_envelope` is 40.0 × 25.6 × 10.8 mm (sorted largest→smallest). Sort constraints: 39 × 39 × 13. Element-wise: 40 > 39 (miss), 25.6 < 39 (fits), 10.8 < 13 (fits). **Only A needs to change** (40 → 39). B, C, D, E, F all stay at standard values. Proportional scaling of everything is wrong here.

Example of rebalancing: if the binding constraint is height AND shrinking the height drops Ae so much that losses blow up, then AFTER the minimum change you may propose a secondary change (e.g., widen the footprint to recover centre-leg area), but only if (a) there is budget in another free dimension and (b) the objective requires it. State explicitly why each additional change was made.

**Use Frenetic only when you actually need simulated data** for the current decision (thermal-rise evaluation, final validation). Early analytical iterations do not require Frenetic in the loop.

## Step 7 — Validate in Frenetic

When the candidate is close to the target, have the user enter it in Frenetic and simulate:

1. Enter the custom geometry in Frenetic.
2. Ask the user to report the **Ae and Le Frenetic reports**.
3. **Compare to the IEC-calculated targets from Step 6.** You already have these numbers — do not guess "expected" values from the standard core's published Ae.
4. Decision rule:
   - **Close match** (|Frenetic − IEC| ≤ ~3% on Ae, ≤ ~2% on Le) → accept, proceed.
   - **Meaningful divergence** → **iterate on the Frenetic dimensions** (not on the IEC spec) until Frenetic reports Ae and Le equal to the IEC targets. Typically the centre-leg cross-section is the most sensitive knob for Ae; path-length dimensions drive Le. Change one dim, re-simulate, converge.
   - **Never** accept the result with language like *"unexpected but actually good news"* or *"higher Ae means better thermal capacity so it's fine"*. That erodes user confidence and hides a real divergence between the manufacturing spec (IEC) and the simulation geometry. If Frenetic and IEC disagree, either iterate or explicitly flag that the simulation does not yet represent the intended geometry.
5. When Frenetic reports the IEC targets, record both dimension sets: IEC dimensions = **manufacturing spec**; Frenetic dimensions = **simulation-only geometry**. They may differ slightly. (See `custom-core-geometry.md` for empirical divergence data.)
6. Simulate the **full design** — core + winding — in Frenetic. Not just the core in isolation.

## Step 8 — Stop conditions

Stop iterating only when **both** hold:
1. The user accepts the current candidate, **and**
2. The design meets all stated goals (constraints + chosen objective target).

If the user accepts something that still misses a goal, **surface the miss explicitly** ("you said max height 12 mm; this design is 12.8 mm — confirm you want to proceed?") and let them override if they still accept.

## Step 9 — Deliverable

The deliverable is **always a Frenetic simulation of the custom core and the complete design.** That is the artifact the user takes away. No separate spec-sheet / datasheet output in v1 — the simulation is both the validation and the deliverable.

For manufacturing, hand off **the IEC dimensions** (not the adjusted Frenetic dimensions, if they differ).

## Step 10 — Infeasibility handling

If no geometry in v1's shape-family (variations of a standard core) can satisfy the stated constraints after reasonable iteration, **escalate**:

1. Name the specific blocking constraint and the amount of miss.
2. Offer the relevant subset of:
   - **Switch shape family** (e.g., PQ → ETD, E → RM) that could plausibly satisfy the constraints, with the reasoning.
   - **Relax a named mechanical constraint** (height / footprint / volume / weight) by a specific amount — name what changes and by how much.
   - **Raise the transformer loss budget** (= relax the target efficiency). State both numbers, e.g., *"raise the transformer budget from 21.6 W to 28 W; that corresponds to lowering the converter efficiency target from 97 % to ~96.2 %"*. Be explicit that this means **the design will dissipate more watts**, which is what makes the smaller core thermally viable. Never word this as "reducing losses" — that is the inverted framing.
   - **Improve cooling** (higher airflow, heatsink, conduction path) — this raises the *thermal capacity* of any given core without changing the loss budget, so a smaller core can carry the same losses.
3. Spell out the tradeoff for each option (what the user gives up). Let the user pick direction. Do **not** silently switch shape families, drop constraints, or invert the framing of the efficiency/loss tradeoff.

**Sanity check before presenting any "make the small core work" option:** for the same V, I, f, and ripple, a smaller core *always* dissipates more watts than a larger one. So any path that keeps the small core must come from one of: (a) more allowed losses (budget up), (b) more cooling (capacity up), or (c) different shape with better surface-to-volume ratio. There is no path where shrinking the core *reduces* losses — if your reasoning leads there, you have inverted a sign.

## Quick checklist (agent self-check)

- [ ] Asked the full constraint-intake block at the right step (before core selection).
- [ ] Used `core_envelope` (not eyeballed datasheet labels) to check dimensional fit.
- [ ] Matched envelopes numerically and orientation-agnostically (sorted values, not named axes).
- [ ] Flagged, not gated, any constraint miss.
- [ ] Offered customization on any miss AND available on user request for testing.
- [ ] **On the constraint-miss path: completed the full baseline design on the closest standard core (windings + losses + thermal) BEFORE entering customization.** Skipped this only on the user-initiated path.
- [ ] Suggested a starting core but accepted user override. On the constraint-miss path, the starting core is the one from the baseline design.
- [ ] Confirmed the optimization objective before iterating.
- [ ] **Changed only the binding dimensions** — did NOT proportionally scale every dimension.
- [ ] **Computed IEC Ae/Le/Ve via `compute_core` BEFORE asking the user to enter dimensions in Frenetic.** Never guessed from memory or datasheet numbers.
- [ ] Proposed one geometry at a time, waited for user reaction.
- [ ] Called Frenetic only when simulation was actually needed.
- [ ] **Compared Frenetic Ae/Le to the IEC target, not to a remembered standard-core Ae.** Did not use "unexpected but OK" language — either the numbers match or we iterate.
- [ ] If Frenetic ≠ IEC: adjusted Frenetic dimensions, not IEC spec, until Frenetic reports the IEC target.
- [ ] Stopped only on user-accept + goals-met (or surfaced the miss and got explicit override).
- [ ] Closed with a Frenetic simulation of core + full design.
- [ ] On infeasibility, offered shape-family switch OR named constraint relaxation — never silent.
