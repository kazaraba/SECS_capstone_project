#!/usr/bin/env python3
"""
fetch_cmip6_projections.py

Pull CMIP6 SSP5-8.5 daily projections (2026-2045) for Seville + Larissa from the
Copernicus CDS, then merge to one tidy daily CSV per city.

Request shape copied from the CDS "Show API request" output, so it is confirmed
valid: no `day` field, no `level` field, all 20 years in a single request.

Stages:
    python fetch_cmip6_projections.py download   # 12 requests (6 vars x 2 cities)
    python fetch_cmip6_projections.py extract    # unzip
    python fetch_cmip6_projections.py merge      # units, RH derivation -> CSV
    python fetch_cmip6_projections.py status     # what's done

Credentials: ~/.cdsapirc (CDS portal, NOT the EWDS one).
"""

import os
import sys
import glob
import time
import zipfile
import traceback

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
DATASET = "projections-cmip6"

# EC-Earth3 is NOT offered for daily SSP5-8.5 in the CDS CMIP6 subset (greyed
# out in the download form). EC-Earth3-CC substituted: same atmospheric
# component and ~0.7 deg resolution, plus an interactive carbon cycle.
MODEL = "ec_earth3_cc"
EXPERIMENT = "ssp5_8_5"

YEARS = [str(y) for y in range(2026, 2046)]
MONTHS = [f"{m:02d}" for m in range(1, 13)]

# Only these six are available for this model at daily resolution.
# near_surface_relative_humidity and near_surface_wind_speed are NOT published;
# relative humidity is derived from huss + tas + psl in the merge stage.
VARIABLES = {
    "near_surface_air_temperature":               "tas",
    "daily_maximum_near_surface_air_temperature": "tasmax",
    "daily_minimum_near_surface_air_temperature": "tasmin",
    "precipitation":                              "pr",
    "near_surface_specific_humidity":             "huss",
    "sea_level_pressure":                         "psl",
}

# request_area is [North, West, South, East] -- padded to integers so it always
# contains several ~0.7 deg grid cells. analysis_box is the real target box.
CITIES = {
    "seville": {
        "request_area": [39, -8, 36, -4],
        "analysis_box": [37.6, -6.2, 37.2, -5.7],
        "centre": (37.39, -5.98),
    },
    "larissa": {
        "request_area": [41, 21, 38, 24],
        "analysis_box": [39.8, 22.2, 39.4, 22.7],
        "centre": (39.64, 22.42),
    },
}

RAW_DIR = os.path.join("data", "raw_cmip6")
NC_DIR = os.path.join(RAW_DIR, "nc")
OUT_DIR = "data"

RETRIES = 3
RETRY_SLEEP = 60


# --------------------------------------------------------------------------
# STAGE 1: download
# --------------------------------------------------------------------------
def _attempt(client, request, target_tmp, label):
    """One retrieve with retries. Returns final path, or None on failure."""
    for attempt in range(1, RETRIES + 1):
        try:
            print(f"  {label} (attempt {attempt})", flush=True)
            client.retrieve(DATASET, request, target_tmp)
            with open(target_tmp, "rb") as fh:
                magic = fh.read(2)
            ext = ".zip" if magic == b"PK" else ".nc"
            final = os.path.splitext(target_tmp)[0] + ext
            os.replace(target_tmp, final)
            size = os.path.getsize(final) / 1024
            print(f"    ok  {os.path.basename(final)}  {size:.0f} KB", flush=True)
            return final
        except Exception as exc:
            msg = " | ".join(str(exc).strip().splitlines()[:3])[:250]
            print(f"    ! {msg}", flush=True)
            if "ensemble" in msg.lower() or "variant" in msg.lower():
                if "ensemble_member" not in request:
                    request["ensemble_member"] = "r1i1p1f1"
                    print("    -> retrying with ensemble_member=r1i1p1f1",
                          flush=True)
                    continue
            if attempt < RETRIES:
                time.sleep(RETRY_SLEEP)
    return None


def stage_download():
    import cdsapi

    os.makedirs(RAW_DIR, exist_ok=True)
    client = cdsapi.Client()

    jobs = [(c, v) for c in CITIES for v in VARIABLES]
    print(f"[download] {len(jobs)} requests "
          f"({len(CITIES)} cities x {len(VARIABLES)} variables, "
          f"all {len(YEARS)} years per request)")

    done = skipped = failed = 0

    for i, (city, var) in enumerate(jobs, 1):
        short = VARIABLES[var]
        stem = f"{city}_{short}_{YEARS[0]}_{YEARS[-1]}"

        have = [p for p in glob.glob(os.path.join(RAW_DIR, f"{city}_{short}_*"))
                if p.endswith((".zip", ".nc"))]
        if have:
            skipped += 1
            continue

        print(f"\n[{i}/{len(jobs)}] {city} / {short}", flush=True)
        request = {
            "temporal_resolution": "daily",
            "experiment": EXPERIMENT,
            "variable": var,
            "model": MODEL,
            "year": YEARS,
            "month": MONTHS,
            "area": CITIES[city]["request_area"],
        }

        got = _attempt(client, request,
                       os.path.join(RAW_DIR, stem + ".download"), stem)

        if got is None:
            # whole-range request failed -- drop to one year at a time
            print(f"    full range failed; falling back to per-year for {short}",
                  flush=True)
            n_ok = 0
            for year in YEARS:
                ystem = f"{city}_{short}_{year}"
                if [p for p in glob.glob(os.path.join(RAW_DIR, ystem + ".*"))
                        if p.endswith((".zip", ".nc"))]:
                    n_ok += 1
                    continue
                yreq = dict(request, year=[year])
                if _attempt(client, yreq,
                            os.path.join(RAW_DIR, ystem + ".download"),
                            ystem) is not None:
                    n_ok += 1
            if n_ok:
                done += 1
                print(f"    recovered {n_ok}/{len(YEARS)} years", flush=True)
            else:
                failed += 1
                open(os.path.join(RAW_DIR, stem + ".failed"), "w").close()
        else:
            done += 1

    print(f"\n[download] new={done} already-had={skipped} failed={failed}")
    if failed:
        print("[download] rm data/raw_cmip6/*.failed then re-run to retry")


# --------------------------------------------------------------------------
# STAGE 2: extract
# --------------------------------------------------------------------------
def stage_extract():
    os.makedirs(NC_DIR, exist_ok=True)
    n = 0
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.zip"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        with zipfile.ZipFile(path) as zf:
            for member in zf.namelist():
                if not member.lower().endswith(".nc"):
                    continue
                out = os.path.join(NC_DIR, f"{stem}__{os.path.basename(member)}")
                if os.path.exists(out):
                    continue
                with zf.open(member) as src, open(out, "wb") as dst:
                    dst.write(src.read())
                n += 1
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.nc"))):
        out = os.path.join(NC_DIR, os.path.basename(path))
        if not os.path.exists(out):
            with open(path, "rb") as src, open(out, "wb") as dst:
                dst.write(src.read())
            n += 1
    total = len(glob.glob(os.path.join(NC_DIR, "*.nc")))
    print(f"[extract] {n} new -> {NC_DIR}   ({total} total)")


# --------------------------------------------------------------------------
# STAGE 3: merge
# --------------------------------------------------------------------------
def open_nc(xr, path):
    try:
        coder = xr.coders.CFDatetimeCoder(use_cftime=True)
        return xr.open_dataset(path, decode_times=coder)
    except AttributeError:
        return xr.open_dataset(path, use_cftime=True)
    except Exception:
        return xr.open_dataset(path, decode_times=False)


def _axis(obj, names):
    for cand in names:
        if cand in obj.coords:
            return cand
    return None


def lat_of(o):
    return _axis(o, ("lat", "latitude", "y"))


def lon_of(o):
    return _axis(o, ("lon", "longitude", "x"))


def time_of(o):
    return _axis(o, ("time", "valid_time"))


def normalise_lon(ds):
    """Force longitude onto -180..180 and re-sort. Seville sits at negative
    longitude, so a 0..360 axis would break nearest-neighbour selection."""
    ln = lon_of(ds)
    if ln is None:
        return ds
    if float(ds[ln].max()) > 180.0:
        ds = ds.assign_coords({ln: (((ds[ln] + 180) % 360) - 180)}).sortby(ln)
    return ds


def convert_units(da, short):
    """CMIP6 native units -> analysis units."""
    if short in ("tas", "tasmax", "tasmin"):
        if float(da.max()) > 200:
            da = da - 273.15
        return da, "degC"
    if short == "pr":
        return da * 86400.0, "mm/day"      # flux, NOT the ERA5 tp x1000
    if short == "psl":
        return da / 100.0, "hPa"
    if short == "huss":
        return da, "kg/kg"
    return da, "unknown"


def derive_rh(tas_c, huss, psl_hpa):
    """Relative humidity (%) from specific humidity, temperature, pressure.

    hurs is not published for this model, so it is reconstructed:
      mixing ratio    w  = q / (1 - q)
      vapour pressure e  = w * p / (0.622 + w)
      saturation      es = 6.112 * exp(17.67 T / (T + 243.5))   [Magnus, hPa]
      RH = 100 * e / es
    Same Magnus coefficients as the ERA5 side of the pipeline, so the historical
    and projection humidity series stay methodologically consistent.
    """
    import numpy as np

    w = huss / (1.0 - huss)
    e = w * psl_hpa / (0.622 + w)
    es = 6.112 * np.exp(17.67 * tas_c / (tas_c + 243.5))
    return (100.0 * e / es).clip(0, 100)


def collapse_to_point(da, box, centre, label):
    """Mean of grid cells inside the analysis box; nearest cell if none."""
    lat_n, lon_n = lat_of(da), lon_of(da)
    if lat_n is None or lon_n is None:
        return da

    n, w, s, e = box
    inside = da.sel({lat_n: slice(min(s, n), max(s, n)),
                     lon_n: slice(min(w, e), max(w, e))})
    n_lat = inside.sizes.get(lat_n, 0)
    n_lon = inside.sizes.get(lon_n, 0)

    if n_lat and n_lon:
        print(f"    {label}: {n_lat * n_lon} cell(s) in box "
              f"({n_lat} lat x {n_lon} lon) -> mean")
        return inside.mean(dim=[lat_n, lon_n])

    clat, clon = centre
    picked = da.sel({lat_n: clat, lon_n: clon}, method="nearest")
    print(f"    {label}: box smaller than model grid -> nearest cell "
          f"lat={float(picked[lat_n]):.3f} lon={float(picked[lon_n]):.3f}")
    return picked


def load_variable(xr, city, short, cfg):
    """All files for one city+variable -> one pandas Series."""
    import numpy as np
    import pandas as pd

    files = sorted(glob.glob(os.path.join(NC_DIR, f"{city}_{short}_*.nc")))
    if not files:
        print(f"  - {short}: no files, skipping")
        return None, None

    pieces = []
    for f in files:
        ds = normalise_lon(open_nc(xr, f))
        cands = [v for v in ds.data_vars if v == short] or [
            v for v in ds.data_vars
            if ds[v].ndim >= 2 and "bnd" not in v and "bound" not in v
        ]
        if not cands:
            ds.close()
            continue
        da = collapse_to_point(ds[cands[0]], cfg["analysis_box"], cfg["centre"],
                               f"{short} {os.path.basename(f)[:38]}")
        pieces.append(da.load())
        ds.close()

    if not pieces:
        return None, None

    tname = time_of(pieces[0]) or "time"
    da = xr.concat(pieces, dim=tname).sortby(tname).drop_duplicates(tname)
    da, unit = convert_units(da, short)

    idx = pd.to_datetime(da[tname].dt.strftime("%Y-%m-%d").values)
    s = pd.Series(np.asarray(da.values).ravel(), index=idx, name=short)
    print(f"  - {short}: {len(s)} days, {s.index.min().date()} -> "
          f"{s.index.max().date()}, {unit}, mean={float(s.mean()):.2f}")
    return s, unit


def stage_merge():
    import pandas as pd
    import xarray as xr

    os.makedirs(OUT_DIR, exist_ok=True)

    for city, cfg in CITIES.items():
        print(f"[merge] {city}")
        series = {}
        for short in VARIABLES.values():
            s, _ = load_variable(xr, city, short, cfg)
            if s is not None:
                series[short] = s

        if not series:
            print(f"  !! nothing to write for {city}")
            continue

        df = pd.concat(series.values(), axis=1).sort_index()

        if {"tas", "huss", "psl"} <= set(df.columns):
            df["hurs_derived"] = derive_rh(df["tas"], df["huss"], df["psl"])
            print(f"  - hurs_derived: mean={df['hurs_derived'].mean():.1f} %")
        else:
            missing = {"tas", "huss", "psl"} - set(df.columns)
            print(f"  - hurs_derived: skipped, missing {sorted(missing)}")

        df.index.name = "date"
        out = os.path.join(OUT_DIR, f"{city}_cmip6_ssp585_daily_2026_2045.csv")
        df.to_csv(out, float_format="%.4f")
        print(f"  -> {out}  ({len(df)} rows, {len(df.columns)} cols)")
        gaps = df.isna().sum()
        if gaps.any():
            print(f"     missing values:\n{gaps[gaps > 0].to_string()}")
        else:
            print("     no missing values")


# --------------------------------------------------------------------------
# STAGE 4: status
# --------------------------------------------------------------------------
def stage_status():
    print(f"[status] model={MODEL}  experiment={EXPERIMENT}  "
          f"{YEARS[0]}-{YEARS[-1]}")
    got = len([p for p in glob.glob(os.path.join(RAW_DIR, "*"))
               if p.endswith((".zip", ".nc"))])
    print(f"[status] raw downloads {got}   "
          f"extracted {len(glob.glob(os.path.join(NC_DIR, '*.nc')))}   "
          f"failed-markers {len(glob.glob(os.path.join(RAW_DIR, '*.failed')))}")
    for city in CITIES:
        for short in VARIABLES.values():
            n = len([p for p in
                     glob.glob(os.path.join(RAW_DIR, f"{city}_{short}_*"))
                     if p.endswith((".zip", ".nc"))])
            print(f"  {city:8s} {short:8s} {n:2d} file(s)"
                  f"{'' if n else '   <-- MISSING'}")


STAGES = {
    "download": stage_download,
    "extract": stage_extract,
    "merge": stage_merge,
    "status": stage_status,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        print(__doc__)
        print("stages:", ", ".join(STAGES))
        sys.exit(1)
    try:
        STAGES[sys.argv[1]]()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
