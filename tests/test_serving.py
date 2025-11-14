from __future__ import annotations

import joblib
import pandas as pd

from coastcast.serving import ForecastEngine


def test_persistence_engine_reconstructs_total_level(tmp_path) -> None:
    bundle = {
        "project": "test",
        "station_code": "BGO",
        "reference_level": "MSL",
        "allowed_years": tuple(range(2017, 2026)),
        "features": ["surge_residual_cm"],
        "models": {
            1: {
                "champion": "persistence",
                "conformal_multiplier": 2.0,
                "scale_feature": "surge_std_24h",
                "minimum_scale_cm": 1.0,
                "estimator": None,
            }
        },
    }
    bundle_path = tmp_path / "bundle.joblib"
    joblib.dump(bundle, bundle_path)
    feature_path = tmp_path / "features.parquet"
    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2025-01-01T00:00:00Z"]),
            "surge_residual_cm": [5.0],
            "target_tide_h1": [20.0],
            "pressure_msl": [1000.0],
            "wind_speed_10m": [4.0],
            "wind_gusts_10m": [6.0],
            "wind_direction_10m": [180.0],
            "wind_eastward_ms": [0.0],
            "wind_northward_ms": [4.0],
            "surge_std_24h": [1.0],
        }
    ).to_parquet(feature_path, index=False)
    result = ForecastEngine(bundle_path, feature_path).forecast("2025-01-01T00:00:00Z", 1, 26.0)
    assert result.predicted_total_cm == 25.0
    assert result.lower_total_cm == 23.0
    assert result.threshold_exceeded is True
