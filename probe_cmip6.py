"""Single small CMIP6 request to validate keys, licence, and grid coverage."""
from pathlib import Path
import cdsapi

Path("data/cmip6_raw").mkdir(parents=True, exist_ok=True)

client = cdsapi.Client()

request = {
    "temporal_resolution": "daily",
    "experiment": "ssp5_8_5",
    "variable": "daily_maximum_near_surface_air_temperature",
    "model": "ec_earth3",
    "level": "single_levels",
    "date": "2026-01-01/2026-12-31",
    "area": [38.5, -7.0, 36.5, -4.5],   # N, W, S, E - Seville, widened
    "data_format": "netcdf_legacy",
    "download_format": "zip",
}

client.retrieve(
    "projections-cmip6",
    request,
    "data/cmip6_raw/probe_seville_tasmax_2026.zip",
)
print("OK")
