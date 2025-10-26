"""Materialize silver and gold analytical datasets in Parquet and DuckDB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb
import pandas as pd

from coastcast.config import Settings
from coastcast.data.contracts import (
    DataContractError,
    validate_missingness,
    validate_timestamp_contract,
)
from coastcast.features import WEATHER_COLUMNS, build_feature_table

LOGGER = logging.getLogger(__name__)


def build_lakehouse(settings: Settings) -> dict[str, Path]:
    water_path = settings.paths.bronze / "water_level.parquet"
    weather_path = settings.paths.bronze / "weather.parquet"
    if not water_path.exists() or not weather_path.exists():
        raise FileNotFoundError("Bronze inputs do not exist. Run ingestion first.")

    water = pd.read_parquet(water_path)
    weather = pd.read_parquet(weather_path)
    water["timestamp"] = pd.to_datetime(water["timestamp"], utc=True)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"], utc=True)
    hourly = water.merge(weather, on="timestamp", how="inner", validate="one_to_one")
    coverage = len(hourly) / max(1, len(water))
    if coverage < 0.90:
        raise DataContractError(f"Weather join coverage is too low: {coverage:.1%}")
    validate_timestamp_contract(hourly, settings.allowed_years, ["timestamp"])
    validate_missingness(
        hourly,
        ["observed_water_level_cm", "tide_cm", *WEATHER_COLUMNS],
        settings.features.maximum_missing_fraction,
    )

    hourly = hourly.sort_values("timestamp")
    silver_path = settings.paths.silver / "coastal_hourly.parquet"
    hourly.to_parquet(silver_path, index=False)
    features = build_feature_table(hourly, settings.features)
    gold_path = settings.paths.gold / "features.parquet"
    features.to_parquet(gold_path, index=False)

    connection = duckdb.connect(str(settings.paths.database))
    try:
        connection.execute(
            "CREATE OR REPLACE TABLE silver_coastal_hourly AS SELECT * FROM read_parquet(?)",
            [str(silver_path)],
        )
        connection.execute(
            "CREATE OR REPLACE TABLE gold_forecast_features AS SELECT * FROM read_parquet(?)",
            [str(gold_path)],
        )
        connection.execute(
            """
            CREATE OR REPLACE VIEW gold_daily_conditions AS
            SELECT
                CAST(timestamp AS DATE) AS date,
                avg(observed_water_level_cm) AS mean_water_level_cm,
                max(observed_water_level_cm) AS max_water_level_cm,
                avg(observed_water_level_cm - tide_cm) AS mean_surge_cm,
                max(observed_water_level_cm - tide_cm) AS max_surge_cm,
                avg(wind_speed_10m) AS mean_wind_ms,
                max(wind_gusts_10m) AS max_gust_ms,
                min(pressure_msl) AS minimum_pressure_hpa
            FROM silver_coastal_hourly
            GROUP BY 1
            ORDER BY 1
            """
        )
    finally:
        connection.close()

    manifest = {
        "allowed_years": list(settings.allowed_years),
        "period_start": settings.period.start.isoformat(),
        "period_end": settings.period.end.isoformat(),
        "silver_rows": len(hourly),
        "gold_rows": len(features),
        "weather_join_coverage": round(coverage, 6),
        "minimum_timestamp": hourly["timestamp"].min().isoformat(),
        "maximum_timestamp": hourly["timestamp"].max().isoformat(),
    }
    (settings.paths.gold / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    LOGGER.info("Lakehouse built with %d hourly rows", len(hourly))
    return {"silver": silver_path, "gold": gold_path, "database": settings.paths.database}
