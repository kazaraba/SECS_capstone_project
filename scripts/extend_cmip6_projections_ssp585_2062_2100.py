"""
Extend the CMIP6 SSP5-8.5 projection pull a second time, from 2026-2061 (the existing
extend_cmip6_projections_2046_2061.py output) through 2062-2100 -- for a divergence study against
the SSP2-4.5 run, extended in parallel by extend_cmip6_projections_ssp245_2046_2100.py, so both
scenarios cover the same 2026-2100 window (the full CDS-published ScenarioMIP horizon for this
model/experiment).

Combines THREE segments per variable, not two: the original 2026-2045 pull
(pull_cmip6_projections.py), the first extension 2046-2061
(extend_cmip6_projections_2046_2061.py), and this script's new 2062-2100 download. Only the third
segment is downloaded here -- the first two are already on disk.

Requires a working ~/.cdsapirc (same credentials as the original pull).
"""

from pathlib import Path

import cdsapi
import pandas as pd

import pull_cmip6_projections as base

YEARS_NEW = [str(y) for y in range(2062, 2101)]   # 2062-2100, 39 years


def download_new_years(city, cfg):
    cfg["nc_dir"].mkdir(exist_ok=True)
    c = cdsapi.Client()
    print(f"[{city}] submitting CDS requests for {base.MODEL}/{base.EXPERIMENT}, "
          f"{YEARS_NEW[0]}-{YEARS_NEW[-1]} ({len(base.VARIABLES)} separate requests, one per "
          f"variable) ...")
    for variable in base.VARIABLES:
        out_path = cfg["nc_dir"] / f"{variable}_2062_2100.nc"
        if out_path.exists():
            print(f"[{city}] {variable} 2062-2100 already downloaded -> {out_path}, skipping")
            continue
        print(f"[{city}] submitting {variable} for 2062-2100 ...")
        c.retrieve(
            "projections-cmip6",
            {
                "temporal_resolution": "daily",
                "experiment": base.EXPERIMENT,
                "variable": [variable],
                "model": base.MODEL,
                "year": YEARS_NEW,
                "month": base.MONTHS,
                "area": cfg["area"],
            },
            str(out_path),
        )
        print(f"[{city}] {variable} 2062-2100 download complete -> {out_path}")


def load_and_combine(city, cfg):
    df = None
    for variable in base.VARIABLES:
        seg1 = base.load_variable_frame(cfg["nc_dir"] / f"{variable}.nc")                    # 2026-2045
        seg2 = base.load_variable_frame(cfg["nc_dir"] / f"{variable}_2046_2061.nc")           # 2046-2061
        seg3 = base.load_variable_frame(cfg["nc_dir"] / f"{variable}_2062_2100.nc")           # 2062-2100
        var_df = (pd.concat([seg1, seg2, seg3], ignore_index=True)
                    .drop_duplicates(subset=["valid_time", "lat", "lon"])
                    .sort_values("valid_time")
                    .reset_index(drop=True))

        if df is None:
            df = var_df
            continue
        merge_keys = [c for c in ("valid_time", "lat", "lon", "latitude", "longitude")
                      if c in df.columns and c in var_df.columns]
        new_cols = merge_keys + [c for c in var_df.columns if c not in df.columns]
        df = df.merge(var_df[new_cols], on=merge_keys, how="outer")

    df = base.add_derived_columns(df)
    df = df.sort_values("valid_time").reset_index(drop=True)

    long_term_dir = Path("../Projected_Long_Term_2100/SSP5-8.5/data")
    long_term_dir.mkdir(parents=True, exist_ok=True)
    out_csv = long_term_dir / f"{city}_cmip6_ssp585_2026_2100.csv"
    df.to_csv(out_csv, index=False)
    print(f"[{city}] wrote {out_csv} ({len(df):,} rows, "
          f"{df['valid_time'].min()} -> {df['valid_time'].max()})")

    lat_col = "lat" if "lat" in df.columns else "latitude"
    lon_col = "lon" if "lon" in df.columns else "longitude"
    n_points = df[[lat_col, lon_col]].drop_duplicates().shape[0]
    n_days = df["valid_time"].nunique()
    print(f"[{city}] {n_points} unique grid point(s), {n_days} unique days "
          f"(expect {n_points * n_days} rows total)")
    return df


if __name__ == "__main__":
    for city, cfg in base.CITIES.items():
        download_new_years(city, cfg)

    for city, cfg in base.CITIES.items():
        load_and_combine(city, cfg)

    print("\nExtension pull done. Combined files cover 2026-2100 for both cities:")
    print("  Projected_Long_Term_2100/SSP5-8.5/data/seville_cmip6_ssp585_2026_2100.csv")
    print("  Projected_Long_Term_2100/SSP5-8.5/data/larissa_cmip6_ssp585_2026_2100.csv")
