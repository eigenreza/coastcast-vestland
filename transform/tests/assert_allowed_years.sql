select observed_at
from {{ ref('int_coastal_hourly') }}
where observed_at < cast('{{ var("study_start") }}' as timestamptz)
   or observed_at >= cast('{{ var("study_end_exclusive") }}' as timestamptz)
