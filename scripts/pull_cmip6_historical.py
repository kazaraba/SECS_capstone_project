"""
Pull CMIP6 `cmcc_esm2` historical-experiment data (1990-2014) for Seville and Larissa -- the
model's own simulated past, needed as the "model" side of a bias-correction quantile mapping
against ERA5 (the "observed" side, already available as eda_results/eda_outputs/{city}_daily.csv).

This is NOT the SSP5-8.5 projection pull (pull_cmip6_projections.py) -- it's the same model run
under the `historical` experiment instead of `ssp5_8_5`, over the period where both CMIP6 and
ERA5 exist, so the two can be compared directly. Reuses MODEL/VARIABLES/CITIES/MONTHS and all
derivation/dedup logic from pull_cmip6_projections.py unchanged -- only EXPERIMENT and YEARS
differ. See that module's docstring for the corrections (model choice, RH derivation,
one-variable-per-request, bnds dedup) this pull depends on staying identical.

1990-2014 is the full CMIP6 `historical` experiment's overlap with the ERA5 record (which starts
1990); CMIP6 historical runs end at 2014 by CMIP6 convention (SSP scenarios pick up at 2015).
Used to fit per-city, per-variable, per-calendar-month quantile mapping functions for bias
correction -- see bias_correct_cmip6_projection.py.

Requires a working ~/.cdsapirc (same credentials as the other pulls).
"""

import cdsapi

import pull_cmip6_projections as base

EXPERIMENT = "historical"
YEARS = [str(y) for y in range(1990, 2015)]   # 1990-2014, 25 years


def download(city, cfg):
    nc_dir = cfg["nc_dir"]
    nc_dir.mkdir(exist_ok=True)
    c = cdsapi.Client()
    print(f"[{city}] submitting CDS requests for {base.MODEL}/{EXPERIMENT}, "
          f"{YEARS[0]}-{YEARS[-1]} ({len(base.VARIABLES)} separate requests, one per variable) ...")
    for variable in base.VARIABLES:
        out_path = nc_dir / f"{variable}_historical_1990_2014.nc"
        if out_path.exists():
            print(f"[{city}] {variable} historical already downloaded -> {out_path}, skipping")
            continue
        print(f"[{city}] submitting {variable} (historical) ...")
        c.retrieve(
            "projections-cmip6",
            {
                "temporal_resolution": "daily",
                "experiment": EXPERIMENT,
                "variable": [variable],
                "model": base.MODEL,
                "year": YEARS,
                "month": base.MONTHS,
                "area": cfg["area"],
            },
            str(out_path),
        )
        print(f"[{city}] {variable} historical download complete -> {out_path}")


def load_and_convert(city, cfg):
    df = None
    for variable in base.VARIABLES:
        var_df = base.load_variable_frame(cfg["nc_dir"] / f"{variable}_historical_1990_2014.nc")
        if df is None:
            df = var_df
            continue
        merge_keys = [c for c in ("valid_time", "lat", "lon", "latitude", "longitude")
                      if c in df.columns and c in var_df.columns]
        new_cols = merge_keys + [c for c in var_df.columns if c not in df.columns]
        df = df.merge(var_df[new_cols], on=merge_keys, how="outer")

    df = base.add_derived_columns(df)
    df = df.sort_values("valid_time").reset_index(drop=True)

    out_csv = base.DATA_DIR / f"{city}_cmip6_historical_1990_2014.csv"
    df.to_csv(out_csv, index=False)
    print(f"[{city}] wrote {out_csv} ({len(df):,} rows, "
          f"{df['valid_time'].min()} -> {df['valid_time'].max()})")
    return df


if __name__ == "__main__":
    for city, cfg in base.CITIES.items():
        download(city, cfg)

    for city, cfg in base.CITIES.items():
        load_and_convert(city, cfg)

    print("\nHistorical pull done. Combined files:")
    print("  data/seville_cmip6_historical_1990_2014.csv")
    print("  data/larissa_cmip6_historical_1990_2014.csv")
    print("\nNext: bias_correct_cmip6_projection.py fits quantile mapping functions from these")
    print("against ERA5 (eda_results/eda_outputs/{city}_daily.csv) and applies them to the")
    print("2026-2061 SSP5-8.5 projection.")
