# Data dictionary

## Bronze water-level table

File: `data/bronze/water_level.parquet`

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| timestamp | UTC timestamp | none | Hour of the observation and tide prediction |
| observed_water_level_cm | float | cm MSL | Measured total water level at station BGO |
| tide_cm | float | cm MSL | Astronomical tide prediction at station BGO |

## Bronze weather table

File: `data/bronze/weather.parquet`

| Column | Type | Unit | Description |
| --- | --- | --- | --- |
| timestamp | UTC timestamp | none | Hour represented by the analysis value |
| pressure_msl | float | hPa | Mean sea-level pressure |
| wind_speed_10m | float | m/s | Wind speed at 10 metres |
| wind_direction_10m | float | degrees | Direction from which wind arrives |
| wind_gusts_10m | float | m/s | Wind gust at 10 metres |
| precipitation | float | mm | Hourly precipitation amount |
| temperature_2m | float | degrees Celsius | Air temperature at 2 metres |
| source_latitude | float | degrees north | Latitude of the returned model grid cell |
| source_longitude | float | degrees east | Longitude of the returned model grid cell |
| source_elevation_m | float | metres | Elevation associated with the grid cell |

## Silver hourly table

File: `data/silver/coastal_hourly.parquet`

The silver table is a one-to-one inner join of both bronze tables on timestamp. The delivered build contains 78,888 hourly records spanning 2017-2025 with complete weather join coverage.

## Gold feature table

File: `data/gold/features.parquet`

In addition to silver columns, the feature table contains:

| Pattern or column | Meaning |
| --- | --- |
| surge_residual_cm | Observed water level minus tide |
| wind_eastward_ms | Eastward wind vector component |
| wind_northward_ms | Northward wind vector component |
| hour_sin, hour_cos | Cyclic hour-of-day encoding |
| year_sin, year_cos | Cyclic day-of-year encoding |
| `*_lag_Nh` | Value observed N hours before issue time |
| surge_mean_Nh | Historical rolling surge mean, excluding current hour |
| surge_std_Nh | Historical rolling surge standard deviation, excluding current hour |
| pressure_change_Nh | Current pressure minus pressure N hours earlier |
| target_surge_hN | Surge residual N hours after issue time |
| target_tide_hN | Astronomical tide N hours after issue time |
| target_total_hN | Observed total water level N hours after issue time |

All `target_*` columns are excluded from model inputs. They exist only for training and evaluation.

## Artifact tables

`artifacts/runtime/test_predictions.parquet` contains one row per test issue time and horizon:

| Column | Description |
| --- | --- |
| timestamp | Forecast issue time |
| horizon_hours | Lead time |
| actual_surge_cm | Realized surge residual |
| predicted_surge_cm | Champion prediction |
| lower_surge_cm | Lower calibrated bound |
| upper_surge_cm | Upper calibrated bound |
| tide_cm | Tide at valid time |
| actual_total_cm | Observed total at valid time |
| predicted_total_cm | Reconstructed total prediction |
| champion | Selected forecast method |
