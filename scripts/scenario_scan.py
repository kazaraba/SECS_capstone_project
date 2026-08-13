#!/usr/bin/env python
"""
scenario_scan.py
----------------
List which CMIP6 experiments (scenarios) are available on the CDS for a given
model, at a given temporal resolution, for the variables SECS depends on.

Reads the public constraints endpoint - no credentials required, no download
cost incurred. Nothing is fetched from the queue.

Usage:
    python scenario_scan.py
    python scenario_scan.py --model ec_earth3_cc
    python scenario_scan.py --model cmcc_esm2 --freq monthly
"""

import argparse
import json
import sys
import urllib.request

DATASETS = ["projections-cmip6", "sis-extreme-indices-cmip6"]

# Variables the SECS pipeline uses (plus sfcWind, the FWI blocker).
VARS_OF_INTEREST = [
    "daily_maximum_near_surface_air_temperature",
    "daily_minimum_near_surface_air_temperature",
    "near_surface_air_temperature",
    "precipitation",
    "near_surface_specific_humidity",
    "sea_level_pressure",
    "near_surface_wind_speed",
]

URL_TEMPLATES = [
    "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/{ds}/constraints.json",
    "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/{ds}/constraints",
]


def fetch_constraints(ds):
    """Return (url, list_of_constraint_blocks) for a dataset."""
    errors = []
    for tpl in URL_TEMPLATES:
        url = tpl.format(ds=ds)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "secs-scenario-scan"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.load(resp)
            if isinstance(data, list) and data:
                return url, data
            errors.append(f"{url} -> unexpected payload type {type(data).__name__}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url} -> {exc}")
    raise RuntimeError("could not fetch constraints:\n  " + "\n  ".join(errors))


def find_key(blocks, wanted):
    """Find which constraint key holds a given value. Returns None if absent."""
    for block in blocks:
        for key, values in block.items():
            if isinstance(values, list) and wanted in values:
                return key
    return None


def values_for_key(blocks, key):
    out = set()
    for block in blocks:
        out.update(block.get(key, []))
    return out


def scan(ds, model, freq):
    print("=" * 78)
    print(f"DATASET: {ds}")
    print("=" * 78)

    try:
        url, blocks = fetch_constraints(ds)
    except RuntimeError as exc:
        print(f"  SKIPPED: {exc}\n")
        return

    print(f"  source   : {url}")
    print(f"  blocks   : {len(blocks)}")

    model_key = find_key(blocks, model)
    if model_key is None:
        all_keys = sorted({k for b in blocks for k in b})
        print(f"  MODEL '{model}' NOT FOUND in this dataset.")
        print(f"  constraint keys present: {all_keys}")
        for key in all_keys:
            near = sorted(v for v in values_for_key(blocks, key) if "cmcc" in v or "ec_earth" in v)
            if near:
                print(f"  candidates under '{key}': {near}")
        print()
        return

    freq_key = find_key(blocks, freq)
    exp_key = find_key(blocks, "ssp5_8_5") or find_key(blocks, "historical")
    var_key = find_key(blocks, VARS_OF_INTEREST[0]) or find_key(blocks, "precipitation")

    print(f"  model key: {model_key!r}   freq key: {freq_key!r}")
    print(f"  exp key  : {exp_key!r}   var key : {var_key!r}")

    if exp_key is None:
        print("  No experiment-like key found; cannot enumerate scenarios.\n")
        return

    # Keep only blocks matching this model (and frequency, if that key exists).
    sel = [b for b in blocks if model in b.get(model_key, [])]
    if freq_key is not None:
        sel = [b for b in sel if freq in b.get(freq_key, [])]
        label = f"{model} @ {freq}"
    else:
        label = f"{model} (no frequency dimension in this dataset)"

    if not sel:
        print(f"  No constraint blocks for {label}.\n")
        return

    all_exps = sorted(values_for_key(sel, exp_key))
    print(f"\n  SCENARIOS AVAILABLE for {label}:")
    for exp in all_exps:
        print(f"    - {exp}")

    if var_key is None:
        print()
        return

    # Variable x experiment availability matrix.
    avail = {}
    for var in VARS_OF_INTEREST:
        exps = set()
        for block in sel:
            if var in block.get(var_key, []):
                exps.update(block.get(exp_key, []))
        avail[var] = exps

    present = [v for v in VARS_OF_INTEREST if avail[v]]
    missing = [v for v in VARS_OF_INTEREST if not avail[v]]

    if present:
        width = max(len(v) for v in present)
        header = " " * (width + 2) + "  ".join(f"{e:^14}" for e in all_exps)
        print(f"\n  VARIABLE x SCENARIO ({label}):")
        print("  " + header)
        for var in present:
            row = "  ".join(f"{('YES' if e in avail[var] else '-'):^14}" for e in all_exps)
            print(f"  {var.ljust(width)}  {row}")

    if missing:
        print(f"\n  NOT available for {label}:")
        for var in missing:
            print(f"    - {var}")
    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="cmcc_esm2")
    ap.add_argument("--freq", default="daily")
    ap.add_argument("--dataset", action="append", help="repeatable; defaults to both CMIP6 datasets")
    args = ap.parse_args()

    datasets = args.dataset or DATASETS
    for ds in datasets:
        scan(ds, args.model, args.freq)

    print("Reminder: availability here is the CDS form constraint, not a guarantee")
    print("that every year/member combination resolves. Confirm with preflight.py")
    print("before triggering a full download.")


if __name__ == "__main__":
    sys.exit(main())
