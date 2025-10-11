"""Typed project configuration and path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class PeriodConfig:
    start: datetime
    end: datetime


@dataclass(frozen=True)
class LocationConfig:
    name: str
    station_code: str
    latitude: float
    longitude: float
    reference_level: str


@dataclass(frozen=True)
class IngestionConfig:
    water_chunk_days: int
    weather_chunk_days: int
    timeout_seconds: int
    retries: int
    backoff_seconds: float
    user_agent: str
    weather_model: str
    weather_variables: tuple[str, ...]


@dataclass(frozen=True)
class FeatureConfig:
    horizons: tuple[int, ...]
    lag_hours: tuple[int, ...]
    rolling_windows: tuple[int, ...]
    maximum_missing_fraction: float


@dataclass(frozen=True)
class ModelConfig:
    random_state: int
    validation_start: datetime
    validation_window_months: int
    calibration_start: datetime
    test_start: datetime
    interval_alpha: float
    n_estimators: int
    learning_rate: float
    max_depth: int
    min_samples_leaf: int


@dataclass(frozen=True)
class PathConfig:
    raw: Path
    bronze: Path
    silver: Path
    gold: Path
    database: Path
    artifacts: Path
    reports: Path

    def create(self) -> None:
        for path in (self.raw, self.bronze, self.silver, self.gold, self.artifacts, self.reports):
            path.mkdir(parents=True, exist_ok=True)
        self.database.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Settings:
    name: str
    timezone: str
    allowed_years: tuple[int, ...]
    period: PeriodConfig
    location: LocationConfig
    ingestion: IngestionConfig
    features: FeatureConfig
    model: ModelConfig
    paths: PathConfig
    root: Path


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed


def load_settings(config_path: str | Path = "configs/base.yml") -> Settings:
    """Load configuration and resolve project-relative filesystem paths."""
    path = Path(config_path).resolve()
    with path.open(encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream)

    root = path.parent.parent
    period = PeriodConfig(
        start=_timestamp(raw["period"]["start"]),
        end=_timestamp(raw["period"]["end"]),
    )
    if period.start >= period.end:
        raise ValueError("The configured start must be earlier than the end")

    project = raw["project"]
    allowed_years = tuple(int(year) for year in project["allowed_years"])
    expected_years = tuple(range(period.start.year, period.end.year + 1))
    if allowed_years != expected_years:
        raise ValueError("allowed_years must exactly cover every year in the configured period")

    location = LocationConfig(**raw["location"])
    ingestion_raw = raw["ingestion"]
    ingestion = IngestionConfig(
        **{key: value for key, value in ingestion_raw.items() if key != "weather_variables"},
        weather_variables=tuple(ingestion_raw["weather_variables"]),
    )
    if min(ingestion.water_chunk_days, ingestion.weather_chunk_days) <= 0:
        raise ValueError("Ingestion chunk sizes must be positive")
    features_raw = raw["features"]
    features = FeatureConfig(
        horizons=tuple(features_raw["horizons"]),
        lag_hours=tuple(features_raw["lag_hours"]),
        rolling_windows=tuple(features_raw["rolling_windows"]),
        maximum_missing_fraction=float(features_raw["maximum_missing_fraction"]),
    )
    model_raw = raw["model"]
    model = ModelConfig(
        **{
            key: value
            for key, value in model_raw.items()
            if key not in {"validation_start", "calibration_start", "test_start"}
        },
        validation_start=_timestamp(model_raw["validation_start"]),
        calibration_start=_timestamp(model_raw["calibration_start"]),
        test_start=_timestamp(model_raw["test_start"]),
    )
    if model.validation_window_months <= 0:
        raise ValueError("validation_window_months must be positive")
    if not (
        period.start
        < model.validation_start
        < model.calibration_start
        < model.test_start
        <= period.end
    ):
        raise ValueError("Model split dates must be ordered within the configured period")

    path_config = PathConfig(**{key: root / value for key, value in raw["paths"].items()})
    return Settings(
        name=project["name"],
        timezone=project["timezone"],
        allowed_years=allowed_years,
        period=period,
        location=location,
        ingestion=ingestion,
        features=features,
        model=model,
        paths=path_config,
        root=root,
    )
