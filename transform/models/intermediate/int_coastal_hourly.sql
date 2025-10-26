select
    water.observed_at,
    water.observed_water_level_cm,
    water.tide_cm,
    water.observed_water_level_cm - water.tide_cm as surge_residual_cm,
    weather.pressure_msl_hpa,
    weather.wind_speed_10m_ms,
    weather.wind_direction_10m_degrees,
    weather.wind_gusts_10m_ms,
    weather.precipitation_mm,
    weather.temperature_2m_c
from {{ ref('stg_water_level') }} as water
inner join {{ ref('stg_weather') }} as weather using (observed_at)
