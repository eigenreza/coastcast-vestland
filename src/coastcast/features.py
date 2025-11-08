"""Leakage-safe feature construction for multi-horizon forecasts."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from coastcast.config import FeatureConfig

WEATHER_COLUMNS = [
    "pressure_msl",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "precipitation",
    "temperature_2m",
]


def build_feature_table(hourly: pd.DataFrame, config: FeatureConfig) -> pd.DataFrame:
    """Build features available at issue time and future targets for evaluation."""
    frame = hourly.sort_values("timestamp").copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["surge_residual_cm"] = frame["observed_water_level_cm"] - frame["tide_cm"]

    direction = np.deg2rad(frame["wind_direction_10m"])
    frame["wind_eastward_ms"] = -frame["wind_speed_10m"] * np.sin(direction)
    frame["wind_northward_ms"] = -frame["wind_speed_10m"] * np.cos(direction)
    frame["hour_sin"] = np.sin(2 * math.pi * frame["timestamp"].dt.hour / 24)
    frame["hour_cos"] = np.cos(2 * math.pi * frame["timestamp"].dt.hour / 24)
    day = frame["timestamp"].dt.dayofyear
    frame["year_sin"] = np.sin(2 * math.pi * day / 365.25)
    frame["year_cos"] = np.cos(2 * math.pi * day / 365.25)

    lag_sources = ["surge_residual_cm", "pressure_msl", "wind_eastward_ms", "wind_northward_ms"]
    for column in lag_sources:
        for lag in config.lag_hours:
            frame[f"{column}_lag_{lag}h"] = frame[column].shift(lag)

    for window in config.rolling_windows:
        history = (
            frame["surge_residual_cm"].shift(1).rolling(window, min_periods=max(2, window // 2))
        )
        frame[f"surge_mean_{window}h"] = history.mean()
        frame[f"surge_std_{window}h"] = history.std()
        frame[f"pressure_change_{window}h"] = frame["pressure_msl"] - frame["pressure_msl"].shift(
            window
        )

    for horizon in config.horizons:
        frame[f"target_surge_h{horizon}"] = frame["surge_residual_cm"].shift(-horizon)
        frame[f"target_tide_h{horizon}"] = frame["tide_cm"].shift(-horizon)
        frame[f"target_total_h{horizon}"] = frame["observed_water_level_cm"].shift(-horizon)
    return frame


def model_feature_columns(frame: pd.DataFrame) -> list[str]:
    blocked_prefixes = ("target_",)
    blocked = {
        "timestamp",
        "observed_water_level_cm",
        "source_latitude",
        "source_longitude",
        "source_elevation_m",
    }
    return [
        column
        for column in frame.columns
        if column not in blocked
        and not column.startswith(blocked_prefixes)
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
