# Frenetic Simulator: PSFB Transformer Core Selection Guide

## ⚠️ MANDATORY — READ FIRST ⚠️
**DO NOT execute Steps 1–6 or Step 9. They are disabled for testing.**
After calculating the loss budget (Step 7), run `core_thermal_search` (Step 8), then run `power_density_search` (Step 8b) to show reference benchmarks. Then jump DIRECTLY to Step 10. Do NOT tell the user to open Frenetic, create a project, select topology, fill waveforms, fill advanced settings, or open the Core Optimizer. Assume all of that is already done. Go straight to the Core Tab instructions in Step 10.

## Overview
Step-by-step guide for selecting a transformer core for a Phase-Shifted Full-Bridge (PSFB) converter (full-wave or center-tap secondary) using Frenetic simulator.

## Required Input Specifications

### Minimum (mandatory)
- Ambient Temperature — T (°C)
- Magnetizing Inductance — Lmag (µH)
- Switching Frequency — fsw (kHz)
- Input Voltage — Vin (V), can be a range (min/max)
- Output Inductor Current Ripple — Io Ripple (A), per operating point. This is the ripple of the **output inductor** current, NOT the transformer magnetizing current ripple. NEVER zero — if unknown, simulate with LTspice or estimate as 20% of Io
- Converter Output Power — Po (W)
- Output Voltage — Vo (V), can be a range
- Secondary Output Power — (W)
- Turns Ratio — m2 = n1/n2

### Recommended (industrial projects)
- Max Temperature Rise — ΔT (°C) = Tmax - Tambient
- Maximum Dimensions — W x H x D (mm)
- Cooling Conditions:
  - Free convection
  - Forced convection (specify air speed in m/s)
- Isolation Requirements:
  - Insulation type: Reinforced, Functional, or Basic
  - Pollution degree: 1, 2, or 3
  - Overvoltage Category: I, II, III, or IV
  - Safety Standards (informational only, no design impact)
  - Creepage distance (mm)
  - Clearance distance (mm)
  - Voltage AC main or DC input (Vrms)
  - Height above sea level (m) — no design impact

## Step-by-Step Workflow

### Step 1: Create New Project
- Open Frenetic simulator → Click **"NEW DESIGN"** (top-right corner)
- Enter project name, optionally select folder and collaborators
- Click **"ACCEPT"**

### Step 2: Select Magnetic Component Type
- Select **"Transformer"** from: Inductor, Transformer, Flyback, Active Clamp Flyback
- The topology selection screen appears automatically after clicking

### Step 3: Select Topology
- Select the correct PSFB variant:
  - **"PSFB Secondary Full Wave Rectifier"** — for full-wave (bridge) secondary rectification
  - **"PSFB Secondary Center Tap"** — for center-tap secondary rectification
- Other available topologies: Custom, Full Bridge LLC, Half Bridge LLC, CLLC, Dual Active Bridge
- The next screen appears automatically after clicking

### Step 4: Define Operating Points and Fill Waveform Data
Each operating point has the same input fields. For each OP, enter:
- **Left side:** T (°C), Lmag (µH), fsw (Hz), Vin (V), Io Ripple (A), Converter Output Power (W)
- **Right side:** m2 (turns ratio n1/n2), Vout (V), Power (W)

These are the ONLY inputs — do NOT mention Duty Cycle, Output Current, or any other parameters that are not listed here. Frenetic automatically generates the waveforms from the topology and these inputs.

**CRITICAL: Io Ripple must NEVER be zero.** This is the **output inductor current ripple** — the AC ripple component on the output filter inductor. It is NOT the magnetizing current ripple of the transformer. Do NOT ask the user for magnetizing current ripple — Frenetic does not need it; it computes the magnetizing current internally from Lmag and the applied voltage.

To obtain the Io Ripple value:
1. **Best:** simulate with LTspice (`ltspice_run`) and measure the output inductor current ripple
2. **If LTspice is available but not yet simulated:** run the simulation and extract the ripple
3. **If no simulation is available:** calculate as Io_ripple = 20% of Io (where Io = Po / Vo)
4. **If the user provided the value:** use their value directly
Always ask the user to confirm the Io Ripple value before entering it.

Create multiple operating points using **"Add OP"** when:
  - The input voltage is a range (different Vin per OP)
  - The output voltage is a range (different Vo per OP)
  - Different load conditions exist (different Po per OP)

**The worst case for the core is always the highest voltage** (either Vin or Vo depending on topology)

### Step 5: (merged into Step 4 above — skip to Step 6)

### Step 6: Fill Advanced Settings
Click **"Advanced"** button to enter:
- Max Temp Rise ΔT (°C) — NOTE: this is the RISE, not absolute max (ΔT = Tmax - Tambient)
- Maximum Dimensions (W, H, D in mm)
- Cooling Conditions (Free/Forced convection)
- Insulation Requirements (type, pollution degree, overvoltage category, voltage)
- Click **"< Back to Waveform"** when done

### Step 7: Calculate Loss Budget
If the user does not provide a specific loss target, calculate it:

1. Total converter losses = Po × (1 - η) / η
   - Default efficiency goal: η = 95% (conservative), 97% (aggressive)
2. Magnetic losses = 30% of total converter losses
3. For topologies with two magnetics (like PSFB):
   - Transformer = 70% of magnetic losses
   - Inductor = 30% of magnetic losses
4. Total transformer losses = core losses + winding losses (use for thermal pre-selection)

### Step 8: Thermal Pre-Selection — BEFORE Core Optimizer

**MANDATORY: Before opening the Core Optimizer in Frenetic, use the `core_thermal_search` tool to find viable cores.**

Call `core_thermal_search` with:
- `total_losses`: the total transformer losses calculated in Step 7 (core + winding)
- `cooling`: the user's cooling condition ("natural", "forced_1", or "forced_4")
- `p_pct_ferrite`: 50 (default for transformers with ~50/50 core/winding split)

The tool searches the thermal dissipation database and returns the **3 smallest cores** (one each from E, PQ, ETD, or RM families) whose total dissipation capacity is at least 90% of the expected total losses.

**⚠️ CRITICAL: Present the EXACT core names and data returned by the tool. NEVER create your own summary table with different cores. NEVER substitute cores from memory or general knowledge. Copy the core names, volumes, and capacities directly from the tool output.**

After presenting the tool output, add a **Power Density** column for each core. Calculate as:

**Power Density (kW/L) = Converter Output Power (W) / Core Effective Volume (mm³) × 1 000 000**

Power Density tells the engineer how aggressively each core is being used — higher values mean a smaller core for the same power, which is harder to cool but more compact.

Also explain:
- These are the starting points for viability screening
- They are thermally viable under the specified cooling conditions
- If no cores are found, discuss alternatives (forced convection, relaxing ΔT, reducing losses)

### Step 8b: Power Density Reference — Benchmark Against Real Designs

**MANDATORY: After thermal pre-selection, use the `power_density_search` tool to find reference designs with similar topology.**

Call `power_density_search` with:
- `topology`: the converter topology (e.g., "PSFB")
- `magnetic_type`: "transformer" or "inductor"

The tool searches the power density database and returns real-world designs with the same topology.

**Present ALL information from the database to the engineer** for each matching design:
- Source (Academic / App Note), reference URL
- Power level, switching frequency, turns ratio
- Cooling conditions
- Core used (and number of stacks)
- Winding technology (concentric, hybrid, etc.)
- Effective volume and **power density (kW/L)** = converter power / effective core volume
- Efficiency
- Loss breakdown: total magnetic losses, winding losses, core losses
- Frenetic simulation link (if available)

**Selection and presentation rules:**
- If there are **multiple matching designs**, select the **closest ones** to the user's design in terms of power level and frequency.
- **Present at least one design per source category** when available — show both an **App Note** reference and an **Academic** reference. These have different value: app notes are industry-proven and conservative, academic designs push the boundaries of power density.
- If only one source category has matches, present the closest designs from that category.
- Present the data in a **full table** so the engineer can compare all parameters side by side.

**Example presentation:**
> *"Here are two reference PSFB transformer designs from the database:*
>
> | Parameter | App Note (Infineon) | Academic (ETH Zürich) |
> |-----------|--------------------|-----------------------|
> | Power | 3300 W | 5000 W |
> | Frequency | 100 kHz | 25 kHz |
> | Core | PI35/23 (×1) | E70/33/32 (×2) |
> | Cooling | Forced air | Natural |
> | Power density | 412 kW/L | 24.5 kW/L |
> | Efficiency | 98% | 98% |
> | Total losses | 30 W | 46.4 W |
> | Winding / Core | 27.3 / 2.7 W | 42.8 / 3.2 W |
>
> *The Infineon app note at 100 kHz with forced air achieves a very high power density (412 kW/L) but uses a specialized core. The ETH academic design at 25 kHz with natural convection is more conservative (24.5 kW/L) but uses stacked E70 cores. Your design at 1 kW / 100 kHz should target somewhere in this range depending on cooling."*

**This gives the engineer context** — they can see what others have achieved with similar designs before starting the screening process. It sets realistic expectations for core size and power density.

### Step 9: Core Optimizer — Open and Configure (DISABLED)

**IMPORTANT: Always identify and start with the worst-case operating point for the core.**
- The worst case for the core is always the **highest voltage** operating point (higher voltage → higher volt-seconds → higher Bpeak → higher core losses)
- Designing for the easy OP first and discovering the hard OP later wastes time

**Testing order:** Start from the **most aggressive** (smallest) core from Step 8. If it works, the bigger ones are even easier.

In the Core Optimizer tab:
1. Select goal: **"Core Loss Target (W)"** from the dropdown
2. Enter a **conservative (lower) core loss target** — use about 50-70% of the calculated budget. A tight target shows MORE candidates on the plot because the optimizer finds solutions with lower losses across more core sizes. A loose target can filter out smaller cores that can't reach that loss level, hiding good options.
3. Select the Family Shape matching the pre-selected core (e.g., PQ, E, ETD, RM)
4. **Select Material** based on the frequency and temperature (see `ferroxcube-material-selection.md` for recommendation)
5. Find the specific core size from Step 8 on the optimizer plot
6. Click to add the core — note the suggested turns, core losses, Bpeak, gap, and inductance
7. Proceed to Step 10 for viability screening with winding

**Handle "No Solution" in Core Optimizer:**

There are two common causes for "no solution" — the agent MUST diagnose which one before proposing a fix:

**Cause A: Core loss target is too HIGH for the Lmag value.**
- A high Lmag requires many turns to achieve the inductance
- More turns → lower Bpeak → **lower core losses** (NOT higher!)
- So the optimizer cannot find a solution that simultaneously has high Lmag AND high core losses — these are contradictory
- **Solution:** Reduce the core loss target by **~20%** (one small step). For example: 5 W → 4 W. If the desired core still doesn't appear after one reduction, **stop** — the core likely cannot achieve that Lmag. Do NOT keep reducing by 50%, 70%, or 80% — that produces unrealistic targets.
- This is the MOST COMMON cause — try this FIRST

**Cause B: The desired core doesn't appear even after one 20% reduction.**
- The core is too small to achieve the target Lmag, OR the Lmag is genuinely too high for this family
- **Solution:** Move on to the next (larger) core from the pre-selection list. If all pre-selected cores in this family fail, propose reducing Lmag to the user. Start with the user's minimum acceptable value. Always ask before changing

**CRITICAL — Lmag and ZVS physics (DO NOT get this wrong):**
- **Lower Lmag → MORE magnetizing current → EASIER ZVS** (more energy available to charge/discharge parasitic capacitances of the MOSFETs)
- **Higher Lmag → LESS magnetizing current → HARDER ZVS** (less energy, ZVS may be lost at light loads)
- So reducing Lmag is NOT harmful for ZVS — it actually **helps** ZVS. The tradeoff is: lower Lmag increases magnetizing current, which adds conduction losses in the primary
- **NEVER say** "reducing Lmag hurts ZVS" or "high Lmag is needed for ZVS" — this is the opposite of reality
- High Lmag does NOT push toward larger cores. High Lmag requires many turns, but many turns means LOWER Bpeak and LOWER core losses. The issue is that the winding becomes more complex (more turns to fit)

**CRITICAL — Physics reminder:**
- More turns → lower Bpeak → **LOWER** core losses (not higher)
- More turns → higher winding resistance → **HIGHER** winding losses
- The Core Optimizer only shows core losses — a "no solution" for a high loss target with high Lmag means the optimizer can't make core losses that HIGH because the many turns keep Bpeak low
- High Lmag does NOT require larger cores — it requires more turns, which makes winding harder but core losses easier

### Step 10: Viability Screening — Core Tab + Winding Check

**Goal:** For each core from Step 8 (now 6 cores in 3 tiers), quickly determine if there is ANY combination of turns that makes total losses (core + winding) thermally viable. This is a screening step — do NOT optimize, just check viability.

**Testing order:** Start from the **most aggressive** (smallest) core first. If a small core works, it's a better design. Work upward toward conservative cores only as needed.

#### Procedure (repeat for each core, starting from most aggressive):

**Phase 1 — Core Tab: Find valid turns with target Lmag and safe Bpeak**

**Goal:** Find a turns count that simultaneously achieves the target magnetizing inductance (Lmag), respects the turns ratio, and keeps Bpeak below saturation — while minimizing turns to keep winding losses low.

1. **Open the Core tab** in Frenetic
2. **Select the core** from the pre-selection list (e.g., PQ26/25)
3. **Select the material** (see `ferroxcube-material-selection.md`)
4. **Open the Inductance Calculator** (click **"LAUNCH CALCULATOR"**)
5. **Propose an initial turns count** — the minimum turns must satisfy TWO constraints simultaneously:

   **Constraint 1 — Turns ratio:** The primary/secondary pair must respect the turns ratio within ±10% error.

   **Constraint 2 — Minimum inductance:** A minimum number of primary turns is needed to reach the target Lmag. Inductance scales with N² (L = AL × N²), so very few turns may make it physically impossible to reach the target inductance even with the maximum gap. If the first ratio-valid pair gives inductance far below Lmag, jump to a higher pair rather than iterating one by one.

   **Procedure:**
   - Try secondary = 1, primary = round(ratio). If the ratio error is too large (>10%), try secondary = 2, then 3, etc.
   - Pick the **smallest** primary/secondary pair where the ratio error is acceptable.
   - Example: ratio n1/n2 = 7.3 → try 7/1 (ratio 7.0, error 4%) — start here.
   - Tell the user: *"Try primary = 7, secondary = 1 in the Inductance Calculator. Click CALCULATE and report: inductance (µH), Bpeak (mT), core losses (W), and gap (mm)."*
   - **If the resulting inductance is far below target Lmag** (e.g., less than 50% of target), do not increment one step at a time — jump to a significantly higher turns pair (e.g., from 7/1 to 15/2 or 22/3) since inductance grows with N².
6. **Evaluate the user's results and iterate:**

   **Completion criteria for Phase 1:** Inductance ≥ target Lmag (or within ±10%) AND Bpeak < Bmax AND gap ≤ 2 mm. When all three are met, Phase 1 is done.

   **Bmax depends on the material:** 200 mT for most ferrite materials, ~220 mT for 3C92.

   **High turns ratio exception (n1/n2 > 10):** When the turns ratio exceeds 10, the secondary often has only 1–2 turns, which forces the primary to a turns count where Bpeak naturally lands above 200 mT. In this case, do NOT immediately increase turns to push Bpeak below 200 mT — that may inflate primary turns unrealistically and explode winding losses. Instead:
   - Allow Bpeak to operate in the **upper Bmax range** (up to ~280–300 mT for most ferrites, near the material's saturation knee at operating temperature). Check the material datasheet for the actual Bsat at Tmax.
   - Tell the user: *"With turns ratio > 10, this design naturally pushes Bpeak above the conservative 200 mT limit. Operating closer to the material's saturation knee is acceptable here, but core losses will be higher. Let's discuss cooling — do you have forced convection available? Heatsink mounting? A larger core footprint?"*
   - Discuss cooling options BEFORE discarding the configuration: forced air, heatsink contact, removing the bobbin (better core-to-winding heat transfer), or a larger core.
   - Only fall back to "increase turns" if the user has no cooling headroom and the higher core losses cannot be dissipated.

   | Condition | Action |
   |-----------|--------|
   | Inductance ≥ Lmag (or within ±10%) AND Bpeak < Bmax AND gap ≤ 2 mm | ✅ **Phase 1 complete** — click **"APPLY"** and proceed to Phase 2 (Winding) |
   | Inductance too low (below 90% of target Lmag) | **Increase turns** — try the next valid pair (e.g., 7/1 → 15/2 → 22/3) |
   | Bpeak ≥ Bmax (near saturation) | **Increase turns** — more turns lowers Bpeak |
   | Gap > 2 mm (manufacturing concern) | **Increase turns** — more turns reduces the required gap |
   | Lmag is much higher than target | This is fine — Frenetic adjusts the gap to match. Only a concern if gap becomes very large (>2 mm) |

   For each iteration, tell the user the new turns to try and ask them to click **"CALCULATE"** and report results.

7. **Once a valid configuration is found:** Click **"APPLY"** to lock in the turns, then proceed to Phase 2.

**Key principle:** Fewer turns = lower winding losses but higher Bpeak. Start from the minimum and only increase when forced by Lmag or Bpeak constraints. This gives the best starting point for winding losses.

**Phase 2 — Winding: Check total losses**

7. **Generate a winding:** Go to Winding tab → set the turns → click **"SUGGEST WIRE"**. Note the winding losses, window occupation %, and whether interleaving is applied.

   **Handle "No solution with reasonable current density" in Suggest Wire:**

   If Frenetic says there is no winding solution with reasonable current density, it means the core's window area is too small to fit the required copper for the RMS currents at this turns count. **Increasing turns does NOT fix this** — current density depends on RMS current and wire cross-section, not on the number of turns. More turns would actually make it worse (more turns to fit in the same window).

   **Action:** The core is too small. Put this core on hold and **move to the next (larger) core** from the pre-selection list. Do NOT attempt to fix this by adjusting turns or wire parameters — the fundamental constraint is window area vs. current.

8. **Review winding before iterating — quick wins FIRST.** Before changing turns, check if the winding itself can be improved at the current turns count. Apply these checks in order:

   **Check A — Interleaving:**
   Ask the user to report the current layer arrangement (e.g., P-P-S, P-S-P, P-S-P-S, etc.).

   **Full interleaving** means primary and secondary layers alternate as much as possible. The correct arrangement depends on the number of layers of each winding:

   | Primary layers | Secondary layers | Full interleaving | NOT full interleaving |
   |---------------|-----------------|-------------------|----------------------|
   | 2 | 1 | **P-S-P** | P-P-S |
   | 1 | 2 | **S-P-S** | S-S-P |
   | 2 | 2 | **P-S-P-S** or **S-P-S-P** | P-P-S-S |
   | 3 | 1 | **P-S-P-P** or **P-P-S-P** | P-P-P-S |
   | 3 | 2 | **P-S-P-S-P** | P-P-S-P-S or worse |
   | 3 | 3 | **P-S-P-S-P-S** | P-P-P-S-S-S |

   **Rule:** If the arrangement already maximizes alternation for the given number of layers, it IS full interleaving — do NOT ask the user to change it. Only request interleaving changes when layers of the same winding are grouped together unnecessarily (e.g., P-P-S instead of P-S-P).

   **Why interleaving matters (physics):** Proximity losses grow quadratically with the number of layers of the same winding stacked together — the factor is (4M²−1)/12, where M is the effective number of same-winding layers between interleaving breaks. Going from 1 → 2 stacked layers increases proximity losses by ~5×; 1 → 3 by ~12×. Interleaving (P-S-P-S) resets the MMF build-up so each section behaves as M = 1. This same quadratic scaling applies to **both round/litz and foil** windings — the gain from interleaving is identical for both.

   If interleaving is NOT applied:
   - Tell the user: **"Customize the position of the layers to apply interleaving (alternate primary and secondary layers) to reduce proximity losses."**
   - Specify the target arrangement from the table above.
   - Ask the user to report the new winding losses after applying interleaving.
   - This alone can significantly reduce winding losses — always do it before concluding the winding is too lossy.

   **Check B — Window occupation:**
   Ask the user for the current window occupation %. If it is **below 70%**, there is room to add copper and reduce winding losses:
   - Tell the user: **"Window occupation is only [X]% — try increasing the number of strands (or parallels) to bring it closer to 80%."**
   - Propose a **small increment** (e.g., if 10 strands, try 12; if 50 strands, try 55). Do NOT propose doubling.
   - Ask the user to click **"SUGGEST WIRE"** again (or manually adjust strands) and report the new winding losses and window occupation.
   - Repeat until window occupation reaches ~75–80% or winding losses stop improving.

   **Check C — Conductor type (litz vs foil):**

   Frenetic can generate either litz-wire or foil windings. The right choice depends on the winding arrangement and whether the core is gapped.

   **Prefer FOIL when all of the following hold:**
   - The winding is **fully enclosed by the core window** (no portion exposed to free air), so the magnetic field stays parallel to the foil.
   - The core has **no air gap**, or the air gap is very small and the foil can be placed **far from the gap** (distance-to-gap dwg ≥ 0.25·bF, where bF is the window width).
   - The foil **fills the window width** (bL ≈ bF). A short foil has reduced effective conductivity by the porosity factor η = NL·bL/bF and loses most of its advantage.
   - Higher winding capacitance is acceptable for the circuit (foil has more turn-to-turn capacitance than litz).

   When these conditions are met, foil beats litz because the "skin" area is larger for the same copper cross-section, reducing skin losses. Foil also has a higher fill factor and lower cost than litz.

   **Prefer LITZ when:**
   - The core has a significant air gap (typical for PSFB designs that tune Lmag with a shim). Air-gap fringing creates a field **orthogonal to foil**, which forces current to the foil edges and makes foil losses explode — potentially worse than solid round wire.
   - The winding is not fully enclosed by magnetic material.
   - Low winding capacitance is important.

   **Foil-specific warnings to pass to the user:**
   - If the user selects foil in a gapped design: **"Foil in gapped cores is risky — the air-gap fringing field is orthogonal to the foil and causes current to concentrate at the foil edges, dramatically increasing losses. Keep the foil at least 25% of the window width away from the gap, and use thin foil (thickness < skin depth at fsw). Consider litz instead if the gap is large."**
   - If the foil does not fill the window width: **"Foil width bL is less than window width bF — this reduces effective conductivity by the porosity factor η = NL·bL/bF. Either widen the foil to fill the window, or expect losses above the ideal foil value."**

   **Practical default for PSFB transformers:** litz wire is usually the safer starting point because most PSFB designs gap the core (shim) for Lmag control. Only recommend foil if the design is un-gapped or the foil can be kept far from the gap.

   **Only after all three checks are done** (interleaving applied, window occupation near 80%, conductor type appropriate), proceed to the design review.

#### Phase 3 — Design Review and Optimization

**Goal:** Evaluate the complete design (core + winding), determine a target loss balance from reference data, and iteratively optimize until viable or discard.

**CRITICAL: Apply ONE lever at a time. After each lever, simulate and check results. If the design is viable → STOP, design completed. If not → move to the NEXT lever. NEVER present multiple levers or options in a single message. NEVER skip a lever.**

9. **Review the full picture.** Ask the user to report:
   - Total losses (W) and temperature (°C)
   - Core losses (W) and winding losses (W)
   - Bpeak (mT)

10. **Determine the target core/winding loss balance.** Use TWO sources:
    - **Power density references (from Step 4):** Find the closest reference design in terms of topology, power level, frequency, and cooling. Note its core/winding loss split (e.g., 30% core / 70% winding). This is the benchmark from real-world designs.
    - **Thermal dissipation table (from Step 3):** Check which loss distribution (core-heavy, balanced, winding-heavy) gives the **highest total dissipation capacity** for this specific core and cooling condition.
    - **⚠️ IMPORTANT — Thermal capacity is a REFERENCE, not a hard limit.** The thermal table values represent the losses at ΔT = 75°C (ambient 25°C → max 100°C). The core CAN dissipate more losses than the table shows — it will simply run at a higher temperature. The real limit is the ferrite material's maximum operating temperature (typically ~120°C, higher for some materials like 3C92). **NEVER say** a core "can't handle" or "is at 117% of capacity" as if it's a failure. If total losses exceed the table capacity, the core runs hotter than 100°C — check the actual temperature in Frenetic to see if it stays below 120°C.
    - **Combine both:** The target balance should satisfy both — align with what similar real designs achieve AND maximize the core's thermal capacity. If they conflict, prioritize the thermal table (it's specific to this core).

    Present the target to the user: *"Based on the Infineon 3.3 kW reference (30/70 core/winding split) and the thermal table showing balanced distribution is optimal for PQ26/25, our target is approximately 35% core / 65% winding losses."*

11. **Apply optimization strategies** to move toward the target balance. Use ONE change at a time, ask the user to report results after each change. Track the iteration count.

    **Optimization lever 1 — Winding improvement (apply FIRST when winding losses are too high):**

    Assuming interleaving is already applied (from step 8). Optimize the litz wire strand diameter and number of strands using the `winding_optimizer` tool.

    **Procedure:**
    1. Ask the user for the current strand diameter (mm) and number of strands for the winding with the highest losses.
    2. Call `winding_optimizer` with the current diameter, strands, and switching frequency.
    3. The tool calculates the new configuration:
       - **For fsw > 99 kHz:** go directly to 0.05 mm strand diameter. The tool calculates the new number of strands to keep the same total copper area (same current density). Formula: `n_new = n_old × (d_old / d_new)²`.
       - **For fsw ≤ 99 kHz:** the tool proposes stepwise reductions through standard sizes. Apply one step at a time and ask the user to report skin and proximity losses after each change. Stop when losses stop improving.
    4. Ask the user to apply the new strand configuration in Frenetic and report: winding losses, skin losses, proximity losses, window occupation %.
    5. **If proximity losses are still high after strand diameter reduction** → the issue is interleaving arrangement, not strand diameter. Ask the user to rearrange layer positions.
    6. **If window occupation exceeds 85%** after increasing strands → the strands don't fit. Try one size larger diameter as a compromise.
    7. **High-frequency crossover (fsw ≳ 1 MHz):** above a certain frequency the internal proximity losses between strands dominate and litz can become *worse* than a single solid conductor of the same copper area. If fsw > 1 MHz and the losses do not improve after two strand-diameter reductions, litz is past its crossover for this design — suggest evaluating foil (if compatible with Check C) or accepting the current configuration.

    **Optimization lever 2 — Fill window to 85% (apply AFTER strand diameter optimization):**

    After optimizing the strand diameter, check the window occupation. If it is **below 80%**, there is room to add more copper to reduce winding losses further.

    **Procedure:**
    1. Ask the user to report **for each winding**: window occupation (%), current density (A/mm²), winding losses (W), and number of strands.
    2. Evaluate the balance across windings. The goal is to **distribute copper proportionally** — windings with higher current density or higher losses per turn need more strands. Do NOT add strands to only one winding.
    3. Propose a **small, balanced increment** of strands across windings. Prioritize the winding with the highest current density or highest losses, but also increase the others to keep window usage balanced. Example: if primary has 320 strands and secondary has 40, propose primary → 350, secondary → 44 (proportional increase).
    4. Ask the user to apply the changes in Frenetic and report: winding losses, current density, and window occupation % for each winding.
    5. **Repeat** until total window occupation reaches ~85% or winding losses stop improving.
    6. **Stop if** window occupation exceeds 85% — back off to the previous values.

    **Key:** Balance copper across all windings proportionally based on current density and losses — do not overload one winding while leaving others underutilized.

    **Optimization lever 3 — Try TDK equivalent material (apply AFTER winding optimization):**

    After optimizing the winding, try the equivalent material from TDK to see if core losses improve. Use this equivalence table:

    | Ferroxcube | TDK equivalent |
    |------------|---------------|
    | 3C90 | N87 |
    | 3C92 | N92 |
    | 3C95 | N95 |
    | 3C96 | N96 |
    | 3C97 | N97 |
    | 3F36 | N49 |

    **Procedure:**
    1. Identify the current Ferroxcube material used in the design.
    2. Look up the TDK equivalent from the table above.
    3. Tell the user: *"Let's try the TDK equivalent — change the material to [TDK material] in the Core tab and report the new core losses, Bpeak, and temperature."*
    4. Compare the results: if the TDK material gives lower core losses or better temperature, keep it. Otherwise, revert to the Ferroxcube material.

    **This is a quick check** — same core, same turns, just a different material from a different manufacturer. Small differences in the loss curves can make one material better than the other at specific frequency/temperature operating points.

    **Optimization lever 4 — Cooling negotiation (apply AFTER levers 1-3 if still not viable):**

    If after winding optimization, window fill, and material comparison the losses and temperature are still too high, the design is optimized from a magnetic standpoint. Now it's time to discuss cooling options with the user.

    **CRITICAL: Ask ONE question at a time. Wait for the user's answer before presenting the next option. NEVER list multiple cooling options in a single message.**

    **Present the situation first:**
    > *"The current design is optimized from a magnetic standpoint — we've reduced strand diameter, filled the window to 85%, and tried both Ferroxcube and TDK materials. Total losses are [X] W and temperature is [Y]°C, which is still above the [Z]°C target. Improving the cooling is the most effective path at this point."*

    **Then ask ONE question based on the current cooling condition:**

    **If current cooling is natural convection (no fan):**
    - Ask: *"Can you add a heatsink to the core? A heatsink is approximately equivalent to 1 m/s forced air cooling and would significantly improve heat dissipation."*
    - If yes → change cooling to forced air 1 m/s in Frenetic, re-simulate, check results. If viable → **done.** If not → proceed to next question.
    - If no → ask: *"Can you add a fan? Even a small fan at 1 m/s would help."*
    - If yes → change to forced air 1 m/s, re-simulate. If viable → **done.** If not → proceed to next question.

    **If current cooling is forced air (e.g., 1 m/s):**
    - Ask: *"Can you increase the airflow? Going from [current] m/s to [current + 1] m/s would increase the thermal capacity."*
    - Propose **incremental increases only** — e.g., 1 m/s → 2 m/s, not 1 m/s → 4 m/s. A jump from 1 to 4 m/s is a change in cooling technology, not an incremental improvement.
    - If yes → update airflow in Frenetic, re-simulate. If viable → **done.** If not → ask about next increment.

    **If forced air is maxed out or not enough:**
    - Ask: *"Is liquid cooling an option? Liquid cooling is approximately equivalent to 5 m/s forced air."*
    - If yes → change to 5 m/s in Frenetic, re-simulate. If viable → **done.**
    - If no → proceed to lever 5.

    **After each cooling change**, re-simulate and check if the design is now viable. If viable, the design is **completed**. If not, proceed to the next cooling question or the next lever.

    **Optimization lever 5 — Remove coil former (apply AFTER cooling negotiation if still not viable):**

    If after improving cooling the design is still over temperature, the next option is removing the coil former (bobbin). This is a **user decision** with significant tradeoffs.

    **Present the situation to the user:**
    > *"The design is still above the temperature target even with improved cooling. The next option is removing the coil former (bobbin). This improves thermal performance because the winding sits directly on the core, improving heat transfer. However, you should be aware of the implications:"*
    >
    > - **Production cost increases considerably** — without a coil former, the windings require much more manual labor to assemble
    > - **Not all manufacturers offer this option** — check with your manufacturer before committing to this approach
    > - **Would you like to proceed with a bobbin-less design?**

    If the user agrees:
    - Remove the coil former in Frenetic's Winding tab
    - Re-simulate and report the new temperature and losses
    - If the design is now viable → **design completed.** Record the result (noting it requires bobbin-less construction).
    - If still not viable → **put this design on hold** and continue with the next core. Do NOT discard — it may still be the best option after comparing all cores.

    If the user declines → **put this design on hold** and continue with the next core.

    **Optimization lever 6 — Electrical parameter negotiation (LAST RESORT):**

    If all previous levers have been exhausted and the design is still not viable, ask the user if any electrical parameters can be changed. These are parameters that affect the circuit design, so the user must decide.

    **Present the situation to the user:**
    > *"We've optimized the winding, tried alternative materials, improved cooling, and considered removing the coil former, but the design is still not meeting the temperature/loss target. The remaining option is to revisit the electrical specifications. Would any of these changes be possible in your circuit?"*

    **Parameters to discuss (in order of typical impact):**

    | Parameter | Effect on magnetic design | Tradeoff |
    |-----------|--------------------------|----------|
    | **Turns ratio** | Different ratio may allow fewer turns or better core/winding balance | Affects secondary voltage, rectifier selection |
    | **Magnetizing inductance (Lmag)** | Lower Lmag → fewer turns → less winding losses, but higher magnetizing current | More conduction losses in primary, but easier ZVS |
    | **Switching frequency** | Lower fsw → lower core losses, but larger core needed. Higher fsw → smaller core, but higher losses | Affects EMI, component selection, control loop |
    | **Max temperature rise (ΔT)** | Higher ΔT → more thermal headroom | Reliability, component derating |

    **For each parameter the user agrees to change:**
    1. Go back to Phase 1 with the new spec and re-run the full optimization (new turns, new winding, same core)
    2. If the design becomes viable → **design completed**
    3. If still not viable → **put on hold** and continue with the next core

    **IMPORTANT:** Never change electrical parameters without the user's explicit agreement. Always explain the tradeoff clearly. These are hard specs that affect the entire converter, not just the magnetic.

    **Optimization lever 7 — Custom core (to be defined):**

    If the user is open to a more expensive core, a custom core design can be explored. This is the most flexible option but comes with higher cost and longer lead times. **The procedure for custom core design will be defined in a future session.**

    For now, if all previous levers are exhausted, mention this option to the user:
    > *"There is one more option: designing a custom core tailored to your exact specifications. This is more expensive and has longer lead times, but it can achieve performance that standard cores cannot. Would you like to explore this in a future session?"*

    **NOTE:** The number of turns is fixed from Phase 1 unless the user agrees to change an electrical parameter (lever 6), which restarts the process for this core. The optimization levers in this phase are: strand diameter, window fill, material, cooling, coil former removal, electrical parameter negotiation, and custom core design.

    **After each optimization change**, ask the user to report the new total losses, core/winding split, and temperature. Then evaluate:
    - Are we closer to the target balance?
    - Are total losses decreasing?
    - Is temperature improving?

12. **Check VIABLE condition after each change:**

    ```
    IF temperature < 120°C AND total_losses ≤ loss_budget → ✅ VIABLE. Record and move to next core.
    IF temperature < 120°C AND total_losses ≤ loss_budget × 1.25 → ✅ PROMISING. Record and move to next core.
    ```

    If viable or promising, say:
    > "✅ [Core name] is **viable** — total losses [X] W, temperature [Y]°C. Recording this result and moving to the next core."

13. **DISCARD condition — after 3-4 optimization changes:**

    If after 3-4 optimization iterations the design is still far from the goal, **discard and move to the next core.** "Far from the goal" means:

    ```
    IF loss_budget ≥ 2 W: discard if total_losses > loss_budget × 1.30 (still 30% over)
    IF loss_budget < 2 W: discard if total_losses > loss_budget + 1.0 W (still 1 W over)
    ```

    Say to the user:
    > "❌ [Core name] — after [N] optimization attempts, total losses [X] W are still [Y]% over the budget of [Z] W. Discarding and moving to the next core."

    **Also discard immediately (without 3-4 iterations) if:**
    - Bpeak is at saturation (≥ Bmax) AND winding losses dominate — no room to adjust turns
    - Total losses are more than 2× the budget — too far to optimize

#### Key Rules for This Step
- **Start from the most aggressive (smallest) core** — if it works, the bigger ones will too
- **Always generate a complete winding** (SUGGEST WIRE + interleaving + window fill to 85%) before evaluating
- **Determine target loss balance** from power density references (Step 4) AND thermal table (Step 3)
- **One optimization change at a time** — report results after each
- **Rollback rule:** If a change produces WORSE results than the previous step, **revert it** — ask the user to undo the last change and go back to the previous configuration before trying the next lever. Never keep a change that made things worse. **Exception — material:** if a TDK equivalent (lever 3) gives better results than the original Ferroxcube material, **keep the better material** for all subsequent iterations. The material improvement carries forward even if you later revert other levers.
- **Apply levers in order:** strand diameter → window fill → TDK material → cooling → coil former → electrical params → custom core
- **Turns are fixed in Phase 1** — do NOT change turns during optimization (unless lever 6 restarts the process)
- **Discard after 3-4 failed optimizations** if still 30% over budget (or 1 W for budgets < 2 W)
- **Discard immediately** if total losses > 2× budget
- **On hold** (not discarded) if levers 5-6 are declined by the user — the design may still be the best after comparing all cores
- After finishing one core (viable, on hold, or discarded), **move to the next pre-selected core** and repeat from Phase 1

### Step 6: Final Comparison and Selection

After all pre-selected cores have been tested through Step 5, present a **side-by-side comparison** of all viable and on-hold designs.

**Include in the comparison table:**

| Parameter | Core A | Core B | Core C |
|-----------|--------|--------|--------|
| Core | name + family | name + family | name + family |
| Material | Ferroxcube or TDK | | |
| Turns (pri / sec) | | | |
| Core losses (W) | | | |
| Winding losses (W) | | | |
| Total losses (W) | | | |
| Temperature (°C) | | | |
| Bpeak (mT) | | | |
| Gap (mm) | | | |
| Window occupation (%) | | | |
| Power density (kW/L) | | | |
| Cooling required | | | |
| Coil former | yes / no | | |
| Dimensions (mm) | | | |
| Status | viable / on hold | | |
| Notes | any special requirements | | |

**Present the table and let the user choose.** Highlight the tradeoffs:
- Smallest core vs lowest temperature
- Standard construction vs bobbin-less
- Natural vs forced cooling requirements
- Cost implications (custom core, bobbin-less, strand diameter)

The user makes the final selection.

## Core Family Selection — ALWAYS Explore Multiple Families
**IMPORTANT: Never settle on a single core family without comparing at least 2-3 families.** Different families have different Ae/window area ratios and may offer better solutions.

### Recommended families for PSFB (500 W – 10 kW)
- **PQ** — Good balance of window area and core volume for transformers
- **E** — Widely available, many size options
- **ETD** — Similar to E but optimized for transformers, good thermal performance

Always add these three families to the Core Optimizer plot before selecting a candidate.

### Available families in Frenetic
ETD, ER, EP, PLANAR_ER, PQ, E, EFD, U, EQ, PM, P, PLANAR_E, EC, RM, UR, LP

### Custom cores
Custom core designs are also possible — covered in a separate lesson.

## Design Iteration and Spec Negotiation
Core selection is iterative. If results don't meet targets:
1. Adjust turns first (fewer turns → more core losses, less winding losses)
2. Propose negotiable spec changes to the user (turns ratio, Lmag, dimensions, ΔT, cooling, fsw)
3. Try different core sizes within the same family
4. Try different families (always compare PQ, E, ETD for PSFB)
5. Adjust loss budget (reconsider efficiency target)

**IMPORTANT: Never discard a core based on the Core Optimizer output alone.** The optimizer shows only core losses at one turns count. You MUST run Suggest Winding and check total losses before forming any opinion. Different turns counts completely change the core/winding loss balance.

**IMPORTANT: Always do a thermal pre-screening** using the thermal limits table before going to Frenetic. This filters out cores that can't handle the total losses under the specified cooling condition, saving time.

**IMPORTANT: Specs are negotiable.** Magnetic design is a collaborative process where the agent should propose spec tradeoffs to the user when they would significantly improve the design. Examples:
- "If we accept 5°C higher max temperature, we can use a smaller core"
- "Reducing fsw from 100 kHz to 80 kHz would cut core losses by 30%"
- "Relaxing dimensions by 5 mm allows a much better thermal design"
- "A slightly different turns ratio would eliminate a winding layer"

Always explain the tradeoff clearly and let the user decide. Never change specs unilaterally.

**Hard specs (almost never change):** Voltage, isolation requirements, power.

## Key Lessons

1. **Always start with worst-case OP** for core design (highest voltage)
2. **Thermal pre-screen** cores before going to Frenetic — eliminates non-viable options early
3. **Use conservative core loss target** in Core Optimizer (50-70% of budget) — shows more candidates
4. **Never judge a core from Core Optimizer alone** — always run Suggest Winding to get total losses
5. **The optimizer's turns count is just a starting point** — always iterate turns before deciding
6. **Fewer turns = less winding losses, more core losses** — this is the primary lever for balancing
7. **Explore multiple families** (PQ, E, ETD minimum for PSFB 500W-10kW)
8. **Don't assume unspecified parameters** — ask the user. Only default Tmax=110°C if nothing specified
9. **Specs are negotiable** — propose tradeoffs when they significantly improve the design
10. **Most designs >500W need active cooling** — flag this early
11. **Gap size matters** — very large gaps (>2 mm) are manufacturing concerns
12. **Thermal table capacity is a reference, not a limit** — the values are for ΔT = 75°C (100°C max). The core can run hotter. The real limit is the material's max temperature (~120°C). Always check actual temperature in Frenetic.
