"""
Pull CMIP6 SSP2-4.5 projection data (2026-2045) for Seville and Larissa, using the SAME model
(`cmcc_esm2`) as the SSP5-8.5 pull in pull_cmip6_projections.py.

This is a straight adaptation of that script -- same model, same variables, same bounding boxes,
same unit conversions and RH derivation -- with only the experiment and output paths changed.
Keeping the model identical across scenarios (rather than the ec_earth3_cc used for the earlier,
now-superseded SSP2-4.5 pull in fetch_cmip6_projections.py) means:

  1. The existing `cmcc_esm2` historical run (1990-2014) already pulled for SSP5-8.5
     (../Projected_SSP5-8.5/data/{city}_cmip6_historical_1990_2014.csv) can be reused directly as
     the bias-correction fitting baseline here -- a model's `historical` experiment doesn't depend
     on which future SSP is being projected, so there's no need to pull it twice.
  2. `scripts/bias_correct_cmip6_projection.py` and `scripts/cmip6_grid_processing.py` (both written
     against cmcc_esm2's variable names/units) work unmodified on this pull's output.

Availability confirmed against the live CDS `projections-cmip6` constraints endpoint (no
credentials required for that check) before writing this script: cmcc_esm2/ssp2_4_5/daily has all
7 variables below (see scripts/scenario_scan.py --model cmcc_esm2).

Requires a working ~/.cdsapirc (same credentials used for the ERA5 and SSP5-8.5 pulls).
"""

import zipfile
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr
import pandas as pd

# Resolve relative to this file, not the caller's cwd, so this can be run from anywhere.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "Projected_SSP2-4.5" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "cmcc_esm2"          # same model as pull_cmip6_projections.py (SSP5-8.5), deliberately
EXPERIMENT = "ssp2_4_5"
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

# Same bounding boxes as pull_cmip6_projections.py -- same model, same native ~0.94x1.25 deg grid.
CITIES = {
    "seville": {
        "area": [38.4, -7.25, 36.4, -4.65],
        "nc_dir": DATA_DIR / "seville_cmip6_ssp245_2026_2045",
        "csv_path": DATA_DIR / "seville_cmip6_ssp245_2026_2045.csv",
    },
    "larissa": {
        "area": [40.6, 21.15, 38.6, 23.75],
        "nc_dir": DATA_DIR / "larissa_cmip6_ssp245_2026_2045",
        "csv_path": DATA_DIR / "larissa_cmip6_ssp245_2026_2045.csv",
    },
}

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
    the .nc extension."""
    if zipfile.is_zipfile(nc_path):
        extract_dir = nc_path.parent / f".{nc_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(nc_path) as zf:
            zf.extractall(extract_dir)
            members = [extract_dir / name for name in zf.namelist() if name.endswith(".nc")]
        return [xr.open_dataset(m) for m in members]
    return [xr.open_dataset(nc_path)]


def _to_timestamp_column(series):
    """CMCC-ESM2 uses a non-standard 365-day calendar, so xarray decodes time as
    cftime.DatetimeNoLeap objects, not plain datetimes -- pd.to_datetime() raises on those.
    Convert via year/month/day fields (calendar-agnostic) when cftime objects are present."""
    sample = series.iloc[0] if len(series) else None
    if hasattr(sample, "year") and hasattr(sample, "calendar"):
        return series.apply(lambda t: pd.Timestamp(t.year, t.month, t.day))
    return pd.to_datetime(series)


# Not part of the merge key -- left in, these create a spurious 2x row multiplication per bounds
# dimension, compounding across every downstream cross-variable merge. Dropped at the source.
BNDS_COLS = ["bnds", "time_bnds", "lat_bnds", "lon_bnds", "height"]


def load_variable_frame(nc_path):
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
    pressure -- identical formulas to pull_cmip6_projections.py, kept in sync deliberately."""
    precip_col = next((c for c in PRECIP_CANDIDATES if c in df.columns), None)
    if precip_col is not None:
        df["precip_mm_day"] = df[precip_col] * 86400
    else:
        print(f"WARNING: no recognized precipitation column found in "
              f"{list(df.columns)} -- check CDS variable naming before proceeding.")

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

    lat_col = "lat" if "lat" in df.columns else "latitude"
    lon_col = "lon" if "lon" in df.columns else "longitude"
    if lat_col in df.columns and lon_col in df.columns:
        n_points = df[[lat_col, lon_col]].drop_duplicates().shape[0]
        print(f"[{city}] {n_points} unique grid point(s) inside the bounding box.")

    return df


if __name__ == "__main__":
    for city, cfg in CITIES.items():
        download(city, cfg)

    for city, cfg in CITIES.items():
        load_and_convert(city, cfg)

    print("\nPrimary pull done. Reuses ../Projected_SSP5-8.5/data/{city}_cmip6_historical_1990_2014.csv "
          "as the bias-correction historical baseline -- same model (cmcc_esm2), so no separate "
          "historical pull is needed for this scenario.")
