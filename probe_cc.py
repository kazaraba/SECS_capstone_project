"""Confirm ec_earth3_cc works, determine the correct time key, and check all six variables."""
import cdsapi
from pathlib import Path

Path("data/cmip6_diag").mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

MODEL = "ec_earth3_cc"

BASE = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "model": MODEL,
    "level": "single_levels",
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}

TIME_KEYS = {
    "date_range": {"date": "2026-01-01/2026-01-31"},
    "year_month_day": {
        "year": ["2026"],
        "month": ["01"],
        "day": [f"{d:02d}" for d in range(1, 32)],
    },
}

VARIABLES = [
    "daily_maximum_near_surface_air_temperature",
    "daily_minimum_near_surface_air_temperature",
    "near_surface_air_temperature",
    "precipitation",
    "near_surface_relative_humidity",
    "near_surface_wind_speed",
]


def try_request(tag, extra):
    req = {**BASE, **extra}
    target = f"data/cmip6_diag/{tag}.zip"
    try:
        client.retrieve("projections-cmip6", req, target)
        return True, f"{Path(target).stat().st_size:,} bytes"
    except Exception as exc:
        return False, str(exc).splitlines()[-1][:90]


# --- Phase 1: which time key works?
print("=== phase 1: time key ===")
working_key = None
for label, tk in TIME_KEYS.items():
    ok, detail = try_request(
        f"tk_{label}",
        {**tk, "variable": VARIABLES[0]},
    )
    print(f"  {'PASS' if ok else 'FAIL'}  {label:16s}  {detail}")
    if ok and working_key is None:
        working_key = tk
        working_label = label

if working_key is None:
    raise SystemExit("\nBoth time keys failed - stop and report this output.")

print(f"\nusing: {working_label}")

# --- Phase 2: which variables exist at daily resolution?
print("\n=== phase 2: variables ===")
rows = []
for var in VARIABLES:
    ok, detail = try_request(f"var_{var}", {**working_key, "variable": var})
    print(f"  {'PASS' if ok else 'FAIL'}  {var:48s}  {detail}")
    rows.append((var, "PASS" if ok else "FAIL", detail))

print("\n=== SUMMARY ===")
print(f"model      : {MODEL}")
print(f"time key   : {working_label}")
for var, status, detail in rows:
    print(f"{status:5s}  {var}")
