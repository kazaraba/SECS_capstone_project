# Projection Data Pull: SSP5-8.5, 2026–2045

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
| Relative humidity | Derived from t2m/d2m via Magnus formula | Available **directly** as `near_surface_relative_humidity` — no derivation needed |
| Grid alignment | Fixed 0.25° ERA5 grid, matches existing bounding boxes exactly | Model-native grid, resolution varies by model — the same bounding box coordinates work as a subset request, but the returned grid points will *not* line up with the ERA5 2×2 grid |

---

## Step-by-step plan

**1. CMIP6 model: confirmed as `ec_earth3`, used for both cities.**
European-developed, good regional performance over the Mediterranean/Balkans, and consistent in
spirit with the `ec_earth` GCM already used elsewhere in the project's EURO-CORDEX references.
This choice is now locked in for all projection requests below.

**2. Submit the CDS request per city**, mirroring the historical structure exactly (same bounding
boxes, same variable-first approach):

```python
import cdsapi

c = cdsapi.Client()

MODEL = "ec_earth3"          # confirmed choice
EXPERIMENT = "ssp5_8_5"
YEARS = [str(y) for y in range(2026, 2046)]   # 2026-2045, 20 years
MONTHS = [f"{m:02d}" for m in range(1, 13)]

VARIABLES = [
    "near_surface_air_temperature",              # mean 2m-equivalent temp
    "daily_maximum_near_surface_air_temperature", # true daily tmax
    "daily_minimum_near_surface_air_temperature", # true daily tmin
    "precipitation",                              # flux, kg m-2 s-1 -- needs unit conversion
    "near_surface_relative_humidity",              # direct RH, no derivation needed
    "near_surface_wind_speed",                     # direct wind speed, no u/v combination needed
]

c.retrieve(
    "projections-cmip6",
    {
        "temporal_resolution": "daily",
        "experiment": EXPERIMENT,
        "variable": VARIABLES,
        "model": MODEL,
        "year": YEARS,
        "month": MONTHS,
        "area": [37.6, -6.2, 37.2, -5.7],   # Seville -- same box as historical
    },
    "seville_cmip6_ssp585_2026_2045.nc",
)

c.retrieve(
    "projections-cmip6",
    {
        "temporal_resolution": "daily",
        "experiment": EXPERIMENT,
        "variable": VARIABLES,
        "model": MODEL,
        "year": YEARS,
        "month": MONTHS,
        "area": [39.8, 22.2, 39.4, 22.7],   # Larissa -- same box as historical
    },
    "larissa_cmip6_ssp585_2026_2045.nc",
)
```

No `ensemble_member`/variant field appeared in this dataset's request form — unlike the
EURO-CORDEX indicator dataset, which required one explicitly. If the actual request errors out
asking for one, add `"ensemble_member": "r1i1p1f1"` (the most common CMIP6 realization) and retry.

**3. Convert units on load — this is the step most likely to go wrong silently.**
`precipitation` is a flux, not an accumulation: multiply by 86,400 to get mm/day. This is a
*different* conversion than the historical `tp × 1000` used for ERA5 — reusing the old conversion
here would silently produce precipitation totals off by several orders of magnitude.

**4. Skip the grid-averaging step (or adapt it) — CMIP6's grid isn't the ERA5 grid.**
The historical pipeline's Section 5 (averaging 4 grid points into one city value) assumed the
ERA5 0.25° grid specifically. CMIP6's native resolution depends on the model chosen in Step 1, so
check how many grid points actually fall inside the bounding box before assuming there are exactly
four — there may be one, one, or several, and the averaging step should adapt accordingly.

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

## Decisions locked in for this pull

CMIP6 model: `ec_earth3`, applied to both cities. This plan is ready to execute as written.
