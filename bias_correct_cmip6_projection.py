"""
Bias-correct the CMIP6 SSP5-8.5 projection (2026-2061) against ERA5, using Equidistant CDF
Matching (Li, Sheffield & Wood 2010) -- a detrended/trend-preserving quantile mapping method,
fit per city, per variable, per calendar month, from the model's own historical run
(cmcc_esm2 `historical` experiment, 1990-2014) vs. ERA5 observed (1990-2014).

Why not naive quantile mapping: mapping a future value directly to its matching percentile in the
HISTORICAL observed distribution would silently erase most of the projected warming signal --
every future day would just get pulled back toward the shape of the historical climatology.
Equidistant CDF Matching instead:
  1. Finds the future value's own percentile (tau) within the model's FUTURE distribution for
     that city/variable/month (i.e., relative to the other 2026-2061 SSP5-8.5 days -- computed
     against the model's own historical distribution, per Li et al.'s original formulation, since
     that's what the correction function itself is defined over).
  2. Computes what the bias correction would be AT THAT SAME PERCENTILE, from the model's
     historical distribution vs. ERA5's historical distribution.
  3. Applies that correction to the future value.
This preserves the model's own projected shift (tau reflects where the future value sits in the
model's own distribution) while correcting for the model's systematic bias at that point in the
distribution -- a day that's extreme even by 2050s-SSP5-8.5 standards gets a different correction
than a merely-average 2050s day, rather than one constant offset applied uniformly to everything.

Precipitation uses a multiplicative (ratio) correction instead of additive -- an additive
correction near zero precipitation can push values negative, which has no physical meaning.

Reference (fitting) period: 1990-2014, the full CMIP6 historical / ERA5 overlap -- deliberately
NOT the shorter 2010-2014 window used for the earlier cmcc_esm2-vs-mpi_esm1_2_lr model-selection
bias check (documentation/projection_data_pull_plan.md Correction 4), which was only ever a quick
diagnostic for choosing between two candidate models, not a rigorous correction-fitting reference.
A longer window gives much more stable per-calendar-month quantile estimates, particularly in the
tails that heatwave/hot-day counting cares about most.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from cmip6_grid_processing import grid_average_daily

DATA_DIR = Path("data")

ERA5_DAILY = {
    "seville": Path("eda_results/eda_outputs/seville_daily.csv"),
    "larissa": Path("eda_results/eda_outputs_larissa/larissa_daily.csv"),
}
CMIP6_HISTORICAL = {
    "seville": DATA_DIR / "seville_cmip6_historical_1990_2014.csv",
    "larissa": DATA_DIR / "larissa_cmip6_historical_1990_2014.csv",
}
CMIP6_PROJECTION = {
    "seville": DATA_DIR / "seville_cmip6_ssp585_2026_2061.csv",
    "larissa": DATA_DIR / "larissa_cmip6_ssp585_2026_2061.csv",
}

REF_START, REF_END = 1990, 2014   # CMIP6 historical / ERA5 overlap -- fixed fitting period

# CMIP6 grid-averaged column -> (matching ERA5 column, correction type)
# ERA5's precip_mm_scaled is its undercount-corrected estimate of true daily precip -- the
# right comparison target for CMIP6's precip_mm_day, which is already a true daily total.
VARIABLE_MAP = {
    "tmax_c":          ("tmax_c",           "additive"),
    "tmin_c":          ("tmin_c",           "additive"),
    "tmean_c":         ("tmean_c",          "additive"),
    "wind_avg":        ("wind_avg",         "additive"),
    "rh_mean_percent": ("rh_mean_percent",  "additive"),
    "rh_min_percent":  ("rh_min_percent",   "additive"),
    "precip_mm_day":   ("precip_mm_scaled", "multiplicative"),
}

N_QUANTILES = 101   # 1% steps -- matched to realistic per-month sample sizes (~750 obs/hist days)


def _empirical_cdf(values):
    """Returns (probs, sorted_quantile_values) describing an empirical CDF."""
    values = pd.Series(values).dropna().values
    probs = np.linspace(0.0, 1.0, N_QUANTILES)
    return probs, np.quantile(values, probs)


def _value_to_quantile(x, probs, q_values):
    """Invert an empirical CDF: given raw value(s) x, return their approximate quantile (0-1)."""
    return np.interp(x, q_values, probs)


def _quantile_to_value(tau, probs, q_values):
    """Evaluate an empirical CDF's inverse (quantile function) at probability/probabilities tau."""
    return np.interp(tau, probs, q_values)


def fit_and_apply(city):
    era5 = pd.read_csv(ERA5_DAILY[city], parse_dates=["valid_time"])
    era5["year"] = era5["valid_time"].dt.year
    era5_ref = era5[era5["year"].between(REF_START, REF_END)]

    model_hist = grid_average_daily(CMIP6_HISTORICAL[city])
    model_hist_ref = model_hist[model_hist["year"].between(REF_START, REF_END)]

    model_fut = grid_average_daily(CMIP6_PROJECTION[city])
    corrected = model_fut.copy()

    diagnostics = []
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
                correction = obs_at_tau - hist_at_tau
                new_vals = fut_vals.values + correction
            else:  # multiplicative -- guards against blow-up when hist_at_tau is near zero
                ratio = np.clip(obs_at_tau / np.clip(hist_at_tau, 1e-3, None), 0.1, 10.0)
                new_vals = np.clip(fut_vals.values * ratio, 0, None)

            corrected.loc[fut_mask, model_col] = new_vals

            diagnostics.append({
                "variable": model_col,
                "month": month,
                "mean_bias_hist_vs_obs": float(hist_vals.mean() - obs_vals.mean()),
                "mean_correction_applied": float(np.mean(new_vals - fut_vals.values)),
            })

    diag_df = pd.DataFrame(diagnostics)
    diag_path = DATA_DIR / f"{city}_cmip6_bias_correction_diagnostics.csv"
    diag_df.to_csv(diag_path, index=False)

    out_path = DATA_DIR / f"{city}_cmip6_ssp585_2026_2061_biascorrected.csv"
    corrected.to_csv(out_path)

    print(f"[{city}] wrote {out_path} ({len(corrected):,} rows)")
    print(f"[{city}] wrote {diag_path}")
    print(f"[{city}] mean tmean_c correction applied: "
          f"{diag_df.loc[diag_df['variable'] == 'tmean_c', 'mean_correction_applied'].mean():+.3f} degC")
    return corrected, diag_df


if __name__ == "__main__":
    for city in ["seville", "larissa"]:
        fit_and_apply(city)
