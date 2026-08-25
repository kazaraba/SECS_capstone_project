"""
Compute Larissa's "wet side" indicators for both scenarios over the extended 2026-2100 window:

- Rx1day: annual maximum single-day precipitation (mm) -- the standard ETCCDI extreme-precipitation
  index, more directly tied to flash-flood risk than max_week_precip_mm's weekly aggregate.
- Heavy-precipitation-day count: days/year exceeding the P95 of wet days (>=1mm) in the fixed ERA5
  1990-2020 reference period -- same fixed-reference-period principle used for every other
  threshold-based indicator in this project (never refit on projection data). Measures frequency of
  intense events, not just the single worst day.
- SDII (Simple Daily Intensity Index): total annual precipitation / number of wet days (>=1mm) --
  tests whether rainfall is becoming less frequent but more intense per event, independent of the
  total-amount trend already captured by precip_total.

All three are computed directly from the daily precip_mm_day series already present in the
bias-corrected 2026-2100 files -- no new data pull.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LT_DIR = ROOT / "Projected_Long_Term_2100"

ERA5_DAILY = ROOT / "Historical" / "eda_outputs" / "larissa" / "larissa_daily.csv"
REFERENCE_START, REFERENCE_END = 1990, 2020
WET = 1.0  # mm/day, same threshold used throughout this project

SCENARIOS = {
    "ssp245": LT_DIR / "SSP2-4.5" / "data" / "larissa_cmip6_cmcc_esm2_ssp245_2026_2100_biascorrected.csv",
    "ssp585": LT_DIR / "SSP5-8.5" / "data" / "larissa_cmip6_cmcc_esm2_ssp585_2026_2100_biascorrected.csv",
}

OUT_DIR = LT_DIR / "eda_outputs"


def fixed_heavy_day_threshold():
    era5 = pd.read_csv(ERA5_DAILY, parse_dates=["valid_time"])
    era5["year"] = era5["valid_time"].dt.year
    ref = era5[era5["year"].between(REFERENCE_START, REFERENCE_END)]
    wet = ref.loc[ref["precip_mm_scaled"] >= WET, "precip_mm_scaled"]
    return float(wet.quantile(0.95))


def compute_wet_indicators(daily_csv, heavy_threshold):
    daily = pd.read_csv(daily_csv, index_col=0, parse_dates=True)
    g = daily.groupby("year")["precip_mm_day"]

    rx1day = g.max().rename("rx1day_mm")

    is_wet = daily["precip_mm_day"] >= WET
    is_heavy = daily["precip_mm_day"] >= heavy_threshold
    wet_days = is_wet.groupby(daily["year"]).sum().rename("wet_days")
    heavy_days = is_heavy.groupby(daily["year"]).sum().rename("heavy_days")

    precip_total = g.sum().rename("precip_total")
    sdii = (precip_total / wet_days.replace(0, np.nan)).rename("sdii_mm_per_wet_day")

    return pd.concat([rx1day, heavy_days, sdii, wet_days, precip_total], axis=1)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    threshold = fixed_heavy_day_threshold()
    print(f"Fixed heavy-day threshold (ERA5 1990-2020, P95 of wet days >= {WET}mm): {threshold:.2f} mm/day")

    for scenario, csv_path in SCENARIOS.items():
        if not csv_path.exists():
            print(f"[skip] {scenario}: missing {csv_path}")
            continue
        indicators = compute_wet_indicators(csv_path, threshold)
        out_path = OUT_DIR / f"larissa_{scenario}_wet_indicators_annual_2026_2100.csv"
        indicators.to_csv(out_path)
        print(f"[{scenario}] wrote {out_path} ({len(indicators)} years)")
        print(f"  rx1day_mm      mean={indicators['rx1day_mm'].mean():.1f}  "
              f"min={indicators['rx1day_mm'].min():.1f}  max={indicators['rx1day_mm'].max():.1f}")
        print(f"  heavy_days     mean={indicators['heavy_days'].mean():.1f}/yr")
        print(f"  sdii (mm/wet day) mean={indicators['sdii_mm_per_wet_day'].mean():.2f}")
