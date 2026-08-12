"""
Shared grid-averaging + unit-conversion logic for CMIP6 CSVs already produced by
pull_cmip6_projections.py / pull_cmip6_historical.py's load_and_convert() (raw per-grid-point,
temperature in Kelvin, with precip_mm_day/relative_humidity_pct already derived, bnds-dedup
already applied).

Collapses N grid points -> 1 daily series and converts Kelvin -> Celsius, matching
seville_cmip6_projection_eda.ipynb's Sections 3-5 exactly (same unweighted mean, same
recompute-RH-from-averaged-inputs discipline). Kept as a standalone module -- rather than only
living inside that notebook -- so bias_correct_cmip6_projection.py can reuse it for three
different CSVs (CMIP6 historical, CMIP6 projection) without a third copy of this logic.
"""

import numpy as np
import pandas as pd

BASE = ["tas", "tasmax", "tasmin", "precip_mm_day", "sfcWind", "huss", "psl"]


def derive_rh(tas_k, huss, psl_pa):
    """Identical formula to pull_cmip6_projections.py's per-grid-point derivation, applied here
    to the grid-averaged base variables -- mirrors the ERA5 notebook's rule of recomputing
    nonlinear quantities from averaged inputs, not averaging the nonlinear output directly."""
    t_c = tas_k - 273.15
    p_hpa = psl_pa / 100.0
    q = huss
    vapor_pressure = q * p_hpa / (0.622 + 0.378 * q)
    sat_vapor_pressure = 6.112 * np.exp(17.62 * t_c / (243.12 + t_c))
    return np.clip(100 * vapor_pressure / sat_vapor_pressure, 0, 100)


def grid_average_daily(raw_csv_path):
    """Load a raw multi-grid-point CMIP6 CSV and collapse it to one grid-averaged daily series,
    Celsius-converted, indexed by valid_time with year/month columns attached."""
    df = pd.read_csv(raw_csv_path, parse_dates=["valid_time"])
    # precip_mm_day carries tiny floating-point negative noise near zero rainfall -- see
    # pull_cmip6_projections.py's plausibility-check discussion of the same artifact.
    df["precip_mm_day"] = df["precip_mm_day"].clip(lower=0)

    grid_mean = df.groupby("valid_time")[BASE].mean()
    grid_mean["relative_humidity_pct"] = derive_rh(
        grid_mean["tas"], grid_mean["huss"], grid_mean["psl"])

    daily = pd.DataFrame({
        "tmax_c": grid_mean["tasmax"] - 273.15,
        "tmin_c": grid_mean["tasmin"] - 273.15,
        "tmean_c": grid_mean["tas"] - 273.15,
        "precip_mm_day": grid_mean["precip_mm_day"],
        "wind_avg": grid_mean["sfcWind"],
        "rh_mean_percent": grid_mean["relative_humidity_pct"],
    })
    daily["year"] = daily.index.year
    daily["month"] = daily.index.month
    return daily
