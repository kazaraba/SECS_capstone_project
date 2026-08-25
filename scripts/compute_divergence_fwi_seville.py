"""
Compute Seville's days_fwi_gt30 (annual days above the C3S "high fire danger" threshold) for both
scenarios over the extended 2026-2100 window. Reuses the exact FWI computation machinery already
built and validated in FWI_projections_Seville_2026_2045.ipynb (fwi_from_daily.py's
prepare/compute_fwi, warm-started from CEMS end-of-2025 codes) -- the same warm start applies to
either scenario's projection start, since it's derived purely from the historical CEMS record.

Larissa is not included -- no CEMS ground-truth record exists to validate the FWI implementation
against for that city, and its FWI is not used as a validated climate indicator anywhere else in
this project. See FWI_projections_Seville_2026_2045.ipynb's own intro for the full reasoning.
"""

import sys
from pathlib import Path
from scipy.optimize import brentq

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LT_DIR = ROOT / "Projected_Long_Term_2100"
sys.path.insert(0, str(ROOT / "scripts"))

import fwi_from_daily as F

LAT = 37.39
CEMS_CSV = ROOT / "Historical" / "data" / "seville_fwi_daily_1990_2025.csv"
FWI_THRESHOLD = 30.0
SPINUP_DAYS = 365

PROJ_MAP = {"tasmax": "tmax_c", "pr": "precip_mm_day"}
PROJ_RH, PROJ_WIND = "rh_min_percent", "wind_avg"

SCENARIOS = {
    "ssp245": LT_DIR / "SSP2-4.5" / "data" / "seville_cmip6_cmcc_esm2_ssp245_2026_2100_biascorrected.csv",
    "ssp585": LT_DIR / "SSP5-8.5" / "data" / "seville_cmip6_cmcc_esm2_ssp585_2026_2100_biascorrected.csv",
}

OUT_DIR = LT_DIR / "eda_outputs"


def read_daily(path):
    head = pd.read_csv(path, nrows=1)
    date_col = "date" if "date" in head.columns else head.columns[0]
    df = pd.read_csv(path, parse_dates=[date_col]).set_index(date_col).sort_index()
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    df.index.name = "date"
    return df


def ensure_daily_continuity(df):
    df = df[~df.index.duplicated(keep="first")].sort_index()
    full = pd.date_range(df.index.min(), df.index.max(), freq="D")
    out = df.reindex(full)
    num = out.select_dtypes(include=[np.number]).columns
    out[num] = out[num].interpolate(method="time", limit=3, limit_area="inside")
    if out[num].isna().any(axis=1).sum():
        doy = out.index.dayofyear
        for c in num:
            clim = out[c].groupby(doy).transform("mean")
            out[c] = out[c].fillna(clim)
        out[num] = out[num].ffill().bfill()
    return out


def _bui(dmc, dc):
    if dmc <= 0:
        return 0.0
    if dmc <= 0.4 * dc:
        u = 0.8 * dmc * dc / (dmc + 0.4 * dc)
    else:
        u = dmc - (1.0 - 0.8 * dc / (dmc + 0.4 * dc)) * (0.92 + (0.0114 * dmc) ** 1.7)
    return max(u, 0.0)


def invert_bui_to_dmc(bui, dc, dmc_max=1000.0):
    if not (np.isfinite(bui) and np.isfinite(dc)) or bui <= 0 or dc <= 0:
        return None
    denom = 0.8 * dc - bui
    if denom > 1e-6:
        cand = 0.4 * dc * bui / denom
        if 0 < cand <= 0.4 * dc:
            return float(cand)
    f = lambda d: _bui(d, dc) - bui
    lo, hi = 1e-6, max(0.4 * dc, 1.0)
    while f(hi) < 0 and hi < dmc_max:
        hi *= 2.0
    if f(lo) > 0 or f(hi) < 0:
        return None
    try:
        root = brentq(f, lo, hi, xtol=1e-6)
    except (ValueError, RuntimeError):
        return None
    return float(root) if 0 < root < dmc_max else None


def warm_start_codes(on="2025-12-31"):
    cems = read_daily(CEMS_CSV)
    target = pd.Timestamp(on)
    row = cems.loc[target]
    dc0 = float(row["drought_code"])
    ffmc0 = float(row["fine_fuel_moisture_code"])
    bui = float(row["build_up_index"])
    dmc0 = invert_bui_to_dmc(bui, dc0)
    print(f"warm start {target.date()}: ffmc0={ffmc0:.2f} dmc0={dmc0} dc0={dc0:.2f}")
    return ffmc0, dmc0, dc0


def compute_annual_fwi(daily_csv, ffmc0, dmc0, dc0):
    full = read_daily(daily_csv)
    full = ensure_daily_continuity(full)
    trunc = full.loc["2026":"2100"]

    tmp = OUT_DIR / "_tmp_seville_divergence_fwi_feed.csv"
    try:
        trunc.to_csv(tmp)
        w = F.prepare(daily_csv=str(tmp), wind_csv=None, city="seville",
                      colmap={**F.DEFAULT_MAP, **PROJ_MAP},
                      rh_col=PROJ_RH, wind_col=PROJ_WIND, wind_units="m/s")
        out = F.compute_fwi(w, lat=LAT, ffmc0=ffmc0, dmc0=dmc0, dc0=dc0)
    finally:
        tmp.unlink(missing_ok=True)

    out = out.loc["2026":"2100"]
    annual = F.annual_indicators(out, FWI_THRESHOLD)[["days_fwi_gt30", "fwi_mean", "fwi_p95", "fwi_max"]]
    return annual


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ffmc0, dmc0, dc0 = warm_start_codes()

    for scenario, csv_path in SCENARIOS.items():
        if not csv_path.exists():
            print(f"[skip] {scenario}: missing {csv_path}")
            continue
        print(f"\n=== {scenario} ===")
        annual = compute_annual_fwi(csv_path, ffmc0, dmc0, dc0)
        out_path = OUT_DIR / f"seville_{scenario}_fwi_annual_2026_2100.csv"
        annual.to_csv(out_path)
        print(f"wrote {out_path} ({len(annual)} years, "
              f"mean days_fwi_gt30={annual['days_fwi_gt30'].mean():.1f}, "
              f"min={annual['days_fwi_gt30'].min()}, max={annual['days_fwi_gt30'].max()})")
