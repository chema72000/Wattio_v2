# Ferroxcube Material Selection Guide

## Overview
Guide for selecting the correct Ferroxcube ferrite material based on switching frequency and operating temperature. The agent MUST propose a material from the start and explain why it is the best choice for the user's specifications.

## Materials Available in Frenetic Simulator
Only these materials can be used: 3C90, 3C91, 3C92, 3C92A, 3C94, 3C95, 3C95A, 3C95F, 3C96, 3C97, 3C98, 3C99, 3F3, 3F36, 3F4, 3F46, 4F1

## Selection Criteria

Materials are organized along 4 axes based on their strengths:

### Wide Temperature Range (25–100°C+)
Best when the design must work across a wide ambient temperature range.

| Material | Frequency Range | Temperature Range | Notes |
|----------|----------------|-------------------|-------|
| **3C95F** | up to 400 kHz | 25–100°C | Wide temperature variant of 3C95 |
| **3C95A** | up to 400 kHz | 25–100°C | Wide temperature variant of 3C95 |
| **3C97** | up to 600 kHz | 25–100°C | Extended frequency vs 3C95 |
| **3C95** | up to 200 kHz | 25–100°C | General purpose, most common choice |

### Temperature Optimized (best at specific temperature)
Best when the operating temperature is well-defined and stable.

| Material | Optimized for | Frequency Range | Notes |
|----------|--------------|----------------|-------|
| **3C91A** | 25°C | 250 kHz at 100/200 | Not available in Frenetic |
| **3C91** | 60°C | 300 kHz at 100/200 | Best at moderate temperature |
| **3C96** | 100°C | 250 kHz at 100/200 | Best at high temperature |
| **3C98** | 100°C | 250 kHz at 100/200 | Best at high temperature |

### High Frequency (>200 kHz)
Best for designs with high switching frequency.

| Material | Frequency Range | Temperature Range | Notes |
|----------|----------------|-------------------|-------|
| **4F1** | up to 1–10 MHz | 25–100°C | Very high frequency |
| **3F46** | up to 1–3 MHz | 25–90°C | High frequency |
| **3F36** | 0.5–2 MHz | 25–100°C | Power applications at high frequency |
| **3F4** | up to 2 MHz | — | High frequency |
| **3F3** | up to 1 MHz | — | High frequency |

### High DC Stability
Best when there is a significant DC bias (e.g., inductors, flyback transformers).

| Material | Frequency Range | Temperature Range | Notes |
|----------|----------------|-------------------|-------|
| **3C92** | up to 400 kHz | 25–100°C | Good DC stability |
| **3C92A** | up to 400 kHz | 25–100°C | Improved DC stability |
| **3C99** | up to 400 kHz | up to 200°C | High DC stability + high temp |

### General Purpose
| Material | Notes |
|----------|-------|
| **3C90** | Standard ferrite, lower performance than 3C95, legacy designs |
| **3C94** | Similar to 3C95, some designs may prefer it |

## Decision Flowchart

The agent should follow this logic to recommend a material:

### 1. Check switching frequency first
- **fsw > 1 MHz** → **4F1** (only option for very high frequency)
- **fsw = 500 kHz – 1 MHz** → **3F3** or **3F46**
- **fsw = 200 kHz – 500 kHz** → **3F36**, **3C97**, or **3C96/3C98** (depends on temperature)
- **fsw ≤ 200 kHz** → **3C95** — then check temperature and DC bias below to see if a different material is better

### 2. Check temperature requirements
- **Wide ambient range (field equipment, automotive)** → **3C95** or **3C95A/3C95F**
- **Operates mostly at high temperature (>80°C)** → **3C96** or **3C98**
- **Operates mostly at moderate temperature (~60°C)** → **3C91**

### 3. Check for DC bias
- **Significant DC bias (inductors, flyback)** → consider **3C92**, **3C92A**, or **3C99**
- **No DC bias (transformer in PSFB, LLC, DAB)** → stay with selection from step 2

## How the Agent Should Present the Material Selection

When recommending a material, the agent MUST:
1. State which material it recommends
2. Explain WHY based on the user's frequency, temperature, and application
3. Mention what alternatives exist and when they would be better

**Example:**
> "For your design at 100 kHz with 25°C ambient and 105°C max temperature, I recommend **3C95**. It's the standard power ferrite for frequencies up to 200 kHz with good performance across 25–100°C. If your design later requires operation mostly above 80°C, **3C96** would be a better choice as it's optimized for high-temperature operation."

## Key Rules
1. **Always propose a material from the beginning** — never default to 3C95 without explanation
2. **Only recommend materials available in Frenetic** — see the list above
3. **Frequency is the primary selector** — materials have hard frequency limits
4. **Temperature is the secondary selector** — among materials that cover the frequency, pick the one matching the thermal profile
5. **Material can be changed during optimization** — if a different material would improve the design, propose it as a spec negotiation
