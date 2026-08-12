"""Isolate the cause of RoocsValueError by testing one variable at a time."""
import cdsapi
from pathlib import Path

Path("data/cmip6_diag").mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

BASE = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "variable": "daily_maximum_near_surface_air_temperature",
    "model": "ec_earth3",
    "level": "single_levels",
    "date": "2026-01-01/2026-01-31",   # one month keeps it fast
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}

TESTS = [
    ("T1_no_area",        {}),
    ("T2_larissa_posLon", {"area": [40.5, 21.5, 38.5, 23.5]}),
    ("T3_seville_negLon", {"area": [38.5, -7.0, 36.5, -4.5]}),
    ("T4_seville_0to360", {"area": [38.5, 353.0, 36.5, 355.5]}),
]

results = []
for name, extra in TESTS:
    req = {**BASE, **extra}
    target = f"data/cmip6_diag/{name}.zip"
    print(f"\n--- {name}: area={extra.get('area', 'GLOBAL')}")
    try:
        client.retrieve("projections-cmip6", req, target)
        size = Path(target).stat().st_size
        print(f"    PASS ({size:,} bytes)")
        results.append((name, "PASS", f"{size:,} bytes"))
    except Exception as exc:
        msg = str(exc).splitlines()[-1][:120]
        print(f"    FAIL: {msg}")
        results.append((name, "FAIL", msg))

print("\n=== RESULTS ===")
for name, status, detail in results:
    print(f"{status:5s}  {name:22s}  {detail}")
