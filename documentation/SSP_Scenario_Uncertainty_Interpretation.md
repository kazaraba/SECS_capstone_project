# Interpreting the SSP2-4.5 vs SSP5-8.5 Comparison — Notes on Scenario Uncertainty

Reference notes from a working discussion on how to correctly read the "raw vs. bias-corrected vs.
historical-trend baseline" panels in `seville_cmip6_projection_eda.ipynb` (both the SSP5-8.5 and
SSP2-4.5 versions), specifically the **"Reading the gap"** section and why its near-term
SSP2-4.5-vs-SSP5-8.5 comparison should *not* be read as a real scenario signal. Written up here so the
reasoning and its sources don't have to be re-derived later.

## 1. `tas_mean` vs. `t2m_mean` — same quantity, two names

Both columns represent the same physical measurement — annual mean near-surface (2 m) air
temperature — under two different dataset naming conventions:

- **`tas_mean`** — the CMIP6/projection-side name, derived from CMIP6's `tas` variable
  ("near_surface_air_temperature"), grid-averaged and converted K → °C, then annually averaged
  in `annual_summary` / `annual_summary_corrected`.
- **`t2m_mean`** — the ERA5/historical-side name, derived from ERA5's `t2m` variable
  ("2 metre temperature"), annually averaged in `era5_annual` (built by `seville_era5_eda.ipynb`).

The notebook maps them onto each other directly in Section 16:

```python
t2m_mean_compare = pd.DataFrame({
    "era5_historical": era5_annual["t2m_mean"],
    "cmip6_raw": annual_summary["tas_mean"],
    "cmip6_biascorrected": annual_summary_corrected["tas_mean"],
    ...
})
```

Note there are **two panels** comparing this same pair of series — the original `tas_mean` panel
(baseline: `mean_last_10yr`) and the "`t2m_mean`, revisited" panel further down (baseline:
`ols_full_history`). Not a duplicate by accident: `Climate_Indicators_Modeling.ipynb`'s later,
more rigorous walk-forward-CV analysis found `ols_full_history` to be the better-validated baseline
for this indicator, so the "revisited" panel supersedes the first panel's baseline choice without
deleting the original comparison.

## 2. The "Reading the gap" finding, in plain terms

The panel compares the bias-corrected CMIP6 projection against an ERA5 historical-trend
extrapolation. For the SSP2-4.5 Seville run, it found:

- The projection runs **warmer than the historical-trend extrapolation** by a larger margin than the
  SSP5-8.5 run did (+0.55 °C gap vs. +0.35 °C).
- The SSP2-4.5 run's own within-period warming trend is **statistically significant** (p = 0.01),
  where the SSP5-8.5 run's wasn't.

**Why this looks backwards:** SSP2-4.5 is the *lower*-emissions scenario, so intuitively it should
show *less* warming than SSP5-8.5, not more/more-confidently.

**Why it isn't actually a contradiction:** both runs come from the same climate model
(`cmcc_esm2`), and each is only **one single simulation** — one realization of that model's internal
weather variability, not an average over many. Near-term, SSP2-4.5 and SSP5-8.5 haven't forced the
climate system very differently yet (see §3), so most of what distinguishes the two runs in this
window is random simulation noise, not the emissions difference. Read the result as a fact about
these two specific model runs, not a scenario-ranking conclusion.

## 3. Why near-term scenario comparisons are unreliable — the general picture

Total projection uncertainty **does** grow the further out you project — that intuition is correct.
What changes over time is the *mix of what that growing uncertainty is made of*. Following the
standard decomposition (Hawkins & Sutton, 2009):

| Uncertainty source | What it is | How it evolves with lead time |
|---|---|---|
| **Internal variability** | Natural year-to-year/decade-to-decade noise (weather, ocean cycles) | Present from year one; grows only slowly |
| **Model uncertainty** | Different climate models respond differently to the same forcing | Grows steadily with lead time |
| **Scenario uncertainty** | Which emissions pathway actually happens | Starts near zero (scenarios haven't diverged yet); grows the *fastest*, eventually dominates |

Near-term (this project's 2026–2045 window), the total uncertainty cone is comparatively narrow, and
almost none of that width comes from "which SSP" — it's mostly internal variability and model
behavior. Late-century, the cone is much wider, and scenario disagreement is the largest slice of it.
Both "uncertainty grows over time" and "scenario differences barely matter yet" are true
simultaneously — they describe different parts of the same picture.

**More specific confirmation**, from the actual CMIP6 scenario design paper (O'Neill et al., 2021,
*ScenarioMIP*):

- Averaged across many models, SSP5-8.5's *ensemble-mean* trajectory separates from SSP2-4.5's
  starting around **the early-to-mid 2030s**.
- For any **individual model's single realization** — exactly this project's setup (one model, one
  run per scenario) — that separation is significantly delayed relative to the ensemble mean, with
  scenario trajectories staying confounded by internal variability "until the end of the century" in
  a large fraction of cases for precipitation, and substantially so for temperature too.

So the caveat already written into the notebooks (don't read the SSP2-4.5-vs-SSP5-8.5 gap as a
scenario signal at this horizon) is better-grounded than a generic hand-wave — it's the documented
behavior of exactly this kind of single-realization, near-term comparison.

## 4. Implications for modeling this going forward

Given the finding in §3, options for a more defensible treatment, roughly by cost:

1. **(Already mostly done, worth reinforcing)** Don't treat the SSP2-4.5-vs-SSP5-8.5 gap itself as
   evidence of anything scenario-related in the near term. Compare each scenario only against its
   own historical trend/baseline, and caveat any cross-scenario language accordingly.
2. ~~Pull additional CDS ensemble members of the same `cmcc_esm2` model (`r2i1p1f1`, `r3i1p1f1`, ...)
   for each scenario and average them.~~ **Checked and ruled out.** Two independent checks confirm
   this isn't available for this model:
   - The CDS `projections-cmip6` dataset's constraint API exposes no `ensemble_member`/`realization`
     field at all (`['experiment', 'level', 'model', 'month', 'temporal_resolution', 'variable',
     'year']` are the only constrainable fields) — the dimension isn't selectable through this
     dataset.
   - The underlying CMIP6 archive metadata (ESGF / WDC-Climate) shows CMCC only ever submitted a
     single realization, `r1i1p1f1`, for `cmcc_esm2`'s `ssp245` and `ssp585` ScenarioMIP runs. There
     is no second realization anywhere to pull — this is a gap in what CMCC produced, not a CDS
     access restriction.
   - Some other CMIP6 models do publish large ensembles for these scenarios (CanESM5, MIROC6,
     MPI-ESM1-2-LR are commonly cited with 10-50 members), but switching models would mean redoing
     the historical-run bias-correction baseline and losing the reason `cmcc_esm2` was chosen in the
     first place (the one model with daily wind published) — effectively option 4 below, not a small
     change.
3. **(Realistic next step, if pursued)** Extend the projection window out to where scenarios actually
   separate (mid-2030s onward per O'Neill et al.) — e.g., matching the existing SSP5-8.5 2026–2061
   extension (`extend_cmip6_projections_2046_2061.py`) for SSP2-4.5 too.
4. **(Biggest lift)** Add other CMIP6 models for a true multi-model ensemble, capturing model
   structural uncertainty as well as internal variability — a much larger data-pull and compute
   undertaking, probably out of scope for a capstone timeline.

## 5. Proposed follow-up study (separate project, not part of this capstone)

Option 2 is ruled out *for `cmcc_esm2`* specifically, because that model only published one
realization. It's a genuinely open, worthwhile question on its own terms, though: **does averaging
multiple realizations of the same model actually cancel internal-variability noise well enough to
extract a clean forced-response signal when working at this project's scale** — a single city-sized
grid box, a ~20-year near-term window — rather than the large-region, multi-decade scales at which
Hawkins & Sutton and O'Neill et al. demonstrate the effect? Smaller spatial averaging generally means
proportionally more internal-variability noise relative to signal, so it's plausible the "scenario
signal emerges" timing this project inherited from that literature is optimistic at city-scale — worth
checking rather than assuming.

**Proposed design, for a later, independent project:**

1. **Pick a model with a real ensemble for both scenarios.** CanESM5, MIROC6, and MPI-ESM1-2-LR are
   the usual candidates — confirm current member counts for `ssp2_4_5`/`ssp5_8_5` at daily resolution
   via the CDS constraints check used above before committing to one.
2. **Reuse this project's own pipeline end to end**, just parameterized to the new model: grid-average
   the same way (`cmip6_grid_processing.py`), bias-correct against ERA5 the same way
   (`bias_correct_cmip6_projection.py`), compute the same indicators (`tas_mean`, `tmax_mean`,
   `precip_total`, etc.) for Seville and/or Larissa — same cities, same 2026–2045 window, so results
   are comparable to what's already built here.
3. **Pull every available realization** (`r1i1p1f1`, `r2i1p1f1`, ... `rNi1p1f1`) for both scenarios,
   not just one.
4. **Quantify the noise-cancellation directly:**
   - For a given year, how much does the indicator vary *across realizations* of the same
     scenario (this is a direct empirical measurement of internal variability at this spatial/temporal
     scale) — compare that spread's size to the SSP2-4.5-vs-SSP5-8.5 gap this project measured from a
     single realization each.
   - Build the ensemble mean for each scenario from 1, 2, 4, 8, ... realizations and check how the
     apparent scenario gap and its statistical significance change as more realizations are averaged
     in — this directly shows how many realizations it actually takes to get a stable signal at this
     scale, rather than assuming the literature's answer transfers.
   - Compare the *single-realization* comparison (mimicking exactly what this project did with
     `cmcc_esm2`) against the *ensemble-mean* comparison for the same model, to put a number on how
     misleading a single-realization near-term scenario comparison actually is at this scale.
5. **Deliverable:** either a validated rule of thumb ("at city-scale/20-year windows, N realizations
   are enough to trust a scenario comparison") or a documented finding that this project's caveat
   (don't trust single-run near-term scenario gaps) needs to be even stronger than the general
   literature suggests, if a large ensemble at this scale still shows years of overlap.

This is scoped as its own project, not an extension of the current one — it needs a different model
(breaking the `cmcc_esm2`-everywhere consistency this project deliberately maintains) and a
substantially larger data pull (many realizations × many years × 7 variables × 2 cities).

## Sources

- Hawkins, E., & Sutton, R. (2009). [The Potential to Narrow Uncertainty in Regional Climate
  Predictions](https://journals.ametsoc.org/view/journals/bams/90/8/2009bams2607_1.xml). *Bulletin
  of the American Meteorological Society*, 90(8).
- O'Neill, B. C., et al. (2021). [Climate model projections from the Scenario Model Intercomparison
  Project (ScenarioMIP) of CMIP6](https://esd.copernicus.org/articles/12/253/2021/). *Earth System
  Dynamics*, 12(1).
