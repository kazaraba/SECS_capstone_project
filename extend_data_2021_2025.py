"""
Extend Seville and Larissa ERA5 historical records from 2020 through 2025.

Standalone data-acquisition step, kept separate from the seville_era5_eda.ipynb /
larissa_era5_eda.ipynb analysis notebooks. It:

  1. Downloads 2021-2025 ERA5 data for both cities via the CDS API.
  2. Loads the existing 1990-2020 raw files.
  3. Normalizes both to the same core raw columns (handles Seville's
     'tp(total precipitation) meters' column-naming quirk and Larissa's
     pre-computed *_celsius columns from the old raw file).
  4. Concatenates, de-duplicates, sorts, and writes a new combined CSV per
     city covering 1990-2025.

After running this, update the `CSV` constant in each EDA notebook's section 1.4
to point at the new combined file, then re-run the notebook top to bottom.

Requires a working ~/.cdsapirc (same credentials used for the original pull).
"""

import zipfile
import cdsapi
import xarray as xr
import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")  # adjust if your existing CSVs live elsewhere
DATA_DIR.mkdir(exist_ok=True)

VARIABLES = [
    '2m_temperature', 'total_precipitation',
    '10m_u_component_of_wind', '10m_v_component_of_wind',
    '2m_dewpoint_temperature',
]
YEARS_NEW = [str(y) for y in range(2021, 2026)]  # 2021-2025
MONTHS = [f'{m:02d}' for m in range(1, 13)]
DAYS = [f'{d:02d}' for d in range(1, 32)]
TIMES = ['00:00', '06:00', '12:00', '18:00']

CITIES = {
    "seville": {
        "area": [37.6, -6.2, 37.2, -5.7],
        "existing_csv": DATA_DIR / "seville_era5_combined_1990_2020.csv",
        "new_nc_template": DATA_DIR / "seville_era5_{year}.nc",
        "combined_csv": DATA_DIR / "seville_era5_combined_1990_2025.csv",
    },
    "larissa": {
        "area": [39.8, 22.2, 39.4, 22.7],  # corrected box -- matches existing grid points
        "existing_csv": DATA_DIR / "larissa_era5_historical.csv",
        "new_nc_template": DATA_DIR / "larissa_era5_{year}.nc",
        "combined_csv": DATA_DIR / "larissa_era5_combined_1990_2025.csv",
    },
}

CORE_COLUMNS = ["valid_time", "latitude", "longitude", "tp", "t2m", "u10", "v10", "d2m"]


def download(city, cfg):
    c = cdsapi.Client()
    for year in YEARS_NEW:
        nc_path = Path(str(cfg["new_nc_template"]).format(year=year))
        if nc_path.exists():
            print(f"[{city}] {year} already downloaded -> {nc_path}, skipping")
            continue
        print(f"[{city}] submitting CDS request for {year} ...")
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': ['reanalysis'],
                'variable': VARIABLES,
                'year': [year], 'month': MONTHS, 'day': DAYS, 'time': TIMES,
                'area': cfg["area"],
                'data_format': 'netcdf',
            },
            str(nc_path),
        )
        print(f"[{city}] {year} download complete -> {nc_path}")


def normalize_existing(path):
    """Load an existing raw CSV and reduce it to the core raw columns, regardless
    of quirks in column naming (e.g. Seville's 'tp(total precipitation) meters'
    or Larissa's pre-computed *_celsius columns)."""
    df = pd.read_csv(path)
    df.columns = [c.split("(")[0].strip() for c in df.columns]  # strip unit suffixes
    df["valid_time"] = pd.to_datetime(df["valid_time"])
    keep = [c for c in CORE_COLUMNS if c in df.columns]
    return df[keep]


def _open_year_datasets(nc_path):
    """CDS sometimes returns a zip of multiple NetCDFs (one per stepType, e.g.
    instantaneous vars vs. accumulated vars like precipitation) instead of a
    single raw NetCDF, despite the .nc extension. Handle both cases."""
    if zipfile.is_zipfile(nc_path):
        extract_dir = nc_path.parent / f".{nc_path.stem}_extracted"
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(nc_path) as zf:
            zf.extractall(extract_dir)
            members = [extract_dir / name for name in zf.namelist()]
        return [xr.open_dataset(m) for m in members]
    return [xr.open_dataset(nc_path)]


def normalize_new(nc_paths):
    """Load the freshly downloaded per-year NetCDFs and flatten to the same core columns."""
    frames = []
    for nc_path in nc_paths:
        piece_dfs = []
        for ds in _open_year_datasets(nc_path):
            d = ds.to_dataframe().reset_index()
            if "time" in d.columns and "valid_time" not in d.columns:
                d = d.rename(columns={"time": "valid_time"})
            d["valid_time"] = pd.to_datetime(d["valid_time"])
            piece_dfs.append(d)

        df = piece_dfs[0]
        for extra in piece_dfs[1:]:
            merge_keys = [c for c in ("valid_time", "latitude", "longitude")
                          if c in df.columns and c in extra.columns]
            new_cols = merge_keys + [c for c in extra.columns if c not in df.columns]
            df = df.merge(extra[new_cols], on=merge_keys, how="outer")

        keep = [c for c in CORE_COLUMNS if c in df.columns]
        frames.append(df[keep])
    return pd.concat(frames, ignore_index=True)


def merge_city(city, cfg):
    old = normalize_existing(cfg["existing_csv"])
    nc_paths = [Path(str(cfg["new_nc_template"]).format(year=year)) for year in YEARS_NEW]
    new = normalize_new(nc_paths)

    combined = pd.concat([old, new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["valid_time", "latitude", "longitude"])
    combined = combined.sort_values(["valid_time", "latitude", "longitude"]).reset_index(drop=True)

    combined.to_csv(cfg["combined_csv"], index=False)

    print(f"[{city}] combined record: {combined['valid_time'].min()} -> "
          f"{combined['valid_time'].max()}, {len(combined):,} rows -> {cfg['combined_csv']}")

    # Quick sanity check: timestamps should be almost entirely 6 hours apart,
    # with no unexpected gaps introduced at the 2020/2021 seam.
    gap_check = combined.drop_duplicates("valid_time")["valid_time"].sort_values()
    diffs = gap_check.diff().value_counts()
    print(f"[{city}] timestamp gap distribution (expect ~all 0 days 06:00:00):")
    print(diffs.head())


if __name__ == "__main__":
    for city, cfg in CITIES.items():
        download(city, cfg)

    for city, cfg in CITIES.items():
        merge_city(city, cfg)

    print("\nDone. Next step: update the `CSV` constant in each EDA notebook's "
          "section 1.4 to point at the new *_combined_1990_2025.csv file, then "
          "re-run the notebook top to bottom.")
