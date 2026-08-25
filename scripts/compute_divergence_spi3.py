"""
Compute min SPI-3 (annual drought depth) for both cities and both scenarios over the extended
2026-2100 window, for the Projected_Long_Term_2100/ divergence-study notebooks. Reuses the exact
methodology already built in Calculating_SPI_for_Seville_Projection.ipynb /
Calculating_SPI_for_Larissa_Projection.ipynb -- a gamma distribution fit per calendar month on the
fixed ERA5 1990-2020 reference period, never refit on projection data (fixed_reference_period_
principle.md). Standalone script rather than duplicated notebook logic, since both cities and both
scenarios need the identical fit.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
LT_DIR = ROOT / "Projected_Long_Term_2100"

REFERENCE_START, REFERENCE_END = 1990, 2020
ZERO_EPS = 1e-6

CITIES = {
    "seville": {
        "era5_monthly": ROOT / "Historical" / "eda_outputs" / "seville" / "seville_monthly.csv",
    },
    "larissa": {
        "era5_monthly": ROOT / "Historical" / "eda_outputs" / "larissa" / "larissa_monthly.csv",
    },
}

SCENARIOS = {
    "ssp245": {
        "seville": LT_DIR / "SSP2-4.5" / "data" / "seville_cmip6_cmcc_esm2_ssp245_2026_2100_biascorrected.csv",
        "larissa": LT_DIR / "SSP2-4.5" / "data" / "larissa_cmip6_cmcc_esm2_ssp245_2026_2100_biascorrected.csv",
    },
    "ssp585": {
        "seville": LT_DIR / "SSP5-8.5" / "data" / "seville_cmip6_cmcc_esm2_ssp585_2026_2100_biascorrected.csv",
        "larissa": LT_DIR / "SSP5-8.5" / "data" / "larissa_cmip6_cmcc_esm2_ssp585_2026_2100_biascorrected.csv",
    },
}

OUT_DIR = LT_DIR / "eda_outputs"


def fit_month_distribution(ref_values):
    ref_values = np.asarray(ref_values, dtype=float)
    ref_values = ref_values[~np.isnan(ref_values)]
    zeros = ref_values <= ZERO_EPS
    q = zeros.mean()
    nonzero = ref_values[~zeros]
    if len(nonzero) < 4:
        raise ValueError("Not enough nonzero reference months to fit a gamma distribution.")
    shape, loc, scale = stats.gamma.fit(nonzero, floc=0)
    return {"q": q, "shape": shape, "scale": scale}


def spi_from_distribution(x, dist):
    x = np.asarray(x, dtype=float)
    q, shape, scale = dist["q"], dist["shape"], dist["scale"]
    cdf = np.where(
        x <= ZERO_EPS,
        q,
        q + (1 - q) * stats.gamma.cdf(x, shape, loc=0, scale=scale),
    )
    cdf = np.clip(cdf, 1e-6, 1 - 1e-6)
    return stats.norm.ppf(cdf)


def fit_reference_distributions(city):
    era5_monthly = pd.read_csv(CITIES[city]["era5_monthly"], parse_dates=["valid_time"])
    era5_monthly["precip_3mo"] = era5_monthly["precip_mm_scaled"].rolling(window=3, min_periods=3).sum()
    era5_ref = era5_monthly[era5_monthly["year"].between(REFERENCE_START, REFERENCE_END)]

    distributions = {}
    for m in range(1, 13):
        ref_vals = era5_ref.loc[era5_ref["month"] == m, "precip_3mo"].dropna().values
        distributions[m] = fit_month_distribution(ref_vals)
    return distributions


def compute_min_spi3(daily_csv, distributions):
    daily = pd.read_csv(daily_csv, index_col=0, parse_dates=True)
    monthly = daily.groupby(["year", "month"])["precip_mm_day"].sum().rename("precip_mm").reset_index()
    monthly["valid_time"] = pd.to_datetime(dict(year=monthly["year"], month=monthly["month"], day=1))
    monthly = monthly.sort_values("valid_time").reset_index(drop=True)
    monthly["precip_3mo"] = monthly["precip_mm"].rolling(window=3, min_periods=3).sum()

    def score(row):
        if pd.isna(row["precip_3mo"]):
            return np.nan
        return float(spi_from_distribution(row["precip_3mo"], distributions[row["month"]]))

    monthly["spi3"] = monthly.apply(score, axis=1)
    annual_min = monthly.groupby("year")["spi3"].min().rename("min_spi3")
    return annual_min


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for city in CITIES:
        print(f"\n=== {city} ===")
        distributions = fit_reference_distributions(city)
        for scenario in SCENARIOS:
            csv_path = SCENARIOS[scenario][city]
            if not csv_path.exists():
                print(f"  [skip] {scenario}: missing {csv_path}")
                continue
            annual_min = compute_min_spi3(csv_path, distributions)
            out_path = OUT_DIR / f"{city}_{scenario}_min_spi3_annual_2026_2100.csv"
            annual_min.to_csv(out_path)
            print(f"  [{scenario}] wrote {out_path} ({len(annual_min)} years, "
                  f"mean={annual_min.mean():.2f}, min={annual_min.min():.2f}, max={annual_min.max():.2f})")
