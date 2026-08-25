"""
Bias-correct the extended 2026-2100 Seville CMIP6 pulls for both scenarios (SSP2-4.5 and
SSP5-8.5), for the scenario-divergence study. Same Equidistant CDF Matching machinery used
throughout this project (bias_correct_cmip6_projection.py's helper functions), same fixed
1990-2014 fitting period, same reused cmcc_esm2 historical run for both scenarios (a model's
historical experiment doesn't depend on which future SSP is being projected).

Standalone script rather than embedded in a notebook -- this output feeds a comparison notebook
for both scenarios, so it belongs outside either scenario's own notebook.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from cmip6_grid_processing import grid_average_daily
from bias_correct_cmip6_projection import (
    _empirical_cdf, _value_to_quantile, _quantile_to_value, VARIABLE_MAP, REF_START, REF_END,
)

ERA5_DAILY = ROOT / "Historical" / "eda_outputs" / "seville" / "seville_daily.csv"
HIST_CSV = ROOT / "Projected_SSP5-8.5" / "data" / "seville_cmip6_historical_1990_2014.csv"

LT_DIR = ROOT / "Projected_Long_Term_2100"

SCENARIOS = {
    "ssp245": {
        "raw": LT_DIR / "SSP2-4.5" / "data" / "seville_cmip6_ssp245_2026_2100.csv",
        "out": LT_DIR / "SSP2-4.5" / "data" / "seville_cmip6_cmcc_esm2_ssp245_2026_2100_biascorrected.csv",
    },
    "ssp585": {
        "raw": LT_DIR / "SSP5-8.5" / "data" / "seville_cmip6_ssp585_2026_2100.csv",
        "out": LT_DIR / "SSP5-8.5" / "data" / "seville_cmip6_cmcc_esm2_ssp585_2026_2100_biascorrected.csv",
    },
}


def bias_correct(raw_csv, out_csv):
    era5 = pd.read_csv(ERA5_DAILY, parse_dates=["valid_time"])
    era5["year"] = era5["valid_time"].dt.year
    era5["month"] = era5["valid_time"].dt.month
    era5_ref = era5[era5["year"].between(REF_START, REF_END)]

    model_hist = grid_average_daily(HIST_CSV)
    model_hist_ref = model_hist[model_hist["year"].between(REF_START, REF_END)]

    model_fut = grid_average_daily(raw_csv)
    corrected = model_fut.copy()

    for model_col, (era5_col, kind) in VARIABLE_MAP.items():
        for month in range(1, 13):
            obs_vals = era5_ref.loc[era5_ref["month"] == month, era5_col]
            hist_vals = model_hist_ref.loc[model_hist_ref["month"] == month, model_col]
            fut_mask = model_fut["month"] == month
            fut_vals = model_fut.loc[fut_mask, model_col]

            obs_probs, obs_q = _empirical_cdf(obs_vals)
            hist_probs, hist_q = _empirical_cdf(hist_vals)

            tau = np.clip(_value_to_quantile(fut_vals.values, hist_probs, hist_q), 0.0, 1.0)
            obs_at_tau = _quantile_to_value(tau, obs_probs, obs_q)
            hist_at_tau = _quantile_to_value(tau, hist_probs, hist_q)

            if kind == "additive":
                new_vals = fut_vals.values + (obs_at_tau - hist_at_tau)
            else:  # multiplicative -- guards against blow-up when hist_at_tau is near zero
                ratio = np.clip(obs_at_tau / np.clip(hist_at_tau, 1e-3, None), 0.1, 10.0)
                new_vals = np.clip(fut_vals.values * ratio, 0, None)
            corrected.loc[fut_mask, model_col] = new_vals

    corrected.to_csv(out_csv)
    print(f"wrote {out_csv} ({len(corrected):,} rows, columns: {list(corrected.columns)})")
    return corrected


if __name__ == "__main__":
    for scenario, paths in SCENARIOS.items():
        print(f"\n=== {scenario} ===")
        if not paths["raw"].exists():
            print(f"  MISSING raw file: {paths['raw']}")
            continue
        bias_correct(paths["raw"], paths["out"])
