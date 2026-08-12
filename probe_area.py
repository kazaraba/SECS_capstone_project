"""Does area subsetting work with ec_earth3_cc, and which longitude convention?"""
import cdsapi
from pathlib import Path

Path("data/cmip6_diag").mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

BASE = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "variable": "daily_maximum_near_surface_air_temperature",
    "model": "ec_earth3_cc",
    "level": "single_levels",
    "year": ["2026"],
    "month": ["01"],
    "day": [f"{d:02d}" for d in range(1, 32)],
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}

TESTS = [
    ("B1_larissa",        [40.5, 21.5, 38.5, 23.5]),
    ("B2_seville_negLon", [38.5, -7.0, 36.5, -4.5]),
    ("B3_seville_0to360", [38.5, 353.0, 36.5, 355.5]),
]

rows = []
for name, area in TESTS:
    print(f"\n--- {name}: {area}")
    try:
        client.retrieve("projections-cmip6", {**BASE, "area": area},
                        f"data/cmip6_diag/{name}.zip")
        size = Path(f"data/cmip6_diag/{name}.zip").stat().st_size
        print(f"    PASS ({size:,} bytes)")
        rows.append((name, "PASS", f"{size:,} bytes"))
    except Exception as exc:
        msg = str(exc).splitlines()[-1][:90]
        print(f"    FAIL: {msg}")
        rows.append((name, "FAIL", msg))

print("\n=== AREA RESULTS ===")
for name, status, detail in rows:
    print(f"{status:5s}  {name:20s}  {detail}")
