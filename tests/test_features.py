from __future__ import annotations

import numpy as np
import pandas as pd

from coastcast.config import FeatureConfig
from coastcast.features import build_feature_table, model_feature_columns


def test_future_target_is_shifted_without_entering_features() -> None:
    timestamps = pd.date_range("2024-01-01", periods=80, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "observed_water_level_cm": np.arange(80, dtype=float),
            "tide_cm": np.arange(80, dtype=float) * 0.5,
            "pressure_msl": 1000.0,
            "wind_speed_10m": 5.0,
            "wind_direction_10m": 180.0,
            "wind_gusts_10m": 8.0,
            "precipitation": 0.0,
            "temperature_2m": 10.0,
        }
    )
    config = FeatureConfig((1, 3), (1, 2), (3,), 0.05)
    result = build_feature_table(frame, config)
    assert result.loc[0, "target_surge_h3"] == result.loc[3, "surge_residual_cm"]
    assert not any(column.startswith("target_") for column in model_feature_columns(result))
