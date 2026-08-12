"""Which indices-dataset models also have raw daily output in projections-cmip6?"""
import cdsapi
from pathlib import Path

Path("data/cmip6_diag").mkdir(parents=True, exist_ok=True)
client = cdsapi.Client()

CANDIDATES = ["mpi_esm1_2_lr", "canesm5", "miroc6", "ec_earth3_cc"]

# tas/tasmax/pr are the backbone; huss/psl feed the RH derivation
VARS = [
    "daily_maximum_near_surface_air_temperature",
    "near_surface_specific_humidity",
    "sea_level_pressure",
    "near_surface_wind_speed",
]

BASE = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "area": [39, -8, 36, -4],
    "year": ["2026"],
    "month": ["01"],
    "day": [f"{d:02d}" for d in range(1, 32)],
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}

grid = {}
for model in CANDIDATES:
    print(f"\n--- {model}")
    grid[model] = {}
    for var in VARS:
        try:
            client.retrieve(
                "projections-cmip6",
                {**BASE, "model": model, "variable": var},
                f"data/cmip6_diag/m_{model}_{var[:18]}.zip",
            )
            grid[model][var] = "PASS"
        except Exception:
            grid[model][var] = "fail"
        print(f"  {grid[model][var]:5s}  {var}")

print("\n=== MODEL x VARIABLE ===")
print(f"{'model':16s} " + " ".join(f"{v[:12]:12s}" for v in VARS))
for model, row in grid.items():
    print(f"{model:16s} " + " ".join(f"{row[v]:12s}" for v in VARS))
