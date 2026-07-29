# Week 1 Status Check &amp; To-Do List

**Based on:** cross-checking `seville_era5_eda.ipynb`, `larissa_era5_eda` outputs (`eda_outputs_larissa/`), and `data/` against `week1_detailed_plan.md` and `capstone_task_plan.md`.

---

## Decision: historical/projection window

Historical record extends to **1990–2025** (full calendar years only — 2026 excluded to
avoid a partial year and not-yet-finalized ERA5T data). The **fixed reference period for
percentile thresholds stays 1990–2020**, unchanged, so extending the record doesn't let
the baseline "chase" recent warming. Projections shift to **2026–2045** to preserve the
project's 20-year outlook framing.

---

## What's already done (and where it exceeds plan)

- **CDS account/token working** &mdash; confirmed by successful historical pulls for both cities.
- **Bounding-box extraction, 1990&ndash;2020** &mdash; confirmed clean 2×2 grids: Seville (37.25°/37.50°N, -6.00°/-5.75°E), Larissa (39.50°/39.75°N, 22.25°/22.50°E). No gaps, no duplicates, strict 6-hourly cadence.
- **Full EDA pipeline, both cities** &mdash; far beyond the planned "first visual check": unit conversions, derived variables (RH, wind speed/direction, heat index, dewpoint depression), grid-point averaging, daily/monthly resampling, seasonality, diurnal cycle, decadal trend stats (OLS, Theil-Sen, Kendall's tau), fixed-threshold and percentile-based heatwave events, tropical nights, dry-spell stats, wind climatology, CSV exports. This covers most of what was scoped for Week 2&ndash;3.

## Gaps identified

- **Pre-built indicator catalog check was skipped.** Neither notebook nor `data/` shows any pull from `sis-ecde-climate-indicators` or the CEMS fire danger dataset &mdash; went straight to full raw ERA5 instead.
- **Data stops at 2020.** Both notebooks flag this. The project's own validation strategy needs the 2022 Seville heatwave and September 2023 Larissa drought→Storm Daniel event, both currently outside the data.
- **SPI for Larissa is not computed anywhere** &mdash; confirmed via `larissa_monthly.csv` / `annual_summary.csv` columns. This is the central hypothesis (H4) and the highest-priority missing piece.
- **Fire danger / FWI for Seville has zero presence** in the notebook &mdash; needed for H2 (compound fire risk).

---

## To-do list

1. [ ] Re-pull ERA5 for both cities extending through December 2025 (same variables, same bounding boxes) &mdash; full calendar years only, stopping short of 2026 to avoid partial-year distortion and preliminary ERA5T data. Append to existing historical files rather than redoing the full pull.
2. [ ] Re-run each notebook's sections 3&ndash;15 on the extended series &mdash; mostly re-executing existing cells, not new code.
3. [ ] Compute SPI-3 for Larissa from the extended `larissa_monthly.csv` (via `standard_precip` or a manual gamma fit). Confirm a clear negative dip before September 2023 &mdash; the validation checkpoint the plan says not to skip.
4. [ ] Build the Larissa volatility metric: minimum SPI per year vs. maximum single-week precipitation per year.
5. [ ] Pull Seville fire-weather data. Two options:
   - `sis-ecde-climate-indicators` (`origin: reanalysis`) for `days_with_high_fire_danger` and `fire_weather_index` at yearly resolution &mdash; quick annual-count cross-check, same call structure as the heatwave/tropical-nights pull.
   - The dedicated CEMS Fire danger historical dataset if daily FWI values are needed to correlate against daily heat+dryness for H2.
6. [ ] Optional, not blocking: pull `sis-ecde-climate-indicators` heatwave_days/tropical_nights for both cities as a sanity-check against the custom percentile-based numbers already in `annual_summary.csv`.
7. [ ] Only after 1&ndash;6: pull SSP5-8.5 projections (2026&ndash;2045) for both cities and apply the same thresholds/SPI logic anchored to the fixed 1990&ndash;2020 baseline. Reuse the existing `trend_table()` function.
8. [ ] Build the Seville-vs-Larissa comparison figure (steady escalation vs. widening volatility band) &mdash; the H5 centerpiece.
9. [ ] Write-up, limitations section, polish. Composite cross-city index only if time remains.
