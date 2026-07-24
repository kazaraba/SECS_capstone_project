# Week 1 — Detailed Task Plan: Setup + Historical Baseline Data

**Goal by end of week:** Two clean, validated historical dataframes (Seville, Larissa),
each plotted and sanity-checked, ready for indicator calculations in Week 2.

**Bounding boxes to use throughout:**
- Seville: North 37.6, West -6.2, South 37.2, East -5.7
- Larissa: North 39.8, West 21.9, South 39.5, East 22.6

---

## Day 1: Account setup

1. Go to https://cds.climate.copernicus.eu and create a free account
2. Log in, go to your profile page, copy your **Personal Access Token**
3. On your computer, create a file called `.cdsapirc` in your home directory containing:
   ```
   url: https://cds.climate.copernicus.eu/api
   key: YOUR_PERSONAL_ACCESS_TOKEN
   ```
4. Install required packages:
   ```bash
   pip install cdsapi xarray netCDF4 pandas matplotlib --break-system-packages
   ```
5. Test the connection with a tiny throwaway request (single day, single variable) to
   confirm your credentials work before attempting a real 30-year download:
   ```python
   import cdsapi
   c = cdsapi.Client()
   c.retrieve(
       'reanalysis-era5-single-levels',
       {
           'product_type': ['reanalysis'],
           'variable': ['2m_temperature'],
           'year': ['2020'], 'month': ['01'], 'day': ['01'],
           'time': ['12:00'],
           'area': [37.6, -6.2, 37.2, -5.7],
           'data_format': 'netcdf',
       },
       'test_download.nc'
   )
   print("Success — credentials working")
   ```
6. **Checkpoint:** if this fails, fix it today — don't move to Day 2 with broken credentials.

## Day 2: Explore the catalog before committing to raw downloads

7. On the CDS website, search for `sis-ecde-climate-indicators` ("Climate indicators for
   Europe"). Check: does it already include heatwave days and tropical nights for your
   two city locations, at a usable resolution, for both historical and SSP5-8.5 periods?
8. Also search for the CEMS fire danger historical/projection datasets mentioned in the
   project summary — note their exact dataset names and available variables.
9. Write down (in a text file or notes app) exactly which pre-built products you'll use
   and which raw ERA5 pulls are still needed — this decision now saves you from
   re-downloading things later.

## Day 3: Download historical ERA5 data — Seville

10. Submit the real historical request (this can take a while to process in the CDS
    queue, so start it and work on something else while it runs):
    ```python
    c.retrieve(
        'reanalysis-era5-single-levels',
        {
            'product_type': ['reanalysis'],
            'variable': [
                '2m_temperature', 'total_precipitation',
                '10m_u_component_of_wind', '10m_v_component_of_wind',
                '2m_dewpoint_temperature',  # used to derive relative humidity
            ],
            'year': [str(y) for y in range(1990, 2021)],
            'month': [f'{m:02d}' for m in range(1, 13)],
            'day': [f'{d:02d}' for d in range(1, 32)],
            'time': ['00:00', '06:00', '12:00', '18:00'],
            'area': [37.6, -6.2, 37.2, -5.7],
            'data_format': 'netcdf',
        },
        'seville_era5_historical.nc'
    )
    ```
11. **While it queues:** if it fails or the request is too large for one call, split it
    into decade chunks (1990–1999, 2000–2009, 2010–2020) and merge later — smaller
    requests process faster and are easier to retry if one fails.

## Day 4: Download historical ERA5 data — Larissa

12. Repeat the same request from Day 3, changing only the `area` box to the Larissa
    coordinates and the output filename to `larissa_era5_historical.nc`.
13. **Checkpoint:** by end of today you should have two historical NetCDF files
    downloading or downloaded. If both are still stuck in the CDS queue, that's normal —
    move on to Day 5 while you wait.

## Day 5: Pull any pre-built indicator data identified on Day 2

14. Submit requests for `sis-ecde-climate-indicators` and the fire danger datasets for
    both cities, historical period, based on what you confirmed is available on Day 2.
15. If a pre-built dataset doesn't cover something you need, note it as a "raw pull
    needed in Week 2/3" rather than blocking Week 1 on it.

## Day 6: Load and inspect the data

16. Once your downloads complete, load and inspect each file:
    ```python
    import xarray as xr

    ds_seville = xr.open_dataset('seville_era5_historical.nc')
    print(ds_seville)
    print("Variables:", list(ds_seville.data_vars))
    print("Time range:", ds_seville.time.values.min(), "-", ds_seville.time.values.max())
    ```
17. Do the same for the Larissa file.
18. **Checkpoint — this matters more than it looks:** confirm variable names, units, and
    the full expected date range (1990–2020) before doing anything else. A silent gap or
    wrong unit here will quietly break every downstream indicator in Weeks 2–3.

## Day 7: First plots + sanity check

19. Convert each city's temperature and precipitation to a pandas Series and plot the
    raw daily time series:
    ```python
    import matplotlib.pyplot as plt

    temp_series = ds_seville['t2m'].mean(dim=['latitude', 'longitude']).to_series()
    temp_series.plot(figsize=(12, 4), title='Seville — Raw 2m Temperature, 1990–2020')
    plt.savefig('seville_temp_check.png')
    plt.show()
    ```
20. Visually confirm: does the plot show a sensible seasonal cycle (hot summers, cooler
    winters), with no obviously broken/missing chunks of time? Repeat for precipitation
    and for Larissa.
21. Write a short note (a few sentences) on what you see — this becomes the start of
    your methods section later, and forces you to actually look at the data rather than
    just trusting the download worked.

---

## End-of-week checklist

- [ ] CDS account + API token working
- [ ] Confirmed which pre-built indicator datasets cover which needs
- [ ] Seville historical ERA5 data downloaded and loaded
- [ ] Larissa historical ERA5 data downloaded and loaded
- [ ] Fire danger + climate indicator pre-built data pulled (or confirmed unavailable —
      noted as raw pull needed)
- [ ] Raw time series plotted for both cities, visually sane (correct seasonal pattern,
      no major gaps)
- [ ] Short written note on initial data observations

If you're behind by Day 7, don't panic — the CDS download queue is the most
unpredictable part of this whole project and is largely outside your control. Just
prioritize getting Seville working end-to-end first, since Larissa can follow the exact
same process once it's proven.
