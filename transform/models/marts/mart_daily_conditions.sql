select
    cast(observed_at as date) as date,
    avg(observed_water_level_cm) as mean_water_level_cm,
    max(observed_water_level_cm) as maximum_water_level_cm,
    avg(surge_residual_cm) as mean_surge_residual_cm,
    max(surge_residual_cm) as maximum_surge_residual_cm,
    avg(wind_speed_10m_ms) as mean_wind_speed_ms,
    max(wind_gusts_10m_ms) as maximum_wind_gust_ms,
    min(pressure_msl_hpa) as minimum_pressure_hpa,
    sum(precipitation_mm) as total_precipitation_mm
from {{ ref('int_coastal_hourly') }}
group by 1
