with source as (
    select * from read_parquet('data/bronze/water_level.parquet')
)

select
    cast(timestamp as timestamptz) as observed_at,
    cast(observed_water_level_cm as double) as observed_water_level_cm,
    cast(tide_cm as double) as tide_cm
from source
where timestamp >= cast('{{ var("study_start") }}' as timestamptz)
  and timestamp < cast('{{ var("study_end_exclusive") }}' as timestamptz)
