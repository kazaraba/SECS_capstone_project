# ERA5 Reanalysis Data — Capstone Reference

Column dictionary, grid structure, unit conversions, and aggregation workflow for the Seville climate dataset.

---

## 1. Column Dictionary

| Column | Meaning | Units | Notes |
|---|---|---|---|
| `valid_time` | Timestamp of the observation | datetime | Requested 00:00, 06:00, 12:00, 18:00 — presence of all four confirms the request worked |
| `latitude` | Grid point latitude | degrees | 2 latitude points inside the bounding box: 37.25, 37.50 |
| `longitude` | Grid point longitude | degrees | 2 longitude points: −6.00, −5.75 |
| `tp` | Total precipitation | meters | Row 4 shows 0.000003 = 0.003 mm, a trace amount, not zero. Multiply by 1000 to get mm |
| `t2m` | 2 m air temperature | Kelvin | e.g. 285.49 K |
| `u10` | 10 m wind, east-west component | m/s | Positive = blowing eastward |
| `v10` | 10 m wind, north-south component | m/s | Positive = blowing northward. Combine with `u10` via √(u10² + v10²) for wind speed |
| `d2m` | 2 m dewpoint temperature | Kelvin | Used together with `t2m` to derive relative humidity |
| `t2m_celsius` | Temperature converted to °C | °C | K→°C conversion already applied in the notebook |
| `d2m_celsius` | Dewpoint converted to °C | °C | Already converted |

---

## 2. Notes on the Data Structure

**The bounding box returns a 2×2 grid, not a single point.** Four grid points (two latitudes × two longitudes) means four rows per timestamp before the data moves to the next 6-hour step — rows 0–3 are all `1990-01-01 00:00:00`, and row 4 jumps to `06:00:00`. This matches the plan: average across these four grid points to get one representative value per city.

**Precipitation needs the ×1000 conversion to mm before use.** This is the unit trap flagged earlier — better caught now than after computing SPI on values expressed in meters.

**Relative humidity is missing as a direct column.** The ingredients are present (`t2m_celsius` and `d2m_celsius`) but RH has to be derived from them.

### Deriving relative humidity (Magnus formula)

```python
import numpy as np

def relative_humidity(t2m_c, d2m_c):
    a, b = 17.625, 243.04
    e_dew  = np.exp((a * d2m_c) / (b + d2m_c))
    e_temp = np.exp((a * t2m_c) / (b + t2m_c))
    return 100 * (e_dew / e_temp)

df['rh_percent'] = relative_humidity(df['t2m_celsius'], df['d2m_celsius'])
```

---

## 3. Resampling to Daily

The data currently holds four readings per day for each grid point (00:00, 06:00, 12:00, 18:00). *Resampling to daily* means collapsing those four readings into a single value per day, because the later calculations — heatwave detection, SPI, monthly aggregation — operate on daily or monthly data, not 6-hourly data.

The tricky part: different variables must be collapsed differently.

| Variable | How to collapse | Why |
|---|---|---|
| `t2m_celsius` | `max` and `min` across the 4 daily readings | Heatwave detection needs the daily maximum; tropical nights need the daily minimum (must stay above 20 °C overnight) |
| `tp` (precipitation) | `sum` the 4 readings | Precipitation is cumulative, not a snapshot — summing gives total daily rainfall |
| Wind / dewpoint | average across the day | No strong reason to care about daily max/min the way there is with temperature |

### Code

Assumes the 4 grid points have already been averaged into one value per timestamp (the Seville location average).

```python
# df has one row per timestamp, already averaged across grid points,
# with valid_time as a proper datetime column
df['valid_time'] = pd.to_datetime(df['valid_time'])
df = df.set_index('valid_time')

daily = pd.DataFrame({
    'tmax_c':    df['t2m_celsius'].resample('D').max(),
    'tmin_c':    df['t2m_celsius'].resample('D').min(),
    'precip_mm': (df['tp'] * 1000).resample('D').sum(),
    'wind_avg':  df[['u10', 'v10']]
                   .apply(lambda x: (x['u10']**2 + x['v10']**2)**0.5, axis=1)
                   .resample('D').mean(),
})

print(daily.head())
```

**What `.resample()` does:** `.resample('D')` is a pandas function that groups timestamp-indexed data by calendar day; `.max()`, `.min()` or `.sum()` then tells it how to combine the four readings within that day into one number.

> Later, for SPI, resample a second time — daily to monthly — using `.resample('MS').sum()` on precipitation, since SPI works on monthly totals.

---

## 4. Next Step

Write the groupby step that averages the four grid points into one Seville-representative value per timestamp. That has to happen **before** the daily resampling shown above.
