# Southern European Climate Study (SECS): Modeling Climate Stress Indicators and Livability in Seville and Larissa

## Project Summary

A comparative climate risk analysis of two southern European cities — **Seville, Spain**
(heat and wildfire exposure) and **Larissa, Greece** (continental warming, drought, and
flood risk in the Thessaly agricultural plain, tracked as independent trends rather than
a single causal chain) — examining how climate stress indicators evolved from
1990–2025 and are projected to change through 2045 (2026–2045 projection window) under a
high-emissions scenario (SSP5-8.5). The project uses ERA5 reanalysis data, CMIP6/pre-built
Copernicus climate indicators, and custom drought (SPI) and flood-intensity indicators
built from precipitation extremes.

**Note on baseline vs. historical record:** the historical record now runs 1990–2025 (full
calendar years only — 2026 is excluded to avoid mixing in a partial year and
not-yet-finalized ERA5T data). Percentile-based thresholds (90th-percentile heatwave
definition, etc.) stay anchored to the fixed 1990–2020 reference period regardless of how
far the observed record extends, so the 2021–2025 years are tested against that baseline
rather than folded into it.

**Why these two cities:** They represent two distinct climate "failure modes" rather than
a single generic-warming narrative — Seville shows sustained, escalating heat stress,
while Larissa shows a broader, more comprehensive warming signature than Seville's,
alongside two separate hydrological risks: an independently intensifying wet extreme and a
drought signal that only emerges in the CMIP6 projections, not the observed record — a
historical-to-projected reversal (wetter, then sharply drier) that points toward Larissa's
mountain-flanked local geography shaping its precipitation story more than a simple
heat-driven compounding mechanism, arguably this project's most original finding (see H2
below). This project also tested a direct drought-primes-flood link for Larissa and found
no support for it — the two hydrological risks are presented as independent trends, not a
single volatility story.
**September 2023's Storm Daniel is the key historical precedent for the flood side**:
253mm in a single week, by far the record across the 36-year series (next-highest: 156mm,
1998) — real evidence of what Larissa's flood risk can produce, and the reference event
the ensemble item in "Future Work" below is aimed at resolving more precisely.

---

## Hypotheses to Test

1. **H1 — Heat-driven fire escalation (Seville):** Escalating heat drives drier
   conditions, which in turn fuel more frequent, more dangerous, and longer-duration
   wildfire risk over time — a causal chain (heat ↑ → dryness ↑ → fire danger/duration ↑),
   not three independent trends.

   *Evidence so far:* the heat leg and the heat+dryness→fire leg are both confirmed.
   Daytime heat escalation is significant (`tmax_mean` +0.38°C/decade, p=0.0002), and the
   compound-predictor test shows combined heat + same-day humidity explains fire danger
   (FWI) significantly better than heat alone (ΔR²=+0.17, 95% CI excludes zero) — with one
   precision worth keeping in the write-up: it's *same-day* atmospheric dryness
   (`rh_min`) doing the work, not accumulated 3-month drought (SPI-3 was actually the
   *weakest* of the tested predictors). The "longer-duration fires" leg is the weakest so
   far — the historical duration proxy (`longest_high_run`) trends up but isn't
   significant (p=0.129), and while both projection scenarios show more high/extreme fire
   danger days (Seville +14–22 days/year by 2026–2045, some categories statistically
   distinguishable from baseline noise under SSP5-8.5), the within-projection trend itself
   isn't significant either (p>0.5) — read today as "an elevated new normal," not yet a
   demonstrated accelerating trend.

2. **H2 — Larissa's continental heat signature, decoupled from a drought/precipitation
   trend masked by the valley's local geography:** Larissa's heat exposure is broader and
   more intense than Seville's because it is coupled with a continental climate signature
   — colder, more sheltered winters; wider seasonal swing; less oceanic moderation.

   *Evidence:* **Confirmed.** Every season shows significant warming, day and night
   (`tmin_mean` +0.42°C/decade, p<0.0001, vs. Seville's flat nights), and the climatology
   fingerprint matches the textbook continental signature (colder January mean, 5.1°C vs.
   Seville's 10.6°C; wider annual amplitude, 21.7°C vs. 17.1°C).

   *What we originally expected, beyond the confirmed heat claim:* that this same
   continental-heat intensity would compound the way it does for Seville's fire risk —
   heat escalation driving the valley progressively drier, priming the kind of short,
   intense flash flood Larissa saw with Storm Daniel, rather than steady drying alone.

   *What we actually found — and the real discovery for Larissa:* that compound chain
   doesn't hold, and the way it fails is itself the interesting result. Historically,
   Larissa is trending significantly *wetter* (+51.8mm/decade, p=0.0071) with milder
   droughts (+0.18/decade) — the opposite of the heat-drives-drying expectation. The
   CMIP6 projections then reverse that signal entirely, swinging to extreme drought under
   both scenarios (−2.28 to −2.45 vs. −1.31 historical mean). A trend flipping sign this
   sharply between the observed and modeled record is suspicious on its own — and
   Larissa's geography gives a concrete reason to suspect why: the plain sits tightly
   flanked by the Pindus range to the west and Mt. Pelion/Ossa to the east, exactly the
   kind of orographic setting a ~100km CMIP6 grid cell can't resolve (ERA5's box is a
   tight 0.25° cell on the plain itself; `cmcc_esm2`'s much coarser grid was widened to
   `[40.6, 21.15, 38.6, 23.75]` just to get multiple points, spanning onto that
   surrounding terrain). **Rather than a confirmed heat→dryness→flood mechanism, the
   standout finding for Larissa is that local geography may be shaping its precipitation
   story more than any single compounding climate driver — worth testing directly (the
   grid-resolution and ensemble follow-ups under Future Work below) before treating the
   projected drought reversal as a real signal.**

   Larissa's flood risk (Storm Daniel, 253mm in a single week, September 2023) is tracked
   as a fully separate trend from drought either way — a direct drought→flood link was
   tested and is not supported (r=−0.047, p=0.788).

3. **H3 — Divergent regional risk (cross-city):** The two cities' climate stress
   profiles diverge in *character*, not just magnitude — southern Europe's climate risk
   is geographically heterogeneous, not a single uniform "getting worse" story.

   *Evidence so far:* the best-supported hypothesis in the project. Framed with Seville as
   "the heat city" and Larissa as "the drought/volatility city," the data instead shows
   Larissa has the more complete, more statistically robust heat signature of the two
   (every season, both day and night, both distribution tails), while its "drought" side
   doesn't hold up in the historical record at all — a sharper, more specific form of
   divergence than originally framed.

*H1 and H2 replace the project's original five-hypothesis structure (formerly H1–H4). H1 is
a full causal chain (heat→dryness→fire), confirmed. H2's confirmed claim is scoped to heat/
continental-climate only — the compound heat→dryness→flash-flood mechanism originally
expected for Larissa (mirroring Seville's confirmed fire mechanism) did not hold, and the
specific way it failed — a historical wetting trend that reverses into extreme drought
under CMIP6 projection — is kept as Larissa's headline open finding rather than folded into
H2 as settled: it points toward local orography/grid-resolution interaction as a more
interesting, still-unverified explanation than a simple compounding climate driver. The
flood link was tested directly and rejected, independent of that question. H3 is the
former H5, unchanged, and remains the strongest, most original contribution.*

---

## Datasets

| Purpose | Dataset | Cities | Period |
|---|---|---|---|
| Historical baseline (temp, precip, wind, RH) | `reanalysis-era5-single-levels` (CDS) | Both | 1990–2025 |
| Fixed reference period for percentile thresholds | Same dataset, subset in analysis | Both | 1990–2020 |
| Pre-built climate indicators (check first — may cover heatwave/tropical night calcs already) | `sis-ecde-climate-indicators` (CDS) | Both | 1940–2100 |
| Raw projections (fallback if pre-built indicators don't cover it) | `projections-cmip6`, SSP5-8.5 scenario, `ec_earth3` model | Both | 2026–2045 |
| Fire danger, historical | CEMS Fire danger historical dataset (CDS) | Seville | 1990–2025 |
| Fire danger, projected | "Fire danger indicators for Europe" (RCP4.5/8.5, FWI-based) | Seville | 2026–2045 |
| Precipitation for SPI | Same ERA5 pull as baseline (`total_precipitation` variable); optional E-OBS cross-check | Larissa | 1990–2025 |

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
Pull SSP5-8.5 projection data for 2026–2045 (or use pre-built indicators through 2045); apply the same
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
  frequency and tropical-night counts across the 1990–2025 historical record, with the
  trend continuing (and plausibly steepening) in the 2026–2045 projection — consistent with
  published findings that southern Europe, and Iberia specifically, is warming faster
  than the global average and is already setting individual national heat records.
- **Seville fire risk:** Fire danger index values that track more closely with combined
  heat-and-dryness periods than temperature alone, supporting H1's heat→dryness→fire chain
  and giving you a concrete compound-risk chart rather than a single-variable one.
- **Larissa:** A historical SPI series with a clear, sharp negative dip in the months
  preceding September 2023, validating the pipeline — though drought and flood turned out
  not to move together: drought only emerges as a concern in the CMIP6 projections, while
  flood intensity is increasing independently in the observed record, and a direct
  drought→flood link tested negative. Reported as two separate findings, not one
  volatility story.
- **Cross-city comparison:** Two visibly different risk "shapes" when plotted side by
  side — a steady, narrow upward slope for Seville vs. broad, comprehensive warming for
  Larissa — which is the visual anchor for H3 and the centerpiece figure of the final
  report.
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

---

## Future Work

- **Test the grid-resolution hypothesis directly** (H2's caveat above): re-run the Larissa
  CMIP6 grid average using only the 1–2 points nearest the plain (39.11°N or 40.05°N ×
  22.50°E) instead of the full 6-point unweighted average, redo bias correction and SPI-3,
  and check whether the projected extreme-drought signal softens — separates "real
  projected drying" from "coarse-grid terrain dilution."
- **Move from a single model run to an ensemble.** Every projection here comes from one
  model (`cmcc_esm2`), one realization, no ensemble spread — repeating the SSP2-4.5/SSP5-8.5
  pulls against 2-3 additional CMIP6 models would show whether Larissa's projected
  drought-category jump is a genuine multi-model signal or a `cmcc_esm2`-specific artifact.
  Complementary to the grid-resolution check above, not a substitute: resolution affects the
  *level*, model choice affects the *spread*. This matters directly for the flood side too:
  Storm Daniel (September 2023, 253mm in a single week — by far the record in the observed
  series) is the historical precedent for how extreme Larissa's precipitation signal can
  get, and one model run isn't enough to say how likely a repeat is — an ensemble is the
  right tool for resolving that precipitation signal with real confidence.
- Extend the SPI-3 drought pipeline to Seville's own projections, for a like-for-like
  historical-vs-projected drought comparison in both cities.
- Composite cross-city index and a third city, both cut from scope above, remain natural
  extensions if the project continues past the capstone deadline.
