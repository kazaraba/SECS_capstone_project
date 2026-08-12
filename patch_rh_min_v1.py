#!/usr/bin/env python
"""
patch_rh_min.py
---------------
Adds a noon-RH proxy (`rh_min_percent`) to the SECS CMIP6 pipeline.

Why: FWI needs local-noon relative humidity. `cmip6_grid_processing.py` derives
RH once, from daily-mean `tas`, producing a daily-MEAN RH. In ERA5 at Seville
the ratio rh_min/rh_mean runs 0.652 in July and 0.855 in December, so daily-mean
RH overstates humidity by ~50% in peak fire season and a scalar or monthly-ratio
rescale is not adequate. This patch derives RH a second time at `tasmax` --
which yields the daily MINIMUM RH, the noon proxy -- and registers it for
per-month EDCDFm bias correction against ERA5's `rh_min`.

Two edits:
  1. cmip6_grid_processing.py       -- derive and emit `rh_min_percent`
  2. bias_correct_cmip6_projection.py -- add it to VARIABLE_MAP

Safe to run twice: already-patched files are detected and skipped.
Backups are written as <file>.bak-rhmin unless one already exists.

Usage:
    python patch_rh_min.py --dry-run     # show the diff, change nothing
    python patch_rh_min.py               # apply
    python patch_rh_min.py --revert      # restore from backups
"""

import argparse
import ast
import difflib
import os
import re
import shutil
import sys

GRID = "cmip6_grid_processing.py"
BIAS = "bias_correct_cmip6_projection.py"
SUFFIX = ".bak-rhmin"

DERIVE_BLOCK = '''    # Noon-RH proxy for FWI: evaluating humidity at the daily MAX temperature
    # yields the daily MINIMUM RH, which approximates local-noon conditions.
    # ERA5 rh_min/rh_mean at Seville runs 0.652 in July vs 0.855 in December,
    # so a scalar or monthly-ratio rescale of mean RH is not adequate -- hence a
    # separate derived variable, bias-corrected in its own right. Same
    # recompute-from-averaged-inputs discipline as relative_humidity_pct above.
    grid_mean["relative_humidity_min_pct"] = derive_rh(
        grid_mean["tasmax"], grid_mean["huss"], grid_mean["psl"])
'''

OUTPUT_LINE = '        "rh_min_percent": grid_mean["relative_humidity_min_pct"],\n'

MAP_LINE = '    "rh_min_percent":  ("rh_min",           "additive"),\n'


# --- helpers ----------------------------------------------------------
def read(path):
    if not os.path.exists(path):
        raise SystemExit(f"[error] {path} not found. Run this from the project root.")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def show_diff(path, before, after):
    d = list(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}", n=3))
    if not d:
        print(f"  (no change to {path})")
        return
    for line in d:
        print("  " + line.rstrip("\n"))


def write(path, text, dry_run):
    if dry_run:
        return
    bak = path + SUFFIX
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print(f"  backup -> {bak}")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    print(f"  written {path}")


def check_syntax(path, text):
    try:
        ast.parse(text)
        return True
    except SyntaxError as exc:
        print(f"  [FAIL] {path} would not parse: line {exc.lineno}: {exc.msg}")
        return False


# --- edit 1 -----------------------------------------------------------
def patch_grid(text):
    """Insert the derive call and the output-frame line."""
    if "relative_humidity_min_pct" in text:
        return text, "already patched"

    # Anchor A: the existing derive_rh call for mean RH. Whitespace-tolerant.
    anchor_a = re.search(
        r'[ \t]*grid_mean\["relative_humidity_pct"\][ \t]*=[ \t]*derive_rh\('
        r'\s*grid_mean\["tas"\][ \t]*,[ \t]*grid_mean\["huss"\][ \t]*,'
        r'[ \t]*grid_mean\["psl"\]\)[ \t]*\n',
        text)
    if not anchor_a:
        return text, "could not locate the relative_humidity_pct derive_rh call"

    text = text[:anchor_a.end()] + DERIVE_BLOCK + text[anchor_a.end():]

    # Anchor B: the rh_mean_percent entry in the output DataFrame.
    anchor_b = re.search(
        r'[ \t]*"rh_mean_percent":[ \t]*grid_mean\["relative_humidity_pct"\][ \t]*,[ \t]*\n',
        text)
    if not anchor_b:
        return text, "could not locate the rh_mean_percent output line"

    text = text[:anchor_b.end()] + OUTPUT_LINE + text[anchor_b.end():]
    return text, None


# --- edit 2 -----------------------------------------------------------
def patch_bias(text):
    """Add rh_min_percent to VARIABLE_MAP."""
    if '"rh_min_percent"' in text:
        return text, "already patched"

    anchor = re.search(
        r'[ \t]*"rh_mean_percent":[ \t]*\([ \t]*"rh_mean_percent"[ \t]*,'
        r'[ \t]*"additive"[ \t]*\)[ \t]*,[ \t]*\n',
        text)
    if not anchor:
        return text, "could not locate the rh_mean_percent VARIABLE_MAP entry"

    return text[:anchor.end()] + MAP_LINE + text[anchor.end():], None


# --- revert -----------------------------------------------------------
def revert():
    n = 0
    for path in (GRID, BIAS):
        bak = path + SUFFIX
        if os.path.exists(bak):
            shutil.copy2(bak, path)
            print(f"restored {path} from {bak}")
            n += 1
        else:
            print(f"no backup for {path}")
    return 0 if n else 1


# --- main -------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--revert", action="store_true")
    args = ap.parse_args()

    if args.revert:
        return revert()

    jobs = [(GRID, patch_grid), (BIAS, patch_bias)]
    results = []

    for path, fn in jobs:
        print(f"\n=== {path} ===")
        before = read(path)
        after, problem = fn(before)

        if problem == "already patched":
            print("  already patched -- skipping")
            results.append((path, "skipped"))
            continue
        if problem:
            print(f"  [FAIL] {problem}")
            print("  The file may differ from what this patch expects.")
            print("  Nothing was written. Apply the edit by hand instead.")
            results.append((path, "failed"))
            continue

        show_diff(path, before, after)
        if not check_syntax(path, after):
            results.append((path, "failed"))
            continue

        write(path, after, args.dry_run)
        results.append((path, "dry-run" if args.dry_run else "patched"))

    print("\n" + "=" * 60)
    for path, status in results:
        print(f"  {status:8s} {path}")

    failed = [p for p, s in results if s == "failed"]
    if failed:
        print("\nSome edits failed. Nothing partial was written to those files.")
        return 1

    if args.dry_run:
        print("\nDry run only. Re-run without --dry-run to apply.")
        return 0

    print("""
Next:
  1. Re-run the bias correction:
       python bias_correct_cmip6_projection.py

  2. Confirm rh_min_percent landed and looks right:
       python -c "
import pandas as pd
d = pd.read_csv('data/seville_cmip6_ssp585_2026_2061_biascorrected.csv',
                index_col=0, parse_dates=True)
print(list(d.columns))
m = d.groupby(d.index.month)[['rh_mean_percent','rh_min_percent']].mean()
m['ratio'] = (m['rh_min_percent']/m['rh_mean_percent']).round(3)
print(m.round(1))
"
     July ratio should sit near 0.65, December near 0.85. If the two columns
     come out nearly equal, the derivation did not take.

  To undo:  python patch_rh_min.py --revert
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
