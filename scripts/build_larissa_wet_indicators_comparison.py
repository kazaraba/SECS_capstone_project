"""
Build era5_historical / cmip6_raw / cmip6_biascorrected comparison CSVs for Larissa's rx1day_mm and
SDII, matching the exact format (and 2026-2045 window) the Results_Summary notebooks read for every
other indicator. Run independently per scenario -- each output compares that scenario's own raw and
bias-corrected projection against the same historical ERA5 record, never against the other scenario.
Reuses cmip6_grid_processing.grid_average_daily() for the raw series and each scenario's own
EDA-notebook-built bias-corrected daily file -- nothing new is computed methodologically, this only
reassembles already-established series into the comparison format, the same way
seville_days_fwi_gt30_era5_vs_cmip6_raw_vs_corrected.csv was built.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from cmip6_grid_processing import grid_average_daily

ERA5_DAILY = ROOT / "Historical" / "eda_outputs" / "larissa" / "larissa_daily.csv"
WET = 1.0

SCENARIOS = {
    "SSP2-4.5": {
        "raw": ROOT / "Projected_SSP2-4.5" / "data" / "larissa_cmip6_ssp245_2026_2045.csv",
        "corrected": ROOT / "Projected_SSP2-4.5" / "eda_outputs" / "larissa" / "larissa_projection_daily_biascorrected_2026_2045.csv",
        "out_dir": ROOT / "Projected_SSP2-4.5" / "eda_outputs" / "larissa",
    },
    "SSP5-8.5": {
        "raw": ROOT / "Projected_SSP5-8.5" / "data" / "larissa_cmip6_ssp585_2026_2045.csv",
        "corrected": ROOT / "Projected_SSP5-8.5" / "eda_outputs" / "larissa" / "larissa_projection_daily_biascorrected_2026_2045.csv",
        "out_dir": ROOT / "Projected_SSP5-8.5" / "eda_outputs" / "larissa",
    },
}


def annual_rx1day_sdii(daily, precip_col):
    year_key = daily["year"] if "year" in daily.columns else daily.index.year
    g = daily.groupby(year_key)[precip_col]
    rx1day = g.max().rename("rx1day_mm")
    is_wet = daily[precip_col] >= WET
    wet_days = is_wet.groupby(year_key).sum()
    total = g.sum()
    sdii = (total / wet_days.replace(0, np.nan)).rename("sdii_mm")
    return rx1day, sdii


def era5_series():
    era5 = pd.read_csv(ERA5_DAILY, parse_dates=["valid_time"])
    era5["year"] = era5["valid_time"].dt.year
    era5 = era5[era5["year"].between(1990, 2025)]
    return annual_rx1day_sdii(era5, "precip_mm_scaled")


if __name__ == "__main__":
    era5_rx1day, era5_sdii = era5_series()

    # Each scenario processed independently -- output compares that scenario's own raw/corrected
    # projection against the shared historical record only, never against the other scenario.
    for scenario, paths in SCENARIOS.items():
        print(f"\n=== {scenario} (vs. historical only) ===")

        raw_daily = grid_average_daily(paths["raw"])
        raw_rx1day, raw_sdii = annual_rx1day_sdii(raw_daily, "precip_mm_day")

        corrected_daily = pd.read_csv(paths["corrected"], index_col=0, parse_dates=True)
        corr_rx1day, corr_sdii = annual_rx1day_sdii(corrected_daily, "precip_mm_day")

        rx1day_compare = pd.DataFrame({
            "era5_historical": era5_rx1day,
            "cmip6_raw": raw_rx1day,
            "cmip6_biascorrected": corr_rx1day,
        })
        sdii_compare = pd.DataFrame({
            "era5_historical": era5_sdii,
            "cmip6_raw": raw_sdii,
            "cmip6_biascorrected": corr_sdii,
        })

        out_rx1day = paths["out_dir"] / "larissa_rx1day_mm_era5_vs_cmip6_raw_vs_corrected.csv"
        out_sdii = paths["out_dir"] / "larissa_sdii_mm_era5_vs_cmip6_raw_vs_corrected.csv"
        rx1day_compare.rename_axis("year").to_csv(out_rx1day)
        sdii_compare.rename_axis("year").to_csv(out_sdii)

        print(f"wrote {out_rx1day}")
        print(f"  hist mean {era5_rx1day.mean():.1f}  corrected mean {corr_rx1day.dropna().mean():.1f}  "
              f"raw mean {raw_rx1day.dropna().mean():.1f}")
        print(f"wrote {out_sdii}")
        print(f"  hist mean {era5_sdii.mean():.2f}  corrected mean {corr_sdii.dropna().mean():.2f}  "
              f"raw mean {raw_sdii.dropna().mean():.2f}")
