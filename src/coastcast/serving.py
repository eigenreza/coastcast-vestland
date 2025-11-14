"""Shared inference engine used by the API and dashboard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, os.cpu_count() or 1))

import joblib
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Forecast:
    issue_time: str
    valid_time: str
    horizon_hours: int
    tide_cm: float
    predicted_surge_cm: float
    predicted_total_cm: float
    lower_total_cm: float
    upper_total_cm: float
    threshold_cm: float
    threshold_exceeded: bool
    champion: str


class ForecastEngine:
    def __init__(self, bundle_path: Path, feature_path: Path) -> None:
        self.bundle: dict[str, Any] = joblib.load(bundle_path)
        self.features = pd.read_parquet(feature_path).sort_values("timestamp")
        self.features["timestamp"] = pd.to_datetime(self.features["timestamp"], utc=True)
        self.features = self.features.set_index("timestamp", drop=False)

    @property
    def horizons(self) -> list[int]:
        return sorted(int(value) for value in self.bundle["models"])

    def forecast(
        self,
        issue_time: str | pd.Timestamp,
        horizon_hours: int,
        threshold_cm: float = 100.0,
        wind_speed_multiplier: float = 1.0,
        pressure_delta_hpa: float = 0.0,
    ) -> Forecast:
        if horizon_hours not in self.horizons:
            raise ValueError(f"Unsupported horizon. Choose from {self.horizons}")
        if not 0.0 <= wind_speed_multiplier <= 3.0:
            raise ValueError("wind_speed_multiplier must be between 0 and 3")
        if not -50.0 <= pressure_delta_hpa <= 50.0:
            raise ValueError("pressure_delta_hpa must be between -50 and 50")

        timestamp = pd.Timestamp(issue_time)
        timestamp = (
            timestamp.tz_localize("UTC")
            if timestamp.tzinfo is None
            else timestamp.tz_convert("UTC")
        )
        if timestamp not in self.features.index:
            raise KeyError(f"No feature row is available at {timestamp.isoformat()}")
        row = self.features.loc[[timestamp]].copy()
        tide_column = f"target_tide_h{horizon_hours}"
        tide = float(row.iloc[0][tide_column])
        if np.isnan(tide):
            raise ValueError("Astronomical tide is unavailable at the requested valid time")

        row["pressure_msl"] = row["pressure_msl"] + pressure_delta_hpa
        row["wind_speed_10m"] = row["wind_speed_10m"] * wind_speed_multiplier
        row["wind_gusts_10m"] = row["wind_gusts_10m"] * wind_speed_multiplier
        direction = np.deg2rad(row["wind_direction_10m"])
        row["wind_eastward_ms"] = -row["wind_speed_10m"] * np.sin(direction)
        row["wind_northward_ms"] = -row["wind_speed_10m"] * np.cos(direction)

        model_spec = self.bundle["models"][horizon_hours]
        if model_spec["champion"] == "persistence":
            surge = float(row.iloc[0]["surge_residual_cm"])
        else:
            surge = float(model_spec["estimator"].predict(row[self.bundle["features"]])[0])
        scale_feature = str(model_spec.get("scale_feature", "surge_std_24h"))
        minimum_scale = float(model_spec.get("minimum_scale_cm", 1.0))
        local_scale = max(float(row.iloc[0][scale_feature]), minimum_scale)
        radius = float(model_spec["conformal_multiplier"]) * local_scale
        total = tide + surge
        valid_time = timestamp + pd.Timedelta(hours=horizon_hours)
        return Forecast(
            issue_time=timestamp.isoformat(),
            valid_time=valid_time.isoformat(),
            horizon_hours=horizon_hours,
            tide_cm=tide,
            predicted_surge_cm=surge,
            predicted_total_cm=total,
            lower_total_cm=total - radius,
            upper_total_cm=total + radius,
            threshold_cm=threshold_cm,
            threshold_exceeded=total + radius >= threshold_cm,
            champion=model_spec["champion"],
        )

    def available_times(self) -> pd.DatetimeIndex:
        last_horizon = max(self.horizons)
        scale_features = {
            str(model_spec.get("scale_feature", "surge_std_24h"))
            for model_spec in self.bundle["models"].values()
        }
        complete = self.features[f"target_tide_h{last_horizon}"].notna()
        for scale_feature in scale_features:
            complete &= self.features[scale_feature].notna()
        return pd.DatetimeIndex(self.features.loc[complete, "timestamp"])
