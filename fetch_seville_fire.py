#!/usr/bin/env python3
"""
Seville fire-weather data pull.

Two independent sources, deliberately kept separate because they are NOT the
same product and must not be silently merged:

  A) cems-fire-historical-v1  (CEMS Early Warning Data Store, *not* CDS)
     ERA5-forced GEFF reanalysis of daily fire danger indices. This is the
     one that can support H2 (daily FWI vs daily heat + dryness).

  B) sis-ecde-climate-indicators  (CDS)
     Annual ECDE indicators. Per the ECDE catalogue overview, the fire
     variables ('days_with_high_fire_danger', 'fire_weather_index') are the
     ones sourced from the SIS Tourism *projections* dataset (EURO-CORDEX,
     bias-corrected against reanalysis FWI over 1981-2010) rather than from
     ERA5 directly. Whether origin='reanalysis' is even a legal combination
     for those two variables is NOT confirmed -- run `python
     fetch_seville_fire.py ecde-check` first, which prints the dataset's own
     constraints, before assuming it is.

Usage
-----
    python fetch_seville_fire.py fwi-download    # EWDS, per-year, resumable
    python fetch_seville_fire.py fwi-subset      # local -> data/*.csv
    python fetch_seville_fire.py ecde-check      # print legal ECDE combos
    python fetch_seville_fire.py ecde-download   # only if ecde-check says ok
    python fetch_seville_fire.py ecde-subset

Credentials
-----------
EWDS is a separate portal from CDS with a separate API key. ~/.cdsapirc will
NOT work for it. Put the EWDS key in ~/.ewdsapirc as:

    url: https://ewds.climate.copernicus.eu/api
    key: <your EWDS personal access token>

This script reads that file explicitly for the fire download and falls back to
the CDSAPI_URL / CDSAPI_KEY environment variables.
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- config ----

DATA = Path("data")
RAW_FWI = DATA / "raw_fwi"
RAW_ECDE = DATA / "raw_ecde"

YEAR_MIN, YEAR_MAX = 1990, 2025

# Seville: same 2x2 block of cells used for the heat indicators, plus a small
# pad so that request-time area cropping cannot clip the cells we want.
SEVILLE_LATS = [37.50, 37.25]
SEVILLE_LONS = [-6.00, -5.75]
AREA = [38.0, -6.5, 37.0, -5.5]        # N, W, S, E  (padded)

# FWI itself plus the two moisture codes that carry the "dryness" signal H2
# needs. DC has a ~52-day time constant, FFMC ~16 hours -- between them they
# separate slow soil/fuel drying from same-day flammability.
FWI_VARIABLES = [
    "fire_weather_index",
    "drought_code",
    "fine_fuel_moisture_code",
    "build_up_index",
    "initial_fire_spread_index",
]

ECDE_VARIABLES = ["days_with_high_fire_danger", "fire_weather_index"]

EWDS_DATASET = "cems-fire-historical-v1"
ECDE_DATASET = "sis-ecde-climate-indicators"


# ------------------------------------------------------------- helpers -----


def _client(rcfile: str):
    """Build a cdsapi client for a specific portal."""
    import cdsapi

    path = Path(os.path.expanduser(rcfile))
    if path.exists():
        url = key = None
        for line in path.read_text().splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k.strip() == "url":
                url = v.strip()
            elif k.strip() == "key":
                key = v.strip()
        if url and key:
            return cdsapi.Client(url=url, key=key)
        raise SystemExit(f"{path} exists but has no usable url:/key: lines")

    if os.environ.get("CDSAPI_URL") and os.environ.get("CDSAPI_KEY"):
        print(f"[info] {path} not found, falling back to CDSAPI_* env vars")
        return cdsapi.Client()

    raise SystemExit(
        f"no credentials: create {path} (see the docstring) or export "
        "CDSAPI_URL / CDSAPI_KEY"
    )


def _is_zip(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(4) == b"PK\x03\x04"


def _netcdfs(path: Path, workdir: Path) -> list[Path]:
    """Return the .nc file(s) inside path, extracting first if it is a ZIP."""
    if not _is_zip(path):
        return [path]
    out = workdir / (path.stem + "_unzipped")
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.endswith((".nc", ".nc4"))]
        if not names:
            raise SystemExit(f"{path} is a ZIP with no NetCDF inside: {zf.namelist()[:5]}")
        for n in names:
            zf.extract(n, out)
    return sorted(out.rglob("*.nc")) + sorted(out.rglob("*.nc4"))


def _coord(ds, candidates):
    for c in candidates:
        if c in ds.coords or c in ds.dims:
            return c
    raise SystemExit(f"none of {candidates} found; have {list(ds.coords)}")


def _seville_block(ds, field: str) -> pd.Series:
    """Mean of the 2x2 Seville cells for one variable, indexed by time."""
    latn = _coord(ds, ["latitude", "lat"])
    lonn = _coord(ds, ["longitude", "lon"])
    timen = _coord(ds, ["valid_time", "time", "forecast_reference_time"])

    da = ds[field]

    # Normalise longitude to -180..180 and re-sort, otherwise a 0..360 axis
    # crossing the prime meridian is non-monotonic and nearest-neighbour
    # selection raises.
    lons = ds[lonn].values
    if float(np.nanmax(lons)) > 180.0:
        da = da.assign_coords({lonn: (((ds[lonn] + 180) % 360) - 180)}).sortby(lonn)

    sel = da.sel({latn: SEVILLE_LATS, lonn: SEVILLE_LONS}, method="nearest")
    got_lat = np.round(np.atleast_1d(sel[latn].values), 3).tolist()
    got_lon = np.round(np.atleast_1d(sel[lonn].values), 3).tolist()
    print(f"       {field}: cells lat={got_lat} lon={got_lon}")

    s = sel.mean(dim=[latn, lonn]).to_series()
    s.index = pd.to_datetime(ds[timen].values)
    s.name = field
    return s


# ------------------------------------------------- A) daily FWI (EWDS) -----


def fwi_download() -> None:
    """One request per year per variable. Small requests survive cost limits."""
    RAW_FWI.mkdir(parents=True, exist_ok=True)
    c = _client("~/.ewdsapirc")

    todo = [
        (y, v)
        for y in range(YEAR_MIN, YEAR_MAX + 1)
        for v in FWI_VARIABLES
        if not (RAW_FWI / f"{v}_{y}.nc").exists()
    ]
    print(f"{len(todo)} request(s) outstanding "
          f"({len(FWI_VARIABLES)} vars x {YEAR_MAX - YEAR_MIN + 1} years)")

    for i, (year, var) in enumerate(todo, 1):
        target = RAW_FWI / f"{var}_{year}.nc"
        print(f"[{i}/{len(todo)}] {var} {year} -> {target}")
        try:
            c.retrieve(
                EWDS_DATASET,
                {
                    "product_type": "reanalysis",
                    "variable": var,
                    "system_version": "4_1",
                    "dataset_type": "consolidated_dataset",
                    "year": str(year),
                    "month": [f"{m:02d}" for m in range(1, 13)],
                    "day": [f"{d:02d}" for d in range(1, 32)],
                    "grid": "0.25/0.25",
                    "area": AREA,
                    "data_format": "netcdf",
                },
                str(target),
            )
        except Exception as exc:                       # noqa: BLE001
            print(f"    FAILED: {type(exc).__name__}: {exc}")
            print("    if this says the dataset_type is invalid for a recent "
                  "year, retry that year with 'intermediate_dataset'")
            continue

    print("\ndone. files present:")
    for p in sorted(RAW_FWI.glob("*.nc")):
        print(f"  {p.name}  {p.stat().st_size/1e6:.1f} MB  "
              f"{'ZIP' if _is_zip(p) else 'nc'}")


def fwi_subset() -> None:
    import xarray as xr

    files = sorted(RAW_FWI.glob("*.nc"))
    if not files:
        raise SystemExit(f"nothing in {RAW_FWI} -- run fwi-download first")

    series: dict[str, list[pd.Series]] = {}
    for f in files:
        var = f.stem.rsplit("_", 1)[0]
        for nc in _netcdfs(f, RAW_FWI):
            ds = xr.open_dataset(nc)
            fields = [v for v in ds.data_vars if ds[v].ndim >= 2]
            if not fields:
                ds.close()
                continue
            print(f"  {f.name}: fields={fields}")
            series.setdefault(var, []).append(_seville_block(ds, fields[0]))
            ds.close()

    if not series:
        raise SystemExit("no usable fields found")

    cols = {v: pd.concat(parts).sort_index() for v, parts in series.items()}
    df = pd.DataFrame(cols)
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="first")].sort_index()

    # Integrity: a daily series should have no gaps inside its own span.
    full = pd.date_range(df.index.min(), df.index.max(), freq="D")
    gaps = full.difference(df.index)
    print(f"\nrows: {len(df)}  span: {df.index.min().date()} .. {df.index.max().date()}")
    print(f"missing days: {len(gaps)}" + (f"  first few: {list(gaps[:5])}" if len(gaps) else ""))
    print("nulls per column:\n" + df.isna().sum().to_string())

    df = df.reset_index()
    df.insert(1, "city", "Seville")
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / f"seville_fwi_daily_{YEAR_MIN}_{YEAR_MAX}.csv"
    df.to_csv(out, index=False, float_format="%.4f")
    print(f"\nwrote {out}  ({len(df)} rows, {len(df.columns)} cols)")
    print(df.head(3).to_string(index=False))
    print(df.tail(3).to_string(index=False))


# ------------------------------------------- B) annual ECDE (CDS) ----------


def ecde_check() -> None:
    """Print the dataset's own constraints so we stop guessing about origin."""
    import urllib.request

    url = (
        "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
        f"{ECDE_DATASET}/constraints"
    )
    print(f"GET {url}\n")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            blocks = json.load(r)
    except Exception as exc:                           # noqa: BLE001
        raise SystemExit(f"could not read constraints: {exc}\n"
                         "Open the Download tab in a browser instead, pick a "
                         "fire variable, and read which origins stay enabled.")

    hits = [b for b in blocks
            if any(v in b.get("variable", []) for v in ECDE_VARIABLES)]
    if not hits:
        print("No constraint block mentions the fire variables at all.")
        return
    origins, temporal, versions = set(), set(), set()
    for b in hits:
        origins.update(b.get("origin", []))
        temporal.update(b.get("temporal_aggregation", []))
        versions.update(b.get("version", []))
    print(f"blocks mentioning {ECDE_VARIABLES}: {len(hits)}")
    print(f"  origin              : {sorted(origins)}")
    print(f"  temporal_aggregation: {sorted(temporal)}")
    print(f"  version             : {sorted(versions)}")
    if "reanalysis" not in origins:
        print("\n>>> origin='reanalysis' is NOT offered for the fire variables.")
        print(">>> The annual cross-check as planned is not available. Use the")
        print(">>> CEMS daily FWI and aggregate to annual counts yourself.")


def ecde_download() -> None:
    RAW_ECDE.mkdir(parents=True, exist_ok=True)
    c = _client("~/.cdsapirc")
    for var in ECDE_VARIABLES:
        target = RAW_ECDE / f"ecde_{var}_yearly.nc"
        if target.exists():
            print(f"skip {target} (exists)")
            continue
        print(f"requesting {var} -> {target}")
        c.retrieve(
            ECDE_DATASET,
            {
                "variable": [var],
                "origin": "reanalysis",
                "temporal_aggregation": "yearly",
                "spatial_aggregation": "gridded",
                "version": "v2_0",
                "data_format": "netcdf",
            },
            str(target),
        )


def ecde_subset() -> None:
    import xarray as xr

    files = sorted(RAW_ECDE.glob("*.nc"))
    if not files:
        raise SystemExit(f"nothing in {RAW_ECDE} -- run ecde-download first")

    cols = {}
    for f in files:
        var = f.stem.replace("ecde_", "").replace("_yearly", "")
        for nc in _netcdfs(f, RAW_ECDE):
            ds = xr.open_dataset(nc)
            fields = [v for v in ds.data_vars if ds[v].ndim >= 2]
            print(f"  {f.name}: fields={fields}")
            s = _seville_block(ds, fields[0])
            cols[var] = pd.Series(s.values, index=pd.to_datetime(s.index).year)
            ds.close()

    df = pd.DataFrame(cols)
    df.index.name = "year"
    df = df.loc[(df.index >= YEAR_MIN) & (df.index <= YEAR_MAX)].reset_index()
    df.insert(1, "city", "Seville")
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / f"seville_ecde_fire_annual_{YEAR_MIN}_{YEAR_MAX}.csv"
    df.to_csv(out, index=False, float_format="%.4f")
    print(f"\nwrote {out}  ({len(df)} rows)")
    print(df.to_string(index=False))


# ---------------------------------------------------------------- entry -----

STAGES = {
    "fwi-download": fwi_download,
    "fwi-subset": fwi_subset,
    "ecde-check": ecde_check,
    "ecde-download": ecde_download,
    "ecde-subset": ecde_subset,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        raise SystemExit(__doc__)
    STAGES[sys.argv[1]]()
