"""
Extend the CMIP6 SSP2-4.5 projection pull from 2026-2045 through 2046-2100, for both Seville and
Larissa -- for a divergence study against the SSP5-8.5 run, extended in parallel by
extend_cmip6_projections_ssp585_2062_2100.py. Mirrors extend_cmip6_projections_2046_2061.py's
pattern exactly, just for the other scenario and a longer new segment: download only the new
years, load what pull_cmip6_projections_ssp245.py already fetched for 2026-2045 (no re-download
of those 14 files), concatenate, and write a new combined CSV covering 2026-2100 -- the full
CDS-published ScenarioMIP horizon for this model/experiment (confirmed via the public constraints
endpoint before writing this script).

Requires a working ~/.cdsapirc (same credentials as the original pull).
"""

import cdsapi
import pandas as pd

import pull_cmip6_projections_ssp245 as base

YEARS_NEW = [str(y) for y in range(2046, 2101)]   # 2046-2100, 55 years


def download_new_years(city, cfg):
    cfg["nc_dir"].mkdir(exist_ok=True)
    c = cdsapi.Client()
    print(f"[{city}] submitting CDS requests for {base.MODEL}/{base.EXPERIMENT}, "
          f"{YEARS_NEW[0]}-{YEARS_NEW[-1]} ({len(base.VARIABLES)} separate requests, one per "
          f"variable) ...")
    for variable in base.VARIABLES:
        out_path = cfg["nc_dir"] / f"{variable}_2046_2100.nc"
        if out_path.exists():
            print(f"[{city}] {variable} 2046-2100 already downloaded -> {out_path}, skipping")
            continue
        print(f"[{city}] submitting {variable} for 2046-2100 ...")
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
        print(f"[{city}] {variable} 2046-2100 download complete -> {out_path}")


def load_and_combine(city, cfg):
    df = None
    for variable in base.VARIABLES:
        old = base.load_variable_frame(cfg["nc_dir"] / f"{variable}.nc")
        new = base.load_variable_frame(cfg["nc_dir"] / f"{variable}_2046_2100.nc")
        var_df = (pd.concat([old, new], ignore_index=True)
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

    long_term_dir = base.DATA_DIR.parent.parent / "Projected_Long_Term_2100" / "SSP2-4.5" / "data"
    long_term_dir.mkdir(parents=True, exist_ok=True)
    out_csv = long_term_dir / f"{city}_cmip6_ssp245_2026_2100.csv"
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
    print("  Projected_Long_Term_2100/SSP2-4.5/data/seville_cmip6_ssp245_2026_2100.csv")
    print("  Projected_Long_Term_2100/SSP2-4.5/data/larissa_cmip6_ssp245_2026_2100.csv")
