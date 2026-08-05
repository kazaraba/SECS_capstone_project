# FWI Seville

Background reference for `seville_fire_eda.ipynb` — what the Fire Weather Index is, how it's
computed, and what each caveat in that notebook's intro cell actually means. Written for someone
with no prior familiarity with the data.

---

## What is FWI, and how is it computed?

The **Canadian Forest Fire Weather Index (FWI) System** estimates fire danger from **weather
alone** — no fuel type, vegetation, or topography input. Originally developed by the Canadian
Forest Service, it's the most widely used fire-danger rating system globally, and it's what EFFIS
(the European Forest Fire Information System) and Copernicus CEMS use for Europe. The data used in
`seville_fire_eda.ipynb` comes from **GEFF** (Global ECMWF Fire Forecasting model) — ECMWF's
implementation that drives the Canadian system with ERA5 weather instead of Canadian station
observations, which is how a consistent global/European grid is produced.

### The four weather inputs

All taken at **local noon** — this is why comparing FWI against a daily max or 6-hourly ERA5 mean
matters: those are different quantities, not noise (see caveat 1 below).

- Temperature (°C)
- Relative humidity (%)
- Wind speed (km/h)
- 24-hour accumulated precipitation (mm)

### The six components, in three layers

**Layer 1 — three fuel moisture codes**, each representing a different fuel layer with a different
drying speed ("memory"):

| Code | Represents | Time constant | Meaning |
|---|---|---|---|
| **FFMC** (Fine Fuel Moisture Code) | Surface litter — leaves, twigs, needles | ~16 hours | Fast-responding; short-term ignition potential |
| **DMC** (Duff Moisture Code) | Loosely compacted organic layer | ~12 days | Medium memory; smoldering/spread potential |
| **DC** (Drought Code) | Deep, compact organic layer | **~52 days** | Long memory; seasonal drought effect, how hard deep fuel is to extinguish |

Each is computed **recursively**: today's value depends on yesterday's value plus today's
weather — rain wets the fuel back down (a rain-response formula), dry noon conditions dry it out
further (an exponential-decay-style formula). This recursive, long-memory structure is exactly the
mechanism behind caveat 2 below — DC's ~52-day time constant is precisely why lag-1 autocorrelation
of the daily FWI series comes out above 0.9.

**Layer 2 — two intermediate indices**, combining the codes with wind:

- **ISI** (Initial Spread Index) = FFMC + wind speed → expected rate of fire spread
- **BUI** (Build-Up Index) = DMC + DC → total fuel available to feed a fire

**Layer 3 — the final index:**

- **FWI** = ISI + BUI → overall fire intensity, the general fire-danger number in the
  `fire_weather_index` column

---

## Walking through the notebook's intro cell

### Source

- **`cems-fire-historical-v1`** is the specific dataset name in Copernicus's catalogue — the
  product ID for "historical fire danger data."
- It's hosted on the **CEMS Early Warning Data Store**, a *different* website/API from the CDS
  (Climate Data Store) that the temperature/precipitation ERA5 data elsewhere in this project came
  from. Different portal means a separate registration and a separate API key.
- **GEFF model forced by ERA5**: GEFF is the fire-danger calculation engine described above.
  "Forced by ERA5" means ERA5's temperature/humidity/wind/precipitation fields are what feed into
  it as input weather.
- **`system_version=4_1`, `dataset_type=consolidated_dataset`, `product_type=reanalysis`**: the
  exact settings used when this data was downloaded — like a receipt. `consolidated_dataset` means
  the finalized, quality-checked version (not a preliminary/near-real-time cut); `reanalysis` means
  it's built from ERA5's best reconstruction of actual past weather (not a forecast); `4_1` pins
  the model version, since results can shift slightly between GEFF versions.

### Spatial averaging

The fire values are averaged over the same four grid cells (a 2×2 box around 37.25–37.50°N,
−6.00 to −5.75°E) used for Seville's temperature/humidity analysis elsewhere in the project. This
is a deliberate consistency choice — it removes *location* as a source of mismatch between the
fire data and the heat/precipitation data: both describe the exact same patch of ground, so any
difference between them isn't because one dataset is secretly looking somewhere else.

This is a **spatial** consistency guarantee only — it says nothing about *time*. It does not
override caveat 1: two series can be perfectly aligned in space (same grid box) and still
misaligned in time (noon snapshot vs. daily max/6-hourly mean), which is exactly the case here.
Comparing FWI to another ERA5 statistic on the same calendar day still requires the noon-vs-daily
adjustment caveat 1 describes — matching locations doesn't fix a timing mismatch.

### Production

`fetch_seville_fire.py` is the script that built the CSV this notebook loads, in two steps:
`fwi-download` (pull the raw data from CEMS) then `fwi-subset` (cut it down to just Seville's grid
box).

### Caveat 1 — noon-referenced

FWI is calculated from weather *at local noon only* — not a daily max, not a 6-hourly average. So
plotting FWI against, say, ERA5's daily maximum temperature isn't comparing two views of the same
day — it's comparing a snapshot at one specific hour against a different statistic entirely. The
mismatch doesn't average out over many days ("noise"); it pushes every comparison the same
direction ("systematic"), because it's always the same kind of mismatch.

### Caveat 2 — the data has far fewer independent observations than it looks like

Three of FWI's building blocks (the moisture codes above) are computed recursively — each day's
value is built from *yesterday's* value plus today's weather. The slowest of these, the Drought
Code, has roughly a 52-day "memory": a dry spell's effect on it lingers for weeks. That means
today's FWI and next week's FWI aren't independent facts — they're heavily related, because they
share most of the same recent-weather history baked in.

"Lag-1 autocorrelation above 0.9" is the concrete measurement of that: today's value predicts
tomorrow's value with over 90% correlation. Practically: even though the dataset has about 13,000
calendar days (36 years), there aren't 13,000 *independent* pieces of evidence — effectively more
like a few hundred, because long stretches of consecutive days are really just restating the same
underlying drought or wet spell.

Why this matters: standard statistical tests (like a textbook correlation p-value) assume every
data point is independent. Feeding 13,000 highly-correlated daily values into one of those tests
would report a wildly overconfident result — a tiny p-value implying near-certainty, when the real
uncertainty (based on the true, much smaller number of independent observations) is far larger.
That's why the notebook uses a **moving-block bootstrap** instead for any correlation involving
FWI — a resampling method that shuffles data in contiguous chunks (blocks) rather than individual
days, so it doesn't accidentally treat correlated days as independent.

### Caveat 3 — `days_fwi_gt30` vs. the EFFIS classes are different definitions

FWI is a single number, typically ranging from around 0 up to 50+, where higher means more
dangerous fire weather. The notebook counts "how many days per year were dangerous" in two
different, incompatible ways:

- **ECDE's definition**: a flat cutoff — any day where FWI is above **30** counts as a "high fire
  danger day."
- **EFFIS's definition**: a six-tier graded scale —

  ```
  very low (0) → low (5.2) → moderate (11.2) → high (21.3) → very high (38.0) → extreme (50.0)
  ```

  where "high" specifically means FWI is between **21.3 and 38.0**.

These don't agree, because ECDE's cutoff of 30 doesn't line up with any EFFIS boundary — it falls
awkwardly *inside* EFFIS's "high" band (21.3–38.0) rather than at its start or end. Concretely:

- A day with FWI = 25 counts as "high" under EFFIS, but is **excluded** from ECDE's count (25 is
  not above 30).
- A day with FWI = 45 — which EFFIS would call "very high," a worse category — still just gets
  lumped into ECDE's single "above 30" bucket, indistinguishable from a milder FWI = 31 day.

Because EFFIS's "high" starts lower (21.3) than ECDE's cutoff (30), the EFFIS count will generally
report *more* dangerous days than the ECDE count, for the exact same year of data. A claim like
"Seville had 40 days of high fire danger in 2022" is meaningless without knowing which definition
produced it — neither is "more correct," they're just different yardsticks. The notebook computes
both (`days_fwi_gt30`, `days_high_effis`, `days_very_high_effis`, `days_extreme_effis`) side by
side rather than picking one and presenting it as *the* count.

### The ECDE annual cross-check

The plan was: ECDE (a separate Copernicus data catalogue) has its own pre-built annual fire
statistics — if they roughly match the numbers computed in this notebook, that's reassuring
evidence the CEMS/GEFF pipeline is working correctly.

The catch: according to ECDE's own documentation, those specific variables
(`days_with_high_fire_danger`, `fire_weather_index`) aren't actually built from real historical
weather at all — they come from a **climate *projection* model** (EURO-CORDEX, the kind of model
used to simulate *future* climate scenarios out to 2098), statistically adjusted
("bias-corrected") to roughly resemble real FWI values over 1981–2010, but fundamentally a
different kind of data product — model-simulated, not observation-driven.

Two consequences:

1. Requesting these ECDE variables with `origin='reanalysis'` (i.e., "give me the real-weather
   version") may not even be a valid request — the data might not exist under that label.
2. Even if a series is returned, comparing it to the CEMS data in this notebook isn't "checking
   against ground truth" — it's comparing two different model pipelines that both happen to
   describe historical fire danger. Agreement wouldn't prove the CEMS numbers are right, and
   disagreement wouldn't prove they're wrong.

That's why the notebook's final cell reports the **bias** (the systematic difference) between the
two series if the ECDE file exists, rather than treating a match as validation. `python
fetch_seville_fire.py ecde-check` is a separate command that checks ECDE's documented constraints
before attempting the comparison.

---

## Key findings (as of the 1990–2025 record, no hypothesis framing)

Everything below is what the FWI data itself shows, computed in `seville_fire_eda.ipynb`. Numbers
are pulled directly from that notebook's executed output, not re-derived from memory.

### Headline: every FWI metric points toward escalation, but none reach statistical significance on their own

| Metric | OLS slope/decade | OLS p-value | Right direction? |
|---|---|---|---|
| `fwi_mean` | +0.41 | 0.387 | Yes |
| `fwi_season_mean` (Jun–Sep) | +0.47 | 0.429 | Yes |
| `fwi_p95` | −0.03 | 0.959 | No — essentially flat |
| `days_fwi_gt30` (ECDE-style count) | +4.2 days | 0.256 | Yes |
| `days_high_effis` (FWI > 21.3) | +3.5 days | 0.389 | Yes |
| `days_very_high_effis` (FWI > 38.0) | +2.1 days | 0.585 | Yes |
| `longest_high_run` | +6.0 days | **0.129** | Yes |
| `first_high_doy` (season start) | −2.4 days | 0.645 | Yes — starting earlier |
| `last_high_doy` (season end) | +5.2 days | **0.167** | Yes — ending later |
| `high_season_span` | +7.6 days | 0.232 | Yes — widening |
| `drought_code` (season mean) | +9.9/yr | 0.658 | Yes |

None clear the conventional p < 0.05 threshold. This is the central, honest finding of the fire
side of the project: fire-danger escalation in Seville is **directionally consistent but not yet
statistically proven** across 36 years of data — a materially weaker statistical footing than the
heat side of the story (see the comparison section below).

### The two most statistically compelling FWI indicators: `longest_high_run` and `last_high_doy`

Ranked by p-value, these two sit closest to significance of everything tested (0.129 and 0.167
respectively — still not significant, but the least noisy of the eleven metrics above). What they
have in common is the interesting part: **both are duration/timing metrics, not intensity or
day-count metrics.** The strongest signal in this dataset isn't "each dangerous day is more
dangerous" (that would show up in `fwi_mean` or `fwi_p95`, which are the *weakest* signals here) or
"there are more dangerous days scattered through the year" (`days_high_effis`, `days_fwi_gt30` —
also weaker). It's that when danger arrives, it **lasts longer once it starts**
(`longest_high_run`) and **sticks around later into the calendar year** (`last_high_doy`). That's a
more specific, more operationally meaningful story than a generic "fire risk is rising," and it's
the framing worth leading with if only two FWI numbers can be cited.

### The fire season is visibly widening in the decade-level view, even where the annual trend is noisy

Decade-mean high-danger season span (first day to last day with FWI > EFFIS "high," 21.3):

```
1990s: 224.3 days  →  2000s: 218.3  →  2010s: 227.8  →  2020s: 240.2
```

A real ~16-day widening from the 1990s to the 2020s, driven by both an earlier start and later end.
The individual linear-trend p-values for `first_high_doy`/`last_high_doy`/`high_season_span` don't
clear 0.05, but the decade-block pattern is visible by eye — consistent with a real but still-noisy
signal, not an artifact.

### No recent clustering of the worst years — the record doesn't look like a steady climb

Worst years by mean FWI: **2005 (26.3), 2012 (25.3), 1995 (25.0), 2009 (24.6), 2019 (24.2)**.
Mildest: **1996 (15.7), 2018 (16.2), 1993 (16.7)**. The two most recent years — **2024 (17.5) and
2025 (17.0)** — sit near the *low* end of the entire 36-year range. The worst years are scattered
across the whole record, not concentrated recently, which is the concrete reason the linear trends
above come out noisy rather than clearly rising.

### What drives day-to-day FWI

Spearman ρ, using the day-of-year-anomaly framing — the one that actually tests same-day
relationships rather than shared seasonality:

| Predictor | ρ vs. FWI anomaly | Notes |
|---|---|---|
| `rh_min` (daily min relative humidity) | **−0.560** | Strongest driver — dryness matters more than heat |
| `t2m_max` (daily max temperature) | +0.402 | Second strongest |
| `tp_mm` (daily total precipitation, scaled) | −0.238 | Weakest, but still real |

All three bootstrap confidence intervals exclude zero (robust, not spurious). All three peak at
**lag 1 day**, not lag 0 — FWI responds slightly more to *yesterday's* heat/dryness than today's, a
small hint of accumulation on top of the ~52-day Drought Code memory.

**Conditional-probability view:** a hot day (t2m_max > 34.1°C, the 90th percentile) makes "high
danger" 2.32× more likely across the full year — but restricted to the fire season itself
(Jun–Sep), where the baseline rate is already 0.911, the marginal lift shrinks to 1.09×. Heat's
predictive power operates mostly at the "is it fire season" scale, not for distinguishing
dangerous-vs-extra-dangerous days once summer has arrived.

### Why the trends are this noisy: effective sample size

Daily FWI's lag-1 autocorrelation is **0.925**, and the autocorrelation function still hasn't
dropped below 0.2 even 60 days out (caveat 2, explained above). That converts the nominal 13,149-day
sample into an effective sample of roughly **513 independent observations (3.9%)**. This is the
direct, quantified reason none of the trend p-values above reach significance despite 36 years of
daily data.

### What's not yet available

The ECDE annual cross-check is currently skipped — `data/seville_ecde_fire_annual_1990_2025.csv`
doesn't exist on disk yet, so there's no independent bias estimate against these CEMS/GEFF numbers.

---

## Comparison to the heat-side findings (`seville_era5_eda.ipynb`)

For reading side by side later. These come from the separate ERA5 temperature/humidity notebook,
not the fire notebook — included here so both stories are in one place.

| Metric | Slope/decade | p-value | Significant? |
|---|---|---|---|
| `tmax_mean` (annual mean daily max temp) | +0.38°C | **0.0002** | **Yes** |
| `days_tmax≥30°C` | +6.2 days | **0.003** | **Yes** |
| `heat_index_mean` | +0.23°C | 0.006 | **Yes** |
| `t2m_mean` (annual mean temp) | +0.22°C | 0.0062 | **Yes** |
| `t2m_p95` (warm tail) | +0.33°C | 0.034 | **Yes** |
| Heatwaves (P90, ≥3 days) | +3.9 days | 0.041 | **Yes** |
| `days_tmax≥33°C` | +4.6 days | 0.042 | Borderline yes |
| `days_tmax≥35°C` | +3.0 days | 0.115 | No |
| Tropical nights (tmin≥20°C) | **−2.7 days** | 0.248 | No — wrong direction |

**The core contrast between the two notebooks:** the heat side of Seville's story (temperature,
heat index, hot-day counts at moderate thresholds) has **six metrics that clear p < 0.05** and a
seventh that's borderline. The fire/drought side (FWI, its EFFIS thresholds, Drought Code) has
**zero** metrics that clear p < 0.05 — the best is `longest_high_run` at p = 0.129. Heat escalation
in Seville rests on solid statistical ground; fire-danger escalation is directionally consistent
with it but not yet statistically confirmed on its own, and needs more years of record (or a
different indicator choice — see "the two most statistically compelling FWI indicators" above) to
close that gap.

One more genuine tension worth carrying into the write-up: tropical nights — one of H1's two named
indicators in the project hypothesis — currently shows a **non-significant negative** trend in the
Seville record, the one heat-side metric that doesn't fit the "escalating heat" pattern the other
temperature metrics show.
