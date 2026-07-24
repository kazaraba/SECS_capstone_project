# From Drought to Deluge: Modeling Climate Volatility and Livability Risk in Southern Europe

## Project Summary

A comparative climate risk analysis of two southern European cities — **Seville, Spain**
(heat and wildfire exposure) and **Larissa, Greece** (drought-to-flood volatility in the
Thessaly agricultural plain) — examining how climate stress indicators evolved from
1990–2020 and are projected to change through 2045 under a high-emissions scenario
(SSP5-8.5). The project uses ERA5 reanalysis data, CMIP6/pre-built Copernicus climate
indicators, and a custom volatility metric built from precipitation extremes.

**Why these two cities:** They represent two distinct climate "failure modes" rather than
a single generic-warming narrative — Seville shows sustained, escalating heat stress,
while Larissa demonstrates that the more dangerous emerging pattern in parts of southern
Europe may be *swings between extremes* (severe drought followed by catastrophic
flooding, as seen with Storm Daniel in September 2023) rather than steady drying alone.

---

## Hypotheses to Test

1. **H1 — Heat escalation (Seville):** Heatwave frequency (≥3 consecutive days above the
   90th-percentile historical threshold) and tropical nights (min temp ≥20°C) show a
   statistically significant upward trend 1990–2020, continuing/accelerating under
   SSP5-8.5 through 2045.

2. **H2 — Compound fire risk (Seville):** Fire danger index values correlate more
   strongly with combined heat+dryness conditions than with temperature alone —
   wildfire risk is better predicted by a compound indicator than by heat data alone.

3. **H3 — Drought severity (Larissa):** The 3-month SPI series for Thessaly shows
   increasing frequency and/or severity of drought values over the historical record.

4. **H4 — Volatility, not just drying (Larissa — central hypothesis):** Climate
   instability in Thessaly — measured as severe drought followed within the same year by
   extreme precipitation — is increasing in frequency, meaning the region's central risk
   is *swing magnitude* rather than a simple drying trend. Directly testable against the
   documented 2023 drought→Storm Daniel sequence.

5. **H5 — Divergent regional risk (cross-city):** The two cities' climate stress
   profiles diverge in *character*, not just magnitude — southern Europe's climate risk
   is geographically heterogeneous, not a single uniform "getting worse" story.

*H4 and H5 are the strongest, most original contributions — they go beyond restating
known warming trends into a specific, testable claim about volatility and regional
heterogeneity.*

---

## Datasets

| Purpose | Dataset | Cities | Period |
|---|---|---|---|
| Historical baseline (temp, precip, wind, RH) | `reanalysis-era5-single-levels` (CDS) | Both | 1990–2020 |
| Pre-built climate indicators (check first — may cover heatwave/tropical night calcs already) | `sis-ecde-climate-indicators` (CDS) | Both | 1940–2100 |
| Raw projections (fallback if pre-built indicators don't cover it) | `projections-cmip6`, SSP5-8.5 scenario | Both | 2025–2045 |
| Fire danger, historical | CEMS Fire danger historical dataset (CDS) | Seville | 1990–2020 |
| Fire danger, projected | "Fire danger indicators for Europe" (RCP4.5/8.5, FWI-based) | Seville | 2025–2045 |
| Precipitation for SPI | Same ERA5 pull as baseline (`total_precipitation` variable); optional E-OBS cross-check | Larissa | 1990–2020 |

**Scope note for the write-up:** the fire danger projections use RCP scenarios
(CMIP5-era), not SSP5-8.5 (CMIP6-era) — roughly comparable in severity but not
technically the same framework. Worth one sentence in the limitations section.

---

## Main Tasks

**Week 1 — Setup + historical data**
Register CDS access; pull ERA5 historical data for both cities; check whether
`sis-ecde-climate-indicators` already covers needed indicators; load and sanity-check
raw time series.

**Week 2 — Historical indicators + validation**
Compute Seville heatwave-day and tropical-night counts; pull/compute fire danger index;
compute Larissa 3-month SPI using `standard_precip` or `spei`; validate against known
events (2022 Seville heat, 2023 Larissa drought→flood) — do not proceed until these show
up clearly in your own computed data.

**Week 3 — Projections + trend analysis**
Pull SSP5-8.5 projection data (or use pre-built indicators through 2045); apply the same
indicator logic to projected data using the same historical baseline thresholds; fit
simple linear trends (not advanced time series models); produce before/after comparison
charts for each indicator.

**Week 4 — Write-up + polish**
Write the comparative narrative (steady escalation vs. volatility); add brief
Po Valley/Évora context paragraphs from published sources (no pipeline needed); write
an explicit limitations section; polish chart labels/titles; attempt stretch goals only
if ahead of schedule.

---

## Expected / Potential Results

- **Seville:** A visible, likely statistically significant upward trend in both heatwave
  frequency and tropical-night counts across the historical record, with the trend
  continuing (and plausibly steepening) in the 2025–2045 projection — consistent with
  published findings that southern Europe, and Iberia specifically, is warming faster
  than the global average and is already setting individual national heat records.
- **Seville fire risk:** Fire danger index values that track more closely with combined
  heat-and-dryness periods than temperature alone, supporting H2 and giving you a
  concrete compound-risk chart rather than a single-variable one.
- **Larissa:** A historical SPI series with a clear, sharp negative dip in the months
  preceding September 2023, validating the pipeline, alongside a broader pattern of
  increasingly large swings between SPI minimums and maximum short-window precipitation
  totals — the core evidence for the volatility hypothesis (H4).
- **Cross-city comparison:** Two visibly different risk "shapes" when plotted side by
  side — a steady upward slope for Seville vs. a widening oscillation band for Larissa —
  which is the visual anchor for H5 and the centerpiece figure of the final report.
- **Honest caveat to state upfront:** with two cities, one model, and one scenario, these
  results are illustrative of directional risk rather than definitive climate-model
  consensus — appropriate framing for a capstone, and worth saying explicitly rather than
  overclaiming.

---

## What Got Cut From the Original Scope (and why)
- 4 cities → 2 cities (debugging surface roughly doubles per added city)
- 2 emissions scenarios → 1 (SSP5-8.5 only)
- Custom-built Fire Weather Index → pre-built Copernicus fire danger data
- Composite cross-city index → stretch goal only, attempted last if time allows
- Advanced time series modeling (e.g. ARIMA) → simple linear trend fitting
