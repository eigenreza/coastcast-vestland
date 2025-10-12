"""Ingestion entry point for raw and bronze layers."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from coastcast.config import Settings
from coastcast.data.clients import KartverketClient, OpenMeteoClient
from coastcast.data.contracts import RangeRule, validate_ranges, validate_timestamp_contract

LOGGER = logging.getLogger(__name__)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest(settings: Settings) -> dict[str, Path]:
    settings.paths.create()
    LOGGER.info("Fetching Kartverket water-level records")
    water_long = KartverketClient(settings).fetch()
    validate_timestamp_contract(water_long, settings.allowed_years, ["timestamp", "series"])
    validate_ranges(water_long, [RangeRule("value_cm", -500.0, 500.0)])

    water = (
        water_long.pivot_table(
            index="timestamp", columns="series", values="value_cm", aggfunc="last"
        )
        .reset_index()
        .rename(columns={"observation": "observed_water_level_cm", "prediction": "tide_cm"})
    )
    required_water = {"observed_water_level_cm", "tide_cm"}
    missing_water = required_water - set(water.columns)
    if missing_water:
        raise ValueError(f"Kartverket response is missing series: {sorted(missing_water)}")

    LOGGER.info("Fetching Open-Meteo historical weather records")
    weather = OpenMeteoClient(settings).fetch()
    validate_timestamp_contract(weather, settings.allowed_years, ["timestamp"])
    validate_ranges(
        weather,
        [
            RangeRule("pressure_msl", 850.0, 1100.0),
            RangeRule("wind_speed_10m", 0.0, 80.0),
            RangeRule("wind_gusts_10m", 0.0, 100.0),
            RangeRule("wind_direction_10m", 0.0, 360.0),
            RangeRule("temperature_2m", -50.0, 50.0),
            RangeRule("precipitation", 0.0, 100.0),
        ],
    )

    water_path = settings.paths.bronze / "water_level.parquet"
    weather_path = settings.paths.bronze / "weather.parquet"
    water.to_parquet(water_path, index=False)
    weather.to_parquet(weather_path, index=False)
    manifest = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "period_start": settings.period.start.isoformat(),
        "period_end": settings.period.end.isoformat(),
        "allowed_years": list(settings.allowed_years),
        "water_level_rows": len(water),
        "weather_rows": len(weather),
        "water_level_first_timestamp": water["timestamp"].min().isoformat(),
        "water_level_last_timestamp": water["timestamp"].max().isoformat(),
        "weather_first_timestamp": weather["timestamp"].min().isoformat(),
        "weather_last_timestamp": weather["timestamp"].max().isoformat(),
        "station_code": settings.location.station_code,
        "weather_model": settings.ingestion.weather_model,
        "files": {
            str(water_path.relative_to(settings.root)): _file_sha256(water_path),
            str(weather_path.relative_to(settings.root)): _file_sha256(weather_path),
        },
    }
    (settings.paths.bronze / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return {"water_level": water_path, "weather": weather_path}
