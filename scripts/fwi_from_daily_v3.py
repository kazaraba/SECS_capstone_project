#!/usr/bin/env python
"""
fwi_from_daily.py
-----------------
Compute Canadian Fire Weather Index codes from a daily CSV of temperature,
humidity inputs and precipitation, substituting a monthly wind climatology
for wind speed.

Why wind is substituted: EC-Earth3-CC does not publish daily near-surface
wind speed under the SSP scenarios on CDS. Holding wind at ERA5 historical
climatology isolates the thermodynamic component of fire-weather change
(temperature, humidity, precipitation), which is the component that can
actually be defended. Wind is among the least reliable CMIP6 fields anyway.

Inputs
    --daily      CSV with a date index and the columns named in --map
    --wind-clim  data/wind_climatology_noon.csv (from build_wind_climatology.py)
    --lat        site latitude (FWI day-length correction depends on it)

Outputs
    CSV with dc, dmc, ffmc, isi, bui, fwi appended, plus the derived
    hurs_noon and wind_kmh actually used.

Usage
    python fwi_from_daily.py --selftest
    python fwi_from_daily.py \
        --daily data/seville_cmip6_ssp245_daily_2026_2045.csv \
        --wind-clim data/wind_climatology_noon.csv \
        --city seville --lat 37.39 \
        --out data/seville_fwi_ssp245_2026_2045.csv
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import xarray as xr

# Default column mapping. Override with --map "tasmax=tx,pr=precip,..."
DEFAULT_MAP = {
    "tasmax": "tasmax",   # deg C
    "huss": "huss",       # kg/kg specific humidity
    "psl": "psl",         # Pa sea level pressure
    "pr": "pr",           # mm/day, 24 h accumulation
}


# --- humidity ---------------------------------------------------------
def relative_humidity(huss, psl_pa, temp_c):
    """
    RH (%) from specific humidity, pressure and temperature.

    Uses tasmax rather than tas on purpose: evaluating RH at the daily
    maximum temperature yields the daily MINIMUM relative humidity, which
    is a good stand-in for the noon value FWI expects. Using tas would give
    a daily-mean RH that is systematically too moist and would bias FWI low.

    psl is sea-level pressure, not surface pressure. For Seville (~10 m) and
    Larissa (~70 m) the resulting error in RH is well under 1 %.
    """
    # vapour pressure from specific humidity (Pa)
    e = (huss * psl_pa) / (0.622 + 0.378 * huss)
    # saturation vapour pressure, Magnus over water (Pa)
    es = 611.2 * np.exp(17.67 * temp_c / (temp_c + 243.5))
    rh = 100.0 * e / es
    return np.clip(rh, 1.0, 100.0)


# --- wind climatology -------------------------------------------------
def daily_wind_from_climatology(index, clim_month_kmh):
    """
    Expand a 12-value monthly climatology to a daily series.

    Monthly means applied as step functions put a discontinuity at every
    month boundary, which shows up as sawtooth in FFMC. Instead each monthly
    value is pinned to the 15th of its month and interpolated, wrapping
    across the year boundary so December and January join smoothly.
    """
    anchors = []
    years = range(index.year.min() - 1, index.year.max() + 2)
    for y in years:
        for m in range(1, 13):
            anchors.append((pd.Timestamp(year=y, month=m, day=15),
                            clim_month_kmh[m]))
    anchor_s = pd.Series(dict(anchors)).sort_index()

    full = anchor_s.reindex(anchor_s.index.union(index)).interpolate("time")
    return full.reindex(index)


# --- FWI --------------------------------------------------------------
def compute_fwi(df, lat, ffmc0=None, dmc0=None, dc0=None):
    """
    Run xclim's Canadian Forest Fire Weather Index System.

    Returns the input frame with dc, dmc, ffmc, isi, bui, fwi appended.
    """
    from xclim.indices import fire

    time = xr.DataArray(df.index.values, dims="time", name="time")

    def da(values, units):
        arr = xr.DataArray(np.asarray(values, dtype="float64"),
                           coords={"time": time}, dims="time")
        arr.attrs["units"] = units
        return arr

    tas = da(df["tasmax_c"].values, "degC")
    pr = da(df["pr_mm"].values, "mm/day")
    wind = da(df["wind_kmh"].values, "km/h")
    hurs = da(df["hurs_noon"].values, "%")
    lat_da = xr.DataArray(float(lat))
    lat_da.attrs["units"] = "degrees_north"

    kwargs = dict(
        tas=tas, pr=pr, sfcWind=wind, hurs=hurs, lat=lat_da,
        season_method=None,      # year-round, as GEFF/CEMS does
        overwintering=False,
    )
    def code0(v):
        arr = xr.DataArray(float(v))
        arr.attrs["units"] = ""      # FWI codes are dimensionless
        return arr

    if ffmc0 is not None:
        kwargs["ffmc0"] = code0(ffmc0)
    if dmc0 is not None:
        kwargs["dmc0"] = code0(dmc0)
    if dc0 is not None:
        kwargs["dc0"] = code0(dc0)

    # xclim returns the codes in this order. Verify against CEMS on the
    # historical run before trusting the projection output.
    dc, dmc, ffmc, isi, bui, fwi = fire.cffwis_indices(**kwargs)

    out = df.copy()
    for name, arr in [("dc", dc), ("dmc", dmc), ("ffmc", ffmc),
                      ("isi", isi), ("bui", bui), ("fwi", fwi)]:
        out[name] = np.asarray(arr.values, dtype="float64")
    return out


# --- assembly ---------------------------------------------------------
def prepare(daily_csv, wind_csv, city, colmap, rh_col=None,
            wind_col=None, wind_units="m/s"):
    """
    Assemble the four FWI inputs.

    Humidity comes either from an existing column (--rh-col, e.g. ERA5's
    rh_min, which already IS the noon proxy) or is derived from specific
    humidity + pressure + tasmax (the CMIP6 route).

    Wind comes either from an existing column (--wind-col, historical runs)
    or from a monthly climatology file (projection runs, where the model
    publishes no wind).
    """
    df = pd.read_csv(daily_csv, index_col=0, parse_dates=True)
    df = df.sort_index()

    need = ["tasmax", "pr"] + ([] if rh_col else ["huss", "psl"])
    missing = [colmap[k] for k in need if colmap[k] not in df.columns]
    if rh_col and rh_col not in df.columns:
        missing.append(rh_col)
    if wind_col and wind_col not in df.columns:
        missing.append(wind_col)
    if missing:
        raise SystemExit(
            f"[error] columns not found in {daily_csv}: {missing}\n"
            f"        available: {list(df.columns)}")

    work = pd.DataFrame(index=df.index)
    work["tasmax_c"] = df[colmap["tasmax"]].astype(float)
    work["pr_mm"] = df[colmap["pr"]].astype(float)

    if rh_col:
        work["hurs_noon"] = df[rh_col].astype(float).clip(1.0, 100.0)
        print(f"[prepare] humidity: column {rh_col!r} used directly")
    else:
        work["hurs_noon"] = relative_humidity(
            df[colmap["huss"]].astype(float).values,
            df[colmap["psl"]].astype(float).values,
            work["tasmax_c"].values,
        )
        print("[prepare] humidity: derived from huss + psl + tasmax")

    if wind_col:
        factor = 3.6 if wind_units.lower() in ("m/s", "ms", "mps") else 1.0
        work["wind_kmh"] = df[wind_col].astype(float) * factor
        print(f"[prepare] wind: column {wind_col!r} x{factor} -> km/h")
    else:
        clim = pd.read_csv(wind_csv)
        clim = clim[clim["city"].str.lower() == city.lower()]
        if clim.empty:
            raise SystemExit(f"[error] no wind climatology rows for city={city!r}")
        month_kmh = dict(zip(clim["month"].astype(int), clim["wind_kmh"].astype(float)))
        if sorted(month_kmh) != list(range(1, 13)):
            raise SystemExit(f"[error] climatology for {city} has months {sorted(month_kmh)}")
        work["wind_kmh"] = daily_wind_from_climatology(work.index, month_kmh).values
        print(f"[prepare] wind: monthly climatology for {city}")

    nan = work.isna().sum()
    if nan.any():
        print("[warn] NaNs in prepared inputs:")
        print(nan[nan > 0].to_string())

    print(f"[prepare] {len(work)} days  "
          f"{work.index.min().date()} -> {work.index.max().date()}")
    print(f"          tasmax  mean {work['tasmax_c'].mean():.1f} degC")
    print(f"          hurs    mean {work['hurs_noon'].mean():.1f} %")
    src = f"column {wind_col}" if wind_col else "monthly climatology"
    print(f"          wind    mean {work['wind_kmh'].mean():.1f} km/h  ({src})")
    print(f"          precip  mean {work['pr_mm'].mean():.2f} mm/day")
    return work


def build_clim_from_daily(daily_csv, wind_col, city, out_csv,
                          wind_units="m/s", start=1991, end=2020):
    """
    Derive the monthly wind climatology from an existing daily wind column,
    so no ERA5 download is needed. Restricted to the WMO 30-year normal
    period by default.
    """
    df = pd.read_csv(daily_csv, index_col=0, parse_dates=True).sort_index()
    if wind_col not in df.columns:
        raise SystemExit(f"[error] {wind_col!r} not in {daily_csv}; "
                         f"available: {list(df.columns)}")

    s = df.loc[str(start):str(end), wind_col].astype(float).dropna()
    if s.empty:
        raise SystemExit(f"[error] no {wind_col} data in {start}-{end}")

    factor = 3.6 if wind_units.lower() in ("m/s", "ms", "mps") else 1.0
    monthly = s.groupby(s.index.month).mean()

    rows = [{
        "city": city,
        "month": int(m),
        "wind_ms": round(float(v if factor == 3.6 else v / 3.6), 4),
        "wind_kmh": round(float(v * factor), 4),
        "n_years": int(s.index.year.nunique()),
    } for m, v in monthly.items()]

    new = pd.DataFrame(rows)
    if os.path.exists(out_csv):
        old = pd.read_csv(out_csv)
        old = old[old["city"].str.lower() != city.lower()]
        new = pd.concat([old, new], ignore_index=True)
    new = new.sort_values(["city", "month"])
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    new.to_csv(out_csv, index=False)

    print(f"[clim] {city}: {len(s)} days, {s.index.year.nunique()} years "
          f"({start}-{end})")
    print(f"[clim] -> {out_csv}")
    print(new[new["city"].str.lower() == city.lower()].to_string(index=False))
    return 0


def annual_indicators(df, threshold=30.0):
    """days above threshold, and longest consecutive run above it, per year."""
    rows = []
    for year, g in df.groupby(df.index.year):
        above = (g["fwi"] > threshold).values
        best = run = 0
        for a in above:
            run = run + 1 if a else 0
            best = max(best, run)
        rows.append({
            "year": int(year),
            f"days_fwi_gt{int(threshold)}": int(above.sum()),
            "longest_high_run": int(best),
            "fwi_mean": round(float(g["fwi"].mean()), 3),
            "fwi_p95": round(float(g["fwi"].quantile(0.95)), 3),
            "fwi_max": round(float(g["fwi"].max()), 3),
        })
    return pd.DataFrame(rows).set_index("year")


# --- self test --------------------------------------------------------
def selftest():
    """Synthetic data of the correct schema, to catch runtime errors early."""
    print("[selftest] building synthetic 3-year daily series")
    idx = pd.date_range("2026-01-01", "2028-12-31", freq="D")
    doy = idx.dayofyear.values
    seasonal = np.sin((doy - 100) / 365.0 * 2 * np.pi)

    tasmax = 18.0 + 14.0 * seasonal + np.random.default_rng(0).normal(0, 2.0, len(idx))
    huss = 0.008 + 0.003 * seasonal
    psl = np.full(len(idx), 101300.0)
    pr = np.where(np.random.default_rng(1).random(len(idx)) < 0.15,
                  np.random.default_rng(2).exponential(6.0, len(idx)), 0.0)

    df = pd.DataFrame({"tasmax": tasmax, "huss": huss, "psl": psl, "pr": pr},
                      index=idx)
    df.index.name = "date"

    tmp_daily = "_selftest_daily.csv"
    tmp_clim = "_selftest_clim.csv"
    df.to_csv(tmp_daily)
    pd.DataFrame({
        "city": ["testville"] * 12,
        "month": list(range(1, 13)),
        "wind_ms": [3.0] * 12,
        "wind_kmh": [10.8] * 12,
        "n_years": [30] * 12,
    }).to_csv(tmp_clim, index=False)

    try:
        work = prepare(tmp_daily, tmp_clim, "testville", DEFAULT_MAP)
        out = compute_fwi(work, lat=37.4)
        print("\n[selftest] FWI computed. Tail:")
        print(out[["tasmax_c", "hurs_noon", "wind_kmh", "pr_mm", "ffmc", "dc", "fwi"]]
              .tail(5).round(2).to_string())
        ann = annual_indicators(out)
        print("\n[selftest] annual indicators:")
        print(ann.to_string())

        assert out["fwi"].notna().sum() > 0.9 * len(out), "too many NaN FWI values"
        assert (out["fwi"] >= 0).all(), "negative FWI"
        assert out["hurs_noon"].between(1, 100).all(), "RH out of range"
        print("\n[selftest] PASS")
        return 0
    finally:
        for f in (tmp_daily, tmp_clim):
            if os.path.exists(f):
                os.remove(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--daily")
    ap.add_argument("--wind-clim", default=os.path.join("data", "wind_climatology_noon.csv"))
    ap.add_argument("--city")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--out")
    ap.add_argument("--map", default="", help='e.g. "tasmax=tx,pr=precip"')
    ap.add_argument("--rh-col", default=None,
                    help="use this column as noon RH instead of deriving it")
    ap.add_argument("--wind-col", default=None,
                    help="use this daily wind column instead of the climatology")
    ap.add_argument("--wind-units", default="m/s", choices=["m/s", "km/h"])
    ap.add_argument("--build-clim", action="store_true",
                    help="derive the monthly climatology from --wind-col and exit")
    ap.add_argument("--clim-start", type=int, default=1991)
    ap.add_argument("--clim-end", type=int, default=2020)
    ap.add_argument("--ffmc0", type=float, default=None)
    ap.add_argument("--dmc0", type=float, default=None)
    ap.add_argument("--dc0", type=float, default=None)
    ap.add_argument("--spinup-days", type=int, default=0,
                    help="discard this many leading days after integration")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.build_clim:
        for req in ("daily", "city", "wind_col"):
            if getattr(args, req) in (None, ""):
                raise SystemExit(f"[error] --{req.replace('_','-')} is required")
        return build_clim_from_daily(args.daily, args.wind_col, args.city,
                                     args.wind_clim, args.wind_units,
                                     args.clim_start, args.clim_end)

    for req in ("daily", "city", "lat", "out"):
        if getattr(args, req) in (None, ""):
            raise SystemExit(f"[error] --{req.replace('_','-')} is required")

    colmap = dict(DEFAULT_MAP)
    for pair in filter(None, args.map.split(",")):
        k, _, v = pair.partition("=")
        colmap[k.strip()] = v.strip()

    work = prepare(args.daily, args.wind_clim, args.city, colmap,
                   rh_col=args.rh_col, wind_col=args.wind_col,
                   wind_units=args.wind_units)
    out = compute_fwi(work, args.lat, args.ffmc0, args.dmc0, args.dc0)

    if args.spinup_days:
        out = out.iloc[args.spinup_days:]
        print(f"[spinup] discarded {args.spinup_days} leading days")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    out.to_csv(args.out, float_format="%.4f")
    print(f"\n[write] {args.out}  ({len(out)} rows)")

    ann_path = args.out.replace(".csv", "_annual.csv")
    ann = annual_indicators(out)
    ann.to_csv(ann_path)
    print(f"[write] {ann_path}  ({len(ann)} years)")
    print(ann.to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
