# Frenetic Simulator: PSFB Transformer Core Selection Guide

## Overview
Step-by-step guide for selecting a transformer core for a Phase-Shifted Full-Bridge (PSFB) converter (full-wave or center-tap secondary) using Frenetic simulator.

## Required Input Specifications

### Minimum (mandatory)
- Ambient Temperature — T (°C)
- Magnetizing Inductance — Lmag (µH)
- Switching Frequency — fsw (kHz)
- Input Voltage — Vin (V), can be a range (min/max)
- Output Current Ripple — Io Ripple (A), per operating point
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
- Choose **"Transformer"** from: Inductor, Transformer, Flyback, Active Clamp Flyback
- Click **"CONTINUE"**

### Step 3: Select Topology
- Choose the correct PSFB variant:
  - **"PSFB Secondary Full Wave Rectifier"** — for full-wave (bridge) secondary rectification
  - **"PSFB Secondary Center Tap"** — for center-tap secondary rectification
- Other available topologies: Custom, Full Bridge LLC, Half Bridge LLC, CLLC, Dual Active Bridge
- Click **"CONTINUE"**

### Step 4: Define Operating Points
- Create multiple operating points using **"Add OP"** when:
  - The output voltage is a range (different Vo per OP)
  - The input voltage is a range (different Vin per OP)
  - Different load conditions exist (different Po per OP)
- Each operating point may have different Vin, Vo, Io Ripple, and Output Power
- **The worst case for the core is always the highest voltage** (either Vin or Vo depending on topology)

### Step 5: Fill Waveform Tab
For each operating point, enter:
- Left side: T, Lmag, fsw, Vin, Io Ripple, Converter Output Power
- Right side: m2 (turns ratio), Vout, Power
- Frenetic automatically generates the waveforms from the topology and inputs

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
4. Split transformer losses: 50% core, 50% winding

### Step 8: Core Optimizer — CRITICAL: Start with Worst-Case Operating Point

**IMPORTANT: Always identify and start with the worst-case operating point for the core.**
- The worst case for the core is always the **highest voltage** operating point (higher voltage → higher volt-seconds → higher Bpeak → higher core losses)
- Designing for the easy OP first and discovering the hard OP later wastes time

In the Core Optimizer tab:
1. Select goal: **"Core Loss Target (W)"** from the dropdown
2. Enter a **conservative (lower) core loss target** — use about 50-70% of the calculated budget. A tight target shows MORE candidates on the plot because the optimizer finds solutions with lower losses across more core sizes. A loose target can filter out smaller cores that can't reach that loss level, hiding good options.
3. Select Family Shape (e.g., PQ, E, RM)
4. Select Material (e.g., 3C95 for ~100 kHz)
5. Click to add cores and compare

### Step 9: Handle "No Solution" for Lmag
If Frenetic shows "No solution close to target inductance":
- The Lmag value is too high for the selected cores
- Ideal Lmag is infinite (minimizes magnetizing current losses)
- If Lmag is very high → user likely NOT targeting ZVS → safe to reduce
- Propose Lmag ≈ 1 mH as a starting point
- If 1 mH doesn't work, decrease further
- Always ask the user before changing Lmag

### Step 10: Evaluate Core Candidates

#### Bpeak Guidelines (for ferrite materials like 3C95)
- Maximum recommended Bpeak for 3C95: **200 mT**
- Recommended range for aggressive designs: **180–200 mT**
- Conservative designs: **< 180 mT**
- If Bpeak is too high: increase turns (reduces Bpeak but may reduce inductance)

#### Power Density Guidelines
- < 20 kW/L: Standard design, free convection OK
- 20–50 kW/L: High optimization, needs enhanced thermal (resins, potting)
- > 50 kW/L: Extreme optimization, requires liquid cooling
- **Most designs above 500 W need some heat dissipation method** (forced air, potting, heatsink), otherwise designs become too large
- Use the heat dissipation capacity table per core to evaluate cooling needs

#### Gap Size Guidelines
- Very small gaps (< 0.1 mm) are difficult to control in manufacturing
- Prefer gaps ≥ 0.1 mm for production reliability

#### Turns Ratio Constraint
- Primary and secondary must have integer turns
- For ratio n1/n2 = 3.5, valid pairs: 7-2, 14-4, 21-6, 28-8, 35-10
- After selecting a core, adjust turns to nearest valid pair using **"LAUNCH CALCULATOR"**

### Step 11: Adjust Turns with Calculator
- In Core tab, click **"LAUNCH CALCULATOR"**
- Set new number of turns
- Calculator adjusts gap to maintain target inductance
- Click **"CALCULATE"** then **"APPLY"**

### Step 12: Create Initial Winding
- Go to Winding tab
- Set correct turns for Primary and Secondary
- Click **"SUGGEST WIRE"** for initial winding (will optimize later)
- This is needed so the simulator can calculate full losses

### Step 13: Verify Both Operating Points
- Check Core tab under both OP1 and OP2
- Ensure Bpeak and core losses are acceptable in both cases
- The worst-case OP drives the design; the other OP should be well within limits

### Step 14: Present Core Proposals
After evaluating all candidates from the Core Optimizer:
- Present **3 proposals** to the user, each with real data: core name, turns, core losses, Bpeak, dimensions, inductance, gap, power density
- Include thermal validation against the cooling method and ΔT
- Categorize proposals (e.g., conservative/balanced/compact or with spec negotiation)
- Flag any proposals that require spec changes (e.g., different cooling)

### Step 15: Detailed Comparison — Run Each Proposal Through Full Design
After the user approves the proposals, guide them to **create a separate design in Frenetic for each proposal** and complete the full design flow:

For each proposal:
1. **Apply** the core from the Core Optimizer
2. **Adjust turns** in the Core tab using Launch Calculator to match valid integer turn pairs for the turns ratio
3. **Create winding** (Winding tab → set correct primary and secondary turns → Suggest Wire)
4. **Run simulation** to get full results: core losses, winding losses, total losses, Bpeak, temperatures
5. **Verify all operating points**
6. **Check thermal limits** — compare simulated total losses against the thermal dissipation capacity for the selected core and cooling method

Then present a **side-by-side comparison table** of all proposals with:
- Core losses (W) per OP
- Winding losses (W) per OP
- Total losses (W)
- Bpeak (mT) per OP
- Max temperature (°C)
- Dimensions (mm)
- Power density (kW/L)
- Thermal margin (Pmax total - actual total losses)
- Gap size (manufacturability)
- Cost/availability considerations

This allows the user to make an informed final decision based on complete data, not just core optimizer estimates.

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
1. Try different core sizes within the same family
2. Try different families (always compare PQ, E, ETD for PSFB)
3. Adjust turns (more turns → lower Bpeak, but harder to fit winding)
4. Adjust Lmag (lower → easier core selection, but more magnetizing current)
5. Adjust loss budget (reconsider efficiency target)

**IMPORTANT: Never discard a core candidate just because Bpeak is slightly above limit at the optimizer's suggested turns count.** Turns can always be adjusted later in the Core tab to bring Bpeak down. Evaluate cores on their overall potential (dimensions, core losses, gap), not just the initial Bpeak value.

**IMPORTANT: Always do a thermal pre-screening** using the thermal limits table before going to Frenetic. This filters out cores that can't handle the total losses under the specified cooling condition, saving time.

**IMPORTANT: Specs are negotiable.** Magnetic design is a collaborative process where the agent should propose spec tradeoffs to the user when they would significantly improve the design. Examples:
- "If we accept 5°C higher max temperature, we can use a smaller core"
- "Reducing fsw from 100 kHz to 80 kHz would cut core losses by 30%"
- "Relaxing dimensions by 5 mm allows a much better thermal design"
- "A slightly different turns ratio would eliminate a winding layer"

Always explain the tradeoff clearly and let the user decide. Never change specs unilaterally.

## Key Lessons

1. **Always start with worst-case OP** for core design (highest voltage)
2. **Thermal pre-screen** cores before going to Frenetic — eliminates non-viable options early
3. **Use conservative core loss target** in Core Optimizer (50-70% of budget) — shows more candidates
4. **Never discard cores** for slightly high Bpeak — turns can be adjusted later
5. **Explore multiple families** (PQ, E, ETD minimum for PSFB 500W-10kW)
6. **Don't assume unspecified parameters** — ask the user. Only default Tmax=110°C if nothing specified
7. **Specs are negotiable** — propose tradeoffs when they significantly improve the design
8. **Most designs >500W need active cooling** — flag this early
9. **Gap size matters** — very small gaps (<0.1mm) are manufacturing concerns
10. **Complete the full design flow** for each proposal before making final comparison — Core Optimizer data alone is not enough
