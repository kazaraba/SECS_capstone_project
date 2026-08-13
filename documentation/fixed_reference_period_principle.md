# Why the Reference Period Stays Fixed at 1990–2020

## The problem: a moving target that absorbs its own signal

A percentile threshold — "hot" means hotter than 90% of days in some reference set — is only
meaningful relative to whatever set of years defines "normal." If that reference set keeps
expanding to include every new year as it arrives, the threshold itself creeps upward each time a
warmer year is added, because the recent warm years become part of what counts as normal. A day
that would have counted as extreme in 1995 might no longer count as extreme in 2025 — not because
the atmosphere failed to change, but because the definition of normal changed along with it.

This is sometimes called **shifting baseline bias**. The measuring stick stretches in the same
direction as the thing being measured, which mutes the very trend the analysis is trying to
detect. In the extreme case of a perfectly steady warming trend measured against an
ever-expanding baseline, every year would show roughly the same number of "extreme" days relative
to its own recent past — even though the underlying climate had shifted substantially over the
full period. The trend would appear to vanish, not because it isn't real, but because the
yardstick moved with it.

## The fix: fit once, on a fixed period; apply to everything

Fixing the reference period at 1990–2020 breaks this feedback loop. "Hot" always means "hotter
than the 1990–2020 normal" — full stop, never recalculated. Asking "were 2023's heatwave days
unusual" then means comparing 2023 against a fixed, unchanging yardstick from three decades
earlier, not against a yardstick that has already partially adjusted to include 2021–2023
themselves.

This mirrors the World Meteorological Organization's own convention for official 30-year
"climate normals," which are periodically redefined on a roughly decadal cycle rather than
continuously recalculated with each new year of data.

The practical technique is a clean split between two roles:

- **Reference period (1990–2020):** used only to *estimate* what counts as normal — fit the
  percentile thresholds, or fit the distribution parameters, using only these years.
- **Evaluation period (1990–2025):** every year, including the newly extended years, gets
  *scored* against that fixed reference — never used to redefine it.

New data is measured against history. History is never redefined by the new data.

## Applying this to SPI specifically

The Standardised Precipitation Index (SPI) is a distribution-fit index, so the same principle
applies one layer more directly. SPI-3 works by fitting a gamma distribution to 3-month rolling
precipitation totals, then converting each observed value's position in that distribution into a
standard-normal z-score.

If that gamma distribution is fit using the full 1990–2025 record — including an anomalous event
like the 2023 drought-to-Storm-Daniel sequence — the distribution reshapes itself partly around
that very event. The resulting SPI value for September 2023 would then understate how unusual the
month actually was, precisely because the event became part of its own baseline.

Fitting the distribution only on 1990–2020, then applying that fixed distribution to score every
month through 2025, avoids this: September 2023 gets measured against "what counted as normal
September rainfall, historically," so if it was genuinely anomalous, the index will show that
clearly — which is exactly the validation check the project's plan calls for (a clear, sharp
negative SPI dip preceding the September 2023 event).

## Summary

| | Reference period (1990–2020) | Evaluation period (1990–2025) |
|---|---|---|
| Role | Defines what "normal" means | Gets scored against that definition |
| Recalculated when new data arrives? | No — fixed | N/A — new years are scored, not folded in |
| Used for | Fitting percentile thresholds, gamma distribution parameters | Applying those fixed thresholds/distributions to compute indicators for every year |

Keeping this split intact is what allows genuine extremes in the extended 2021–2025 years to
actually register as extreme, rather than being partially normalized away by their own inclusion
in the baseline.
