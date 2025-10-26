select
    observed_at,
    observed_water_level_cm,
    tide_cm,
    surge_residual_cm,
    pressure_msl_hpa,
    wind_speed_10m_ms,
    wind_direction_10m_degrees,
    wind_gusts_10m_ms,
    precipitation_mm,
    temperature_2m_c
from {{ ref('int_coastal_hourly') }}
