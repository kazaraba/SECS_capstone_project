# Southern Europe Climate Livability Capstone — Realistic Solo Plan (1 Month)

**Cities (narrowed to 2):** Seville, Spain (heat/wildfire) · Larissa, Thessaly, Greece (drought-to-flood volatility)
**Why these two:** Together they cover 3 of your original 4 themes (heat, wildfire, drought, and — uniquely — volatility) and Larissa is your most original, defensible angle. Dropping Po Valley and Évora to full-context mentions (a paragraph each, no pipeline) keeps the story of "risk isn't uniform across southern Europe" without doubling your workload.
**Scenario:** One only — SSP5-8.5 (higher-emissions / "if current trends continue"). Skip the SSP1-2.6 comparison; mention in your limitations section that scenario uncertainty exists but wasn't in scope.
**Data strategy:** Use Copernicus's **pre-built European climate indicator products** wherever they exist (heatwave days, tropical nights, SPI, fire danger) instead of computing from raw ERA5/CMIP6. This removes the hardest parts of the original plan — regridding, custom index math, model debugging — while still giving you real, citable, defensible numbers. Only fall back to raw ERA5 pulls for anything not already pre-computed.
**Composite cross-city index:** Dropped from core scope. Only attempt it in week 4 if you're ahead of schedule.

---

## Week 1: Setup + historical baseline data

1. Create CDS account, set up API token
2. Search the CDS catalog for **pre-computed indicator datasets** first:
   - "European climate indicators" / "Climate indicators for Europe" (heatwave days, tropical nights, frost days, etc.)
   - "Fire danger indices" (Copernicus EFFIS/CEMS product — historical + projected fire weather, already computed)
   - "Standardised Precipitation Index" products if available, or the E-OBS precipitation dataset if you need to compute SPI yourself
3. If a needed indicator isn't pre-built, pull raw ERA5 for just that one variable (e.g., precipitation for Larissa) rather than the full variable set from the original plan
4. Extract data for Seville and Larissa bounding boxes only, 1990–2020
5. Load into pandas, do a first visual check: plot raw temperature/precipitation time series for both cities — confirms your download actually worked before you build anything on top of it

**Milestone by end of Week 1:** two clean historical dataframes (Seville, Larissa), each plotted and sanity-checked.

## Week 2: Historical indicators + validation

6. Seville: compute/extract heatwave-day counts and tropical-night counts per year (pre-built dataset or ≥3-day-streak-above-90th-percentile if computing yourself)
7. Seville: extract fire danger index annual high-risk-day counts (pre-built dataset — don't build FWI from scratch, it's not worth the time cost for a 1-month solo project)
8. Larissa: compute SPI (3-month) from precipitation — this is the one genuinely custom calculation worth keeping, since it's central to your volatility story; there are existing Python packages (e.g., `climate_indices` or `standard_precip`) that implement SPI so you're not writing the statistics from scratch
9. Larissa: identify the 2023 drought-to-Storm-Daniel event in your own data as a validation check — if your SPI series doesn't show a clear dip before September 2023, debug before moving on
10. Build your simple volatility metric: minimum SPI value in a year vs. maximum single-week precipitation in the same year — a scatter or dual-axis line chart, not a complex derived index

**Milestone by end of Week 2:** validated historical indicators for both cities, with the 2022 Seville heatwaves and 2023 Larissa drought-flood both visible in your own computed data. This is your proof the pipeline works.

## Week 3: Projections + trend analysis

11. Pull the same pre-built indicators (or raw variables) for 2025–2045, SSP5-8.5, same two cities
12. Apply the same indicator calculations to the projected data (reuse Week 2 code/thresholds — don't recompute the 90th-percentile baseline on projected data, keep it anchored to 1990–2020)
13. Basic time series analysis on both historical and projected series: a linear trend line (simple `numpy.polyfit` or `scipy.stats.linregress` is enough — you don't need ARIMA or anything advanced) to quantify "X more heatwave days per decade"
14. Plot historical + projected together, 1990–2045, one chart per indicator per city (should be ~4-5 charts total: Seville heatwaves, Seville tropical nights, Seville fire risk, Larissa SPI, Larissa volatility)

**Milestone by end of Week 3:** every core chart done, each with a clear "before vs. after" trend number you can state in a sentence.

## Week 4: Write-up + polish

15. Write the comparison narrative: Seville = steady heat escalation, Larissa = increasing volatility, not just decline — this contrast is your capstone's actual argument
16. Add the Po Valley/Évora context paragraph (cite the documented 2022 Po drought and Portuguese wildfire/reservoir issues from published sources — no pipeline needed, just supports your "risk isn't uniform" framing)
17. Write the explicit scope/limitations section: one scenario only, two cities only, indicator-based rather than full climate-model-ensemble approach — stating this clearly reads as rigor, not weakness
18. Final pass on chart labels/titles/legends — this is cheap polish that meaningfully affects how professional the final product looks
19. If (and only if) you're ahead of schedule: attempt the composite index or add a third city

**Milestone by end of Week 4:** finished report/notebook with narrative, charts, and limitations section — done.

---

## What got cut from the original plan, and why
- **4 cities → 2 cities:** each additional city roughly doubles debugging surface; Po Valley and Évora become citation-supported context instead
- **2 scenarios → 1 scenario:** SSP1-2.6 vs SSP5-8.5 comparison is a nice-to-have, not core to answering "is it getting worse"
- **Custom Fire Weather Index → pre-built Copernicus fire danger data:** building FWI from scratch is a multi-day task on its own; not worth it against a 1-month deadline
- **Composite cross-city index → dropped to stretch goal:** it's the most complex, least essential piece — only build it if everything else is done early
- **ARIMA/advanced time series → simple linear trend:** with basic time series experience, a defensible trend line beats a poorly-understood advanced model every time in a capstone review
