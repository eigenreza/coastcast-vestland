with source as (
    select * from read_parquet('data/bronze/weather.parquet')
)

select
    cast(timestamp as timestamptz) as observed_at,
    cast(pressure_msl as double) as pressure_msl_hpa,
    cast(wind_speed_10m as double) as wind_speed_10m_ms,
    cast(wind_direction_10m as double) as wind_direction_10m_degrees,
    cast(wind_gusts_10m as double) as wind_gusts_10m_ms,
    cast(precipitation as double) as precipitation_mm,
    cast(temperature_2m as double) as temperature_2m_c
from source
where timestamp >= cast('{{ var("study_start") }}' as timestamptz)
  and timestamp < cast('{{ var("study_end_exclusive") }}' as timestamptz)
