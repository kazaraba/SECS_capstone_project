"""Verify grid coverage, box containment, time completeness, and units."""
import glob
import xarray as xr

EXPECTED_DAYS = 7305   # 2026-2045 inclusive, standard calendar w/ 5 leap years

BOXES = {
    "seville": (36.5, 38.5, -7.0, -4.5),   # S, N, W, E
    "larissa": (38.5, 40.5, 21.5, 23.5),
}

for f in sorted(glob.glob("data/cmip6_nc/*/*.nc")):
    ds = xr.open_dataset(f, use_cftime=True)
    city = f.split("/")[-2].split("_")[0]
    var = [v for v in ds.data_vars
           if v not in ("lat_bnds", "lon_bnds", "time_bnds")][0]
    a = ds[var]

    ncells = ds.lat.size * ds.lon.size
    cal = ds.time.to_index().calendar if hasattr(ds.time.to_index(), "calendar") else "?"

    print(f"\n{f.split('/')[-2]}")
    print(f"  var      : {var}  units={a.attrs.get('units','?')}")
    print(f"  cells    : {ncells}  (lat {ds.lat.size} x lon {ds.lon.size})")
    print(f"  lat      : {ds.lat.values.round(2)}")
    print(f"  lon      : {ds.lon.values.round(2)}")
    print(f"  time     : {ds.time.size} steps  calendar={cal}")
    print(f"  range    : {ds.time.values[0]} -> {ds.time.values[-1]}")
    print(f"  values   : min={float(a.min()):.4g}  max={float(a.max()):.4g}")

    if ncells == 0:
        print("  !! ZERO CELLS")
    if ds.time.size != EXPECTED_DAYS:
        print(f"  !! expected {EXPECTED_DAYS} days, got {ds.time.size}")
    if city in BOXES:
        s, n, w, e = BOXES[city]
        if float(ds.lat.min()) < s - 1.5 or float(ds.lat.max()) > n + 1.5:
            print("  !! lat outside requested box - area may be ignored")
