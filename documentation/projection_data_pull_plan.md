# Projection Data Pull: SSP5-8.5, 2026–2045

## Corrections after live testing (2026-08-07)

This plan was originally written from the CDS web form and documentation, without submitting a
live request. Actually running it surfaced three assumptions that didn't hold up, plus a model
choice that turned out not to exist for this variable set. All four are corrected below; the
"Decisions locked in" section at the bottom and `pull_cmip6_projections.py` reflect the corrected
version, not the original plan text further down this document (left intact for the record, but
superseded where it conflicts with this section).

**1. `ec_earth3` (bare) does not exist for this variable set.** Confirmed by pulling the live
`projections-cmip6` constraints file and filtering for `temporal_resolution=daily`,
`experiment=ssp5_8_5`, and each of the six originally-planned variables: the bare `ec_earth3`
model id never appears. Only `ec_earth3_cc` and `ec_earth3_veg_lr` exist, and neither offers
`near_surface_wind_speed` at daily resolution. This is what the `RoocsValueError` the first
real request threw actually meant — not a transient server issue (it also failed instantly on
retry, and failed identically with `ensemble_member` added and with much larger bounding boxes,
which ruled out the other two hypotheses tried first).

**2. `near_surface_relative_humidity` does not exist at daily resolution, for any model.**
Confirmed the same way: filtering the live constraints for `temporal_resolution=daily` and
`experiment=ssp5_8_5` returns exactly seven variable names, and RH is not one of them — only
`near_surface_specific_humidity` is. RH now has to be derived (see Step 3 below).

**3. `projections-cmip6` silently keeps only the first variable in a multi-variable request.**
This is the most dangerous of the three, because it does not error — it would have silently
produced a file containing only temperature data, for all six requested variables, with no
warning. Confirmed by direct test: requesting `[temperature, precipitation]` in one call returned
only temperature; reversing the order to `[precipitation, temperature]` returned only
precipitation. `download()` in the script now issues one request per variable per city (7 per
city) instead of one bundled request per city.

**4. Model comparison and final choice: `cmcc_esm2`, not `ec_earth3` or `mpi_esm1_2_lr`.**
Of the models offering all 7 needed variables (using specific humidity + sea-level pressure
instead of RH) at daily SSP5-8.5 resolution, two were evaluated as EC-Earth replacements —
`cmcc_esm2` (Italian CMCC, Euro-Mediterranean Centre on Climate Change) and `mpi_esm1_2_lr`
(Max Planck Institute, Germany), both plausible "European, Mediterranean-relevant" substitutes
for the original EC-Earth rationale. Rather than pick by reputation, both were tested directly
against the project's own ERA5 data: pulled 2010–2014 daily `near_surface_air_temperature` from
the CMIP6 `historical` experiment (the overlap period between CMIP6 historical and the ERA5
record) for both models at both cities, and compared the mean to the actual ERA5 2010–2014 mean
(computed from `seville_era5_combined_1990_2025.csv` / `larissa_era5_combined_1990_2025.csv`):

| Model | Seville bias vs. ERA5 | Larissa bias vs. ERA5 | Grid points in bounding box |
|---|---|---|---|
| **cmcc_esm2** | +0.88 K | +0.97 K | 4 / 6 |
| mpi_esm1_2_lr | −3.36 K | −1.17 K | 1 / 1 |

`cmcc_esm2` runs under 1 K warm at both cities. `mpi_esm1_2_lr` runs meaningfully cold (over 3 K
at Seville), and its native grid is coarse enough that the bounding box only contains a single
grid point at either city — no spatial-averaging redundancy the way ERA5's original 4-point boxes
had. `cmcc_esm2` is the clear choice on both counts and is the model locked in below.

**5. Bounding boxes widened to fit `cmcc_esm2`'s native grid.** `cmcc_esm2`'s grid is
~0.94° latitude × 1.25° longitude — much coarser than ERA5's 0.25°, and far coarser than the
original boxes were sized for (those were sized to guarantee exactly 4 ERA5 grid points, and
turned out to contain *zero* `cmcc_esm2` grid points, which was the proximate cause of every
early failed request once the model/variable issues above were fixed). The new boxes are sized
to roughly 2× the native grid spacing around each city center and were verified, by counting
actual returned grid points, to contain multiple points:

- Seville: `[38.4, -7.25, 36.4, -4.65]` (was `[37.6, -6.2, 37.2, -5.7]`) → 4 grid points
- Larissa: `[40.6, 21.15, 38.6, 23.75]` (was `[39.8, 22.2, 39.4, 22.7]`) → 6 grid points

---

## Key finding before starting

`sis-ecde-climate-indicators` (the pre-built indicator dataset used to cross-check historical
heatwave/tropical-night counts) **does not offer SSP5-8.5 projections** for any temperature,
precipitation, or fire-danger indicator — confirmed by checking every entry in its constraints
file. SSP5-8.5 only appears there for two unrelated sea-level variables. Its projection indicators
are RCP4.5/RCP8.5 only (CMIP5-era EURO-CORDEX), which is a different modeling framework than
SSP5-8.5 (CMIP6).

Since the project is explicitly scoped around SSP5-8.5, this means the projection pull has to go
through **raw CMIP6 data** (`projections-cmip6`) rather than a pre-built shortcut — the same
"pull raw, then compute your own indicators" pipeline already built for ERA5, just pointed at a
different dataset.

---

## What's different from the historical ERA5 pipeline

| | Historical (ERA5) | Projections (CMIP6) |
|---|---|---|
| Dataset | `reanalysis-era5-single-levels` | `projections-cmip6` |
| Native resolution | 0.25° grid, 6-hourly | Varies by model, **daily** is the finest available here |
| tmax/tmin | Approximated from 4 daily samples (undercounts true range — noted in both EDA notebooks) | **True daily max/min**, provided directly as their own variables — no approximation needed |
| Precipitation units | `tp`, meters accumulated per hour | `precipitation`, a **flux in kg m⁻² s⁻¹** — needs ×86400 to get mm/day, not the ×1000 conversion used before |
| Relative humidity | Derived from t2m/d2m via Magnus formula | Also **derived** via Magnus formula, from `near_surface_specific_humidity` + `near_surface_air_temperature` + `sea_level_pressure` — `near_surface_relative_humidity` was assumed available directly but does not exist at daily resolution for any model (see Correction 2) |
| Grid alignment | Fixed 0.25° ERA5 grid, matches existing bounding boxes exactly | Model-native grid, resolution varies by model — the same bounding box coordinates work as a subset request, but the returned grid points will *not* line up with the ERA5 2×2 grid |

---

## Step-by-step plan

**1. CMIP6 model: `cmcc_esm2`, used for both cities.**
Superseded from the original `ec_earth3` choice — see "Corrections after live testing" above for
why `ec_earth3` doesn't exist for this variable set, and the bias comparison against ERA5 that
selected `cmcc_esm2` over the other EC-Earth-family and Max-Planck alternatives considered. This
choice is locked in for all projection requests below.

**2. Submit one CDS request per variable per city** — not one bundled request per city as
originally planned. `projections-cmip6` silently keeps only the first variable in a
multi-variable request (see "Corrections" above), so each of the 7 variables below needs its own
`retrieve()` call. `pull_cmip6_projections.py`'s `download()` implements this as a loop; the shape
of a single request is:

```python
import cdsapi

c = cdsapi.Client()

MODEL = "cmcc_esm2"          # corrected choice -- see "Corrections after live testing" above
EXPERIMENT = "ssp5_8_5"
YEARS = [str(y) for y in range(2026, 2046)]   # 2026-2045, 20 years
MONTHS = [f"{m:02d}" for m in range(1, 13)]

VARIABLES = [
    "near_surface_air_temperature",               # mean 2m-equivalent temp
    "daily_maximum_near_surface_air_temperature",  # true daily tmax
    "daily_minimum_near_surface_air_temperature",  # true daily tmin
    "precipitation",                               # flux, kg m-2 s-1 -- needs unit conversion
    "near_surface_specific_humidity",              # RH not available daily -- derive it instead
    "near_surface_wind_speed",                     # direct wind speed, no u/v combination needed
    "sea_level_pressure",                          # needed only to derive RH from specific humidity
]

for variable in VARIABLES:                        # one request per variable -- see Correction 3
    c.retrieve(
        "projections-cmip6",
        {
            "temporal_resolution": "daily",
            "experiment": EXPERIMENT,
            "variable": [variable],
            "model": MODEL,
            "year": YEARS,
            "month": MONTHS,
            "area": [38.4, -7.25, 36.4, -4.65],   # Seville -- widened for cmcc_esm2's native grid
        },
        f"seville_{variable}.nc",
    )
    # ... and again with area = [40.6, 21.15, 38.6, 23.75] for Larissa
```

No `ensemble_member` field exists in this dataset's request schema (confirmed against the live
constraints — the field simply isn't present for any model/variable/experiment combination
checked). Passing one anyway is silently accepted as a no-op; it is not required and not used.

**3. Convert units on load, including deriving relative humidity.**
`precipitation` is a flux, not an accumulation: multiply by 86,400 to get mm/day. This is a
*different* conversion than the historical `tp × 1000` used for ERA5 — reusing the old conversion
here would silently produce precipitation totals off by several orders of magnitude. Relative
humidity is no longer available directly (see Correction 2) and is derived from
`near_surface_specific_humidity` + `near_surface_air_temperature` + `sea_level_pressure` via the
Magnus formula, the same method the ERA5 pull used from t2m/d2m — sea-level pressure stands in
for true surface pressure since both cities sit near sea level, a mild approximation rather than
an exact substitution.

**4. Skip the grid-averaging step (or adapt it) — CMIP6's grid isn't the ERA5 grid.**
The historical pipeline's Section 5 (averaging 4 grid points into one city value) assumed the
ERA5 0.25° grid specifically. `cmcc_esm2`'s native grid is ~0.94° × 1.25° (see Correction 5) —
the widened bounding boxes contain 4 (Seville) and 6 (Larissa) grid points, not the ERA5 pull's
uniform 4, so the averaging step should adapt to whatever count is actually present rather than
assuming 4.

**5. Apply the existing, fixed 1990–2020 thresholds — don't refit anything.**
This is the same fixed-reference-period principle already established for SPI and the percentile
thresholds: the CMIP6 projection data gets *scored* against the thresholds already derived from
the ERA5 historical baseline (90th-percentile heatwave threshold, tropical-night threshold, etc.),
never used to redefine them.

**6. State the bias-correction limitation explicitly, rather than skipping past it.**
Raw CMIP6 output at a single grid cell is known to carry systematic biases relative to
reanalysis-based observations — a model's own "normal" for Seville or Larissa may run warmer,
cooler, wetter, or drier than ERA5's, independent of any real climate signal. Applying ERA5-based
absolute thresholds directly to raw (non-bias-corrected) CMIP6 output is a simplification. For a
one-month capstone this is a defensible choice, consistent with the honest-caveat framing already
in `project_summary.md` ("with two cities, one model, and one scenario, these results are
illustrative of directional risk rather than definitive climate-model consensus") — but it should
be stated plainly in the limitations section, not left implicit.

**7. Re-run the same downstream pipeline.**
Daily resampling (already native here, so this step simplifies), heatwave/tropical-night/wet-day
indicator calculation, and the same `trend_table()` / baseline-model framework — all reused as-is,
just pointed at the new 2026–2045 series instead of 1990–2025.

---

## Supplementary option: `sis-extreme-indices-cmip6` as a cross-check

Unlike `sis-ecde-climate-indicators` (ruled out above), a second pre-built CMIP6 indicator dataset
**does** support SSP5-8.5: `sis-extreme-indices-cmip6`, a pre-calculated ETCCDI extreme-indices and
heat-stress-indicator dataset, available for SSP1-2.6, SSP2-4.5, SSP3-7.0, and SSP5-8.5, with
`ec_earth3` — the model already chosen for this project — among the models included.

It does not replace the raw-pull plan above (no plain `tmax_mean`/`tmin_mean`, no SPI-equivalent
drought-depth series, no fire-danger metric), but it directly provides several indicators this
project already computes by hand, pre-calculated and validated against the ETCCDI standard:

| This dataset's variable | Matches / relates to |
|---|---|
| Tropical nights (tmin > 20°C) | Exact match to `tropical nights tmin≥20°C` |
| Summer days (tmax > 25°C) | Related to `days tmax≥30°C` / `days tmax≥35°C` (different threshold) |
| Warm days / warm nights (90th-percentile based) | Related to the project's own percentile-threshold heatwave logic |
| Consecutive dry days | Related to (but not the same as) `min_spi3` drought-depth framing |
| Heavy / very heavy precipitation days, max 1-day, max 5-day precip | Related to `max 1-day (mm)` / `max_week_precip_mm` |
| Heat index, humidex, wet-bulb temperature (optionally bias-adjusted) | Supplementary heat-stress framing for H1, not currently in the project's indicator set |

**Suggested use:** use it as an independent cross-check on the raw-pull-derived tropical-night and
precipitation-extreme counts once Step 7 is complete — the same "pre-built dataset validates the
custom pipeline" role `sis-ecde-climate-indicators` was originally meant to play on the historical
side, except this one actually covers the project's scenario. Optional, not blocking: the raw
CMIP6 pull remains the primary and complete data source.

**Verified request schema (checked against the live CDS form, not assumed).** This dataset's
request form is meaningfully different from `projections-cmip6`'s, in one important way: **there
is no `area` parameter at all.** Every request returns a global grid — there is no server-side way
to ask for just Seville or just Larissa; subsetting has to happen locally, after download, with
`xarray`. Four more fields are required here that `projections-cmip6` didn't need:

- `product_type` — and this splits the variable list in two. Base-independent indices (tropical
  nights, summer days, consecutive dry days, precipitation extremes) use
  `product_type: "base_independent"`. The two percentile-based indices this project would use
  (warm days, warm nights) need a baseline period instead (e.g. `"base_period_1981_2010"`) and
  **cannot** be requested in the same call as the base-independent ones.
- `ensemble_member` — required, unlike `projections-cmip6`. `r1i1p1f1` is the standard choice.
- `temporal_aggregation` — `"yearly"`, `"monthly"`, or `"daily"`.
- `period` — an exact string from a fixed list (e.g. `"2015_2100"`), not a free year range like
  `projections-cmip6` allowed; the closest match covering 2026–2045 is the yearly `"2015_2100"`
  period.

`ec_earth3` was confirmed available as a model choice in this dataset at the time the original
plan was written, back when `ec_earth3` was still the primary-pull model choice. Now that the
primary pull uses `cmcc_esm2` instead (see "Corrections" above), that claim no longer applies and
has **not** been re-verified — `pull_extreme_indices_crosscheck()` inherits the module-level
`MODEL` constant automatically, so it will request `cmcc_esm2` from this dataset too, but whether
`cmcc_esm2` is actually offered here is unconfirmed. This function is optional and commented out
by default; check this dataset's live constraints for `cmcc_esm2` before enabling it.

---

## Decisions locked in for this pull

CMIP6 model: `cmcc_esm2`, applied to both cities — corrected from the original `ec_earth3` choice
after live testing showed `ec_earth3` doesn't exist for the needed variable set, and a direct
bias comparison against the project's own ERA5 data showed `cmcc_esm2` matching ERA5 temperatures
far more closely than the other candidate considered (`mpi_esm1_2_lr`). See "Corrections after
live testing" at the top of this document for the full investigation. This plan, and
`pull_cmip6_projections.py`, are ready to execute as corrected.
