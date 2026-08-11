"""
Extend the CMIP6 SSP5-8.5 projection pull from 2026-2045 through 2046-2061, for both Seville and
Larissa. Mirrors extend_data_2021_2025.py's pattern for the ERA5 historical pull: download only
the new years, load what pull_cmip6_projections.py already fetched for 2026-2045 (no re-download
of those 14 files), concatenate, and write a new combined CSV covering 2026-2061.

Reuses model, variable list, bounding boxes, and all derivation/dedup logic unchanged from
pull_cmip6_projections.py -- see that module's docstring for the full history of corrections
(model choice, RH derivation, one-variable-per-request, grid sizing, bnds dedup) this extension
depends on staying identical. Do not change MODEL/VARIABLES/CITIES independently in one script
without updating the other; a mismatch would silently produce inconsistent 2026-2045 vs 2046-2061
halves of the combined series.

Requires a working ~/.cdsapirc (same credentials as the original pull).
"""

import cdsapi
import pandas as pd

import pull_cmip6_projections as base

YEARS_NEW = [str(y) for y in range(2046, 2062)]   # 2046-2061, 16 years


def download_new_years(city, cfg):
    cfg["nc_dir"].mkdir(exist_ok=True)
    c = cdsapi.Client()
    print(f"[{city}] submitting CDS requests for {base.MODEL}/{base.EXPERIMENT}, "
          f"{YEARS_NEW[0]}-{YEARS_NEW[-1]} ({len(base.VARIABLES)} separate requests, one per "
          f"variable -- same reason as the original pull, see pull_cmip6_projections.py "
          f"docstring point 3) ...")
    for variable in base.VARIABLES:
        out_path = cfg["nc_dir"] / f"{variable}_2046_2061.nc"
        if out_path.exists():
            print(f"[{city}] {variable} 2046-2061 already downloaded -> {out_path}, skipping")
            continue
        print(f"[{city}] submitting {variable} for 2046-2061 ...")
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
        print(f"[{city}] {variable} 2046-2061 download complete -> {out_path}")


def load_and_combine(city, cfg):
    df = None
    for variable in base.VARIABLES:
        old = base.load_variable_frame(cfg["nc_dir"] / f"{variable}.nc")
        new = base.load_variable_frame(cfg["nc_dir"] / f"{variable}_2046_2061.nc")
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

    out_csv = base.DATA_DIR / f"{city}_cmip6_ssp585_2026_2061.csv"
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

    print("\nExtension pull done. Combined files cover 2026-2061 for both cities:")
    print("  data/seville_cmip6_ssp585_2026_2061.csv")
    print("  data/larissa_cmip6_ssp585_2026_2061.csv")
    print("\nThe original 2026-2045-only combined CSVs are untouched by this script (though")
    print("pull_cmip6_projections.py's own bnds-dedup fix already regenerated them cleanly).")
    print("Update seville_cmip6_projection_eda.ipynb's RAW_CSV constant to the new *_2026_2061.csv")
    print("path (and adjust exported filenames/labels) to analyze the extended period.")
