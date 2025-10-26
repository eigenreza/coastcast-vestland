select observed_at
from {{ ref('int_coastal_hourly') }}
where observed_water_level_cm not between -500 and 500
   or tide_cm not between -500 and 500
   or pressure_msl_hpa not between 850 and 1100
   or wind_speed_10m_ms not between 0 and 80
   or wind_gusts_10m_ms not between 0 and 100
