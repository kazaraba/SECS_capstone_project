"""Test the day-field question and huss/psl availability before the full run."""
import sys, zipfile
from pathlib import Path
import cdsapi, xarray as xr

OUT = Path("data/cmip6_preflight"); OUT.mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

BASE = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "model": "ec_earth3_cc",
    "area": [39, -8, 36, -4],
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}
MONTHS = [f"{m:02d}" for m in range(1, 13)]
DAYS = [f"{d:02d}" for d in range(1, 32)]

def fetch(tag, extra):
    z = OUT / f"{tag}.zip"
    try:
        client.retrieve("projections-cmip6", {**BASE, **extra}, str(z))
    except Exception as e:
        print(f"  FAIL  {tag}: {str(e).splitlines()[-1][:80]}")
        return None
    d = OUT / tag; d.mkdir(exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        for n in [x for x in zf.namelist() if x.endswith(".nc")]:
            zf.extract(n, d)
    ncs = list(d.rglob("*.nc"))
    if not ncs:
        print(f"  FAIL  {tag}: no .nc inside archive"); return None
    return xr.open_dataset(ncs[0], use_cftime=True)

print("=== day field: 2026 full year, tasmax ===")
V = "daily_maximum_near_surface_air_temperature"

ds = fetch("with_day", {"variable": V, "year": ["2026"], "month": MONTHS, "day": DAYS})
n_with = ds.time.size if ds is not None else None
print(f"  with day    : {n_with} steps")

ds = fetch("no_day", {"variable": V, "year": ["2026"], "month": MONTHS})
n_without = ds.time.size if ds is not None else None
print(f"  without day : {n_without} steps")

if n_with and n_without:
    print("  VERDICT: day is optional" if n_with == n_without
          else f"  VERDICT: DAY IS REQUIRED - without it you lose {n_with - n_without} steps")

print("\n=== availability: derivation inputs ===")
for var in sys.argv[1:]:
    ds = fetch(f"avail_{var}", {"variable": var, "year": ["2026"],
                                "month": ["01"], "day": DAYS})
    if ds is not None:
        dv = [v for v in ds.data_vars if "bnds" not in v]
        print(f"  PASS  {var}: {ds.time.size} steps, {dv}, "
              f"units={ds[dv[0]].attrs.get('units','?')}")
