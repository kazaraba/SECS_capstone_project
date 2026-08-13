"""
Pull CMIP6 SSP5-8.5 projection data (2026-2045) for Seville and Larissa.

Standalone data-acquisition step, matching the style of extend_data_2021_2025.py. Implements the
plan in documentation/projection_data_pull_plan.md, with three corrections discovered by testing
against the live CDS API (2026-08) that the plan's assumptions didn't hold up to:

  1. Model: `ec_earth3` (bare) does not exist for this dataset/experiment/resolution -- confirmed
     via the collection's live constraints. Only `ec_earth3_cc` and `ec_earth3_veg_lr` variants
     exist, and neither offers near_surface_wind_speed at daily resolution. Switched to
     `cmcc_esm2` (Italian CMCC -- Euro-Mediterranean Centre on Climate Change), which has all 7
     variables below available at daily ssp5_8_5 resolution.
  2. Humidity: `near_surface_relative_humidity` does not exist at daily resolution for ANY model
     in this dataset -- only `near_surface_specific_humidity` does. RH is derived below from
     specific humidity + near-surface temperature + sea-level pressure via the Magnus formula,
     the same approach the historical ERA5 pull used (there from t2m/d2m instead).
  3. One variable per request: `projections-cmip6` silently honors only the FIRST variable in a
     multi-variable request and drops the rest, with no error or warning -- confirmed by testing
     (requesting [temp, precip] in one call returns only temp; reversing the order returns only
     precip). download() below issues one CDS request per variable per city instead of one
     bundled request.
  4. Bounds-dimension row duplication: each per-variable NetCDF also carries a 2-valued `bnds`
     dimension (from `time_bnds`/`lat_bnds`/`lon_bnds`), which isn't part of the merge key used to
     join the 7 variables together -- left in, this multiplies row count by up to 2**6 = 64x
     (discovered when a downstream notebook found seville_cmip6_ssp585_2026_2045.csv had 3.7M rows
     for what should have been ~29K day-gridpoint observations). Every duplicate row is
     value-identical, so no computed mean/sum was ever wrong, only inflated in row count.
     load_variable_frame() below drops the bounds columns and dedupes before any merge happens.

Bounding boxes were also widened from the original ERA5-matching boxes: cmcc_esm2's native grid
is ~0.94 degrees lat x 1.25 degrees lon, much coarser than ERA5's 0.25 degrees, so the original
tight boxes (sized to guarantee 4 ERA5 grid points) contained zero cmcc_esm2 grid points and
caused every request to fail. The new boxes are sized to ~2x the native grid spacing around each
city center and verified (by counting actual grid points returned) to contain multiple points,
in the same spirit as the original 4-point ERA5 boxes.

Requires a working ~/.cdsapirc (same credentials used for the original ERA5 pull). Temperature
variables are left in their native Kelvin units, consistent with how the historical pull left t2m
in Kelvin for the EDA notebooks to convert downstream -- only precipitation is converted here,
since that conversion is CMIP6-specific and easy to get silently wrong (see plan Step 3).

sis-extreme-indices-cmip6 request schema, verified against its live CDS form (2026-08):
unlike projections-cmip6, this dataset has NO "area" (geographic subsetting) parameter -- every
request returns a GLOBAL grid, subset locally after download. It also requires four fields
projections-cmip6 did not: product_type, ensemble_member, temporal_aggregation, and period (an
exact string like "2015_2100", not a free year range). product_type further splits the variable
list: base-independent indices (tropical/summer days, precip extremes) use
product_type="base_independent"; percentile-based indices (warm_days/warm_nights) need a baseline
period instead and cannot be requested in the same call.
"""

import zipfile
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr
import pandas as pd

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

MODEL = "cmcc_esm2"          # corrected choice -- see module docstring point 1
EXPERIMENT = "ssp5_8_5"
YEARS = [str(y) for y in range(2026, 2046)]   # 2026-2045, 20 years
MONTHS = [f"{m:02d}" for m in range(1, 13)]

VARIABLES = [
    "near_surface_air_temperature",               # mean 2m-equivalent temp, Kelvin
    "daily_maximum_near_surface_air_temperature",  # true daily tmax, Kelvin
    "daily_minimum_near_surface_air_temperature",  # true daily tmin, Kelvin
    "precipitation",                               # flux, kg m-2 s-1 -- converted to mm/day below
    "near_surface_specific_humidity",              # kg/kg -- combined with pressure+temp below
    "near_surface_wind_speed",                     # direct wind speed, m/s
    "sea_level_pressure",                          # Pa -- used only to derive RH, not kept as-is
]

CITIES = {
    "seville": {
        "area": [38.4, -7.25, 36.4, -4.65],
        "nc_dir": DATA_DIR / "seville_cmip6_ssp585_2026_2045",
        "csv_path": DATA_DIR / "seville_cmip6_ssp585_2026_2045.csv",
    },
    "larissa": {
        "area": [40.6, 21.15, 38.6, 23.75],
        "nc_dir": DATA_DIR / "larissa_cmip6_ssp585_2026_2045",
        "csv_path": DATA_DIR / "larissa_cmip6_ssp585_2026_2045.csv",
    },
}

# Variable names as they come back from CDS/xarray -- used to locate columns regardless of exact
# CMIP6 short-name naming; adjust here if a future CDS response renames them.
PRECIP_CANDIDATES = ["pr", "precipitation"]
HUSS_CANDIDATES = ["huss", "near_surface_specific_humidity"]
PSL_CANDIDATES = ["psl", "sea_level_pressure"]
TAS_CANDIDATES = ["tas", "near_surface_air_temperature"]


def download(city, cfg):
    cfg["nc_dir"].mkdir(exist_ok=True)
    c = cdsapi.Client()
    print(f"[{city}] submitting CDS requests for {MODEL}/{EXPERIMENT}, {YEARS[0]}-{YEARS[-1]} "
          f"({len(VARIABLES)} separate requests, one per variable -- this dataset silently "
          f"drops all but the first variable in a multi-variable request) ...")
    for variable in VARIABLES:
        out_path = cfg["nc_dir"] / f"{variable}.nc"
        if out_path.exists():
            print(f"[{city}] {variable} already downloaded -> {out_path}, skipping")
            continue
        print(f"[{city}] submitting {variable} ...")
        c.retrieve(
            "projections-cmip6",
            {
                "temporal_resolution": "daily",
                "experiment": EXPERIMENT,
                "variable": [variable],
                "model": MODEL,
                "year": YEARS,
                "month": MONTHS,
                "area": cfg["area"],
            },
            str(out_path),
        )
        print(f"[{city}] {variable} download complete -> {out_path}")


def _open_datasets(nc_path):
    """CDS sometimes returns a zip of multiple NetCDFs instead of a single raw NetCDF, despite
    the .nc extension -- same handling as extend_data_2021_2025.py's historical pull."""
    if zipfile.is_zipfile(nc_path):
        extract_dir = nc_path.parent / f".{nc_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(nc_path) as zf:
            zf.extractall(extract_dir)
            # projections-cmip6 zips also bundle provenance.json/provenance.png alongside the
            # actual data file(s) -- only .nc members are datasets.
            members = [extract_dir / name for name in zf.namelist() if name.endswith(".nc")]
        return [xr.open_dataset(m) for m in members]
    return [xr.open_dataset(nc_path)]


def _to_timestamp_column(series):
    """CMCC-ESM2 (and many other CMIP6 models) use a non-standard 365-day calendar, so xarray
    decodes time as cftime.DatetimeNoLeap objects, not plain datetimes -- pd.to_datetime() raises
    on those. Convert via year/month/day fields (calendar-agnostic) when cftime objects are
    present; fall back to pd.to_datetime() for normal datetime-like input."""
    sample = series.iloc[0] if len(series) else None
    if hasattr(sample, "year") and hasattr(sample, "calendar"):
        return series.apply(lambda t: pd.Timestamp(t.year, t.month, t.day))
    return pd.to_datetime(series)


# Bounds/coordinate columns xarray carries through from time_bnds/lat_bnds/lon_bnds/height --
# not part of the merge key, so left in they create a spurious 2x row multiplication per bounds
# dimension (bnds has 2 values), compounding across every downstream cross-variable merge (7
# variables -> up to 2**6 = 64x row duplication if all 7 are merged with these columns present).
# Every "duplicate" row this produces is value-identical, so it never changed any computed
# mean/sum -- only inflated row counts -- but it's dropped at the source here rather than papered
# over downstream.
BNDS_COLS = ["bnds", "time_bnds", "lat_bnds", "lon_bnds", "height"]


def load_variable_frame(nc_path):
    """Load one variable's raw CDS output into a clean (valid_time, lat, lon, <variable>) frame,
    with the bnds-driven duplication above resolved and cftime timestamps normalized."""
    pieces = []
    for ds in _open_datasets(nc_path):
        d = ds.to_dataframe().reset_index()
        d = d.drop(columns=[c for c in BNDS_COLS if c in d.columns]).drop_duplicates()
        if "time" in d.columns and "valid_time" not in d.columns:
            d = d.rename(columns={"time": "valid_time"})
        d["valid_time"] = _to_timestamp_column(d["valid_time"])
        pieces.append(d)
    return pd.concat(pieces, ignore_index=True) if len(pieces) > 1 else pieces[0]


def add_derived_columns(df):
    """Precipitation flux->mm/day conversion and RH derivation from specific humidity + temp +
    pressure -- shared by load_and_convert() and extend_cmip6_projections_2046_2061.py, so both
    stay identical rather than drifting apart. See module docstring points 2-3 for why these can't
    be pulled directly from CDS."""
    precip_col = next((c for c in PRECIP_CANDIDATES if c in df.columns), None)
    if precip_col is not None:
        # Flux (kg m-2 s-1) -> mm/day. Section 3 of the plan flags this as most likely to go wrong
        # silently -- do NOT reuse the historical ERA5 tp x 1000 conversion.
        df["precip_mm_day"] = df[precip_col] * 86400
    else:
        print(f"WARNING: no recognized precipitation column found in "
              f"{list(df.columns)} -- check CDS variable naming before proceeding.")

    # Relative humidity: not available at daily resolution for any model in this dataset (see
    # module docstring point 2) -- derived here from specific humidity + near-surface temperature
    # + sea-level pressure via the Magnus formula, mirroring how the ERA5 pull derived RH from
    # t2m/d2m. Sea-level pressure stands in for true surface pressure since both cities sit near
    # sea level; this is a mild approximation, not an exact substitution.
    huss_col = next((c for c in HUSS_CANDIDATES if c in df.columns), None)
    psl_col = next((c for c in PSL_CANDIDATES if c in df.columns), None)
    tas_col = next((c for c in TAS_CANDIDATES if c in df.columns), None)
    if huss_col and psl_col and tas_col:
        t_celsius = df[tas_col] - 273.15
        pressure_hpa = df[psl_col] / 100.0
        q = df[huss_col]
        vapor_pressure = q * pressure_hpa / (0.622 + 0.378 * q)
        sat_vapor_pressure = 6.112 * np.exp(17.62 * t_celsius / (243.12 + t_celsius))
        df["relative_humidity_pct"] = (100 * vapor_pressure / sat_vapor_pressure).clip(0, 100)
    else:
        print(f"WARNING: could not derive relative humidity -- missing one of "
              f"huss/psl/tas columns in {list(df.columns)}.")
    return df


def load_and_convert(city, cfg):
    # Each variable was downloaded as its own file (see download() -- this dataset silently
    # drops all but the first variable in a multi-variable request), so load and concatenate
    # each variable's own file(s) first, then merge across variables on the shared coordinates.
    df = None
    for variable in VARIABLES:
        var_df = load_variable_frame(cfg["nc_dir"] / f"{variable}.nc")
        if df is None:
            df = var_df
            continue
        merge_keys = [c for c in ("valid_time", "lat", "lon", "latitude", "longitude")
                      if c in df.columns and c in var_df.columns]
        new_cols = merge_keys + [c for c in var_df.columns if c not in df.columns]
        df = df.merge(var_df[new_cols], on=merge_keys, how="outer")

    df = add_derived_columns(df)

    df.to_csv(cfg["csv_path"], index=False)
    print(f"[{city}] wrote {cfg['csv_path']} ({len(df):,} rows, "
          f"{df['valid_time'].min()} -> {df['valid_time'].max()})")

    # Grid-point diagnostic: CMIP6's native grid is not the ERA5 0.25-degree grid, so the
    # bounding box will not necessarily contain exactly 4 points the way it did historically.
    lat_col = "lat" if "lat" in df.columns else "latitude"
    lon_col = "lon" if "lon" in df.columns else "longitude"
    if lat_col in df.columns and lon_col in df.columns:
        n_points = df[[lat_col, lon_col]].drop_duplicates().shape[0]
        print(f"[{city}] {n_points} unique grid point(s) inside the bounding box "
              f"(historical ERA5 pull used 4) -- adjust the grid-averaging step accordingly.")

    return df


CROSSCHECK_ENSEMBLE_MEMBER = "r1i1p1f1"  # most common CMIP6 realization
CROSSCHECK_PERIOD = "2015_2100"          # yearly period covering 2026-2045; no exact-year option
CROSSCHECK_VERSION = "2_0"               # v1.0 is superseded

# Split in two: base-independent indices need product_type="base_independent"; the two
# percentile-based indices (warm_days/warm_nights) need a baseline period instead, and CANNOT
# be requested alongside the base-independent ones in a single call.
CROSSCHECK_BASE_INDEPENDENT_VARS = [
    "tropical_nights", "summer_days", "consecutive_dry_days",
    "heavy_precipitation_days", "very_heavy_precipitation_days",
    "maximum_1_day_precipitation", "maximum_5_day_precipitation",
]
CROSSCHECK_PERCENTILE_VARS = ["warm_days", "warm_nights"]


def _crosscheck_request(variables, product_type):
    return {
        "variable": variables,
        "product_type": [product_type],
        "model": [MODEL],
        "ensemble_member": [CROSSCHECK_ENSEMBLE_MEMBER],
        "experiment": [EXPERIMENT],
        "temporal_aggregation": ["yearly"],
        "period": [CROSSCHECK_PERIOD],
        "version": [CROSSCHECK_VERSION],
    }


def pull_extreme_indices_crosscheck(city, cfg):
    """Optional supplementary pull: sis-extreme-indices-cmip6, per
    documentation/projection_data_pull_plan.md's cross-check section. Not required for the
    main pipeline -- run this after the primary pull above if you want an independent check
    on the raw-pull-derived tropical-night / precipitation-extreme counts.

    IMPORTANT: unlike projections-cmip6, this dataset has NO geographic-subsetting ("area")
    parameter on its request form -- every request returns a GLOBAL grid. There is no way to
    ask the API for just Seville or just Larissa; you get the whole world and subset locally
    with xarray after download (see load_crosscheck() below). At yearly resolution for 7-9
    variables this is manageable, but do not switch temporal_aggregation to "daily" for the
    HSI heat-stress variables without expecting a much larger download.
    """
    c = cdsapi.Client()

    requests = [
        ("base_independent", CROSSCHECK_BASE_INDEPENDENT_VARS, "base_independent"),
        ("percentile", CROSSCHECK_PERCENTILE_VARS, "base_period_1981_2010"),
    ]
    for label, variables, product_type in requests:
        out_path = DATA_DIR / f"global_extreme_indices_ssp585_{label}.zip"
        if out_path.exists():
            print(f"[crosscheck:{label}] already downloaded -> {out_path}, skipping")
            continue
        print(f"[crosscheck:{label}] submitting CDS request (global grid, no area subset "
              f"available) for {variables} ...")
        c.retrieve(
            "sis-extreme-indices-cmip6",
            _crosscheck_request(variables, product_type),
            str(out_path),
        )
        print(f"[crosscheck:{label}] download complete -> {out_path}")

    print(f"[{city}] NOTE: both crosscheck files above are global and shared across cities -- "
          f"only download them once, then subset to each city's bounding box locally (see "
          f"load_crosscheck()).")


def load_crosscheck(city, cfg):
    """Subset the global cross-check files down to one city's bounding box. Run once per city
    after pull_extreme_indices_crosscheck() has downloaded the (shared, global) files."""
    south, west = cfg["area"][2], cfg["area"][1]
    north, east = cfg["area"][0], cfg["area"][3]

    frames = []
    for label in ("base_independent", "percentile"):
        zpath = DATA_DIR / f"global_extreme_indices_ssp585_{label}.zip"
        if not zpath.exists():
            print(f"[{city}] missing {zpath} -- run pull_extreme_indices_crosscheck() first")
            continue
        for ds in _open_datasets(zpath):
            lat_name = "lat" if "lat" in ds.coords else "latitude"
            lon_name = "lon" if "lon" in ds.coords else "longitude"
            # Longitude in these global CMIP6-derived grids is often 0-360, not -180/180 --
            # check ds[lon_name].values before assuming west/east convert directly.
            sub = ds.sel({lat_name: slice(south, north), lon_name: slice(west, east)})
            frames.append(sub.to_dataframe().reset_index())

    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    out_csv = DATA_DIR / f"{city}_extreme_indices_ssp585_crosscheck.csv"
    df.to_csv(out_csv, index=False)
    print(f"[{city}] wrote {out_csv} ({len(df):,} rows)")
    return df


if __name__ == "__main__":
    for city, cfg in CITIES.items():
        download(city, cfg)

    for city, cfg in CITIES.items():
        load_and_convert(city, cfg)

    print("\nPrimary pull done. Next step: adapt seville_era5_eda.ipynb / larissa_era5_eda.ipynb's "
          "downstream indicator logic (Kelvin->Celsius conversion, daily resampling, heatwave/"
          "tropical-night detection) to run on the new *_cmip6_ssp585_2026_2045.csv files, using "
          "the fixed 1990-2020 ERA5-derived thresholds -- do not refit thresholds on the "
          "projection data (plan Step 5).")

    print("\nOptional: uncomment below to also pull the sis-extreme-indices-cmip6 cross-check.")
    print("Note: the cross-check files are GLOBAL (no area-subsetting is offered by this "
          "dataset) -- pull_extreme_indices_crosscheck() only needs to run once total, not once "
          "per city; load_crosscheck() then subsets locally for each city.")
    # pull_extreme_indices_crosscheck("shared", CITIES["seville"])  # city arg is just a log label
    # for city, cfg in CITIES.items():
    #     load_crosscheck(city, cfg)
