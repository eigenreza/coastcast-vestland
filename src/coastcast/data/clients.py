"""Clients and parsers for the two CoastCast source systems."""

from __future__ import annotations

import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from datetime import datetime, timedelta

import pandas as pd

from coastcast.config import Settings
from coastcast.data.http import CachedHttpClient

LOGGER = logging.getLogger(__name__)
KARTVERKET_URL = "https://vannstand.kartverket.no/tideapi.php"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def chunk_period(
    start: datetime, end: datetime, chunk_days: int
) -> Iterator[tuple[datetime, datetime]]:
    """Yield inclusive, non-overlapping time windows."""
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk_days) - timedelta(hours=1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(hours=1)


class KartverketClient:
    """Retrieve measured and astronomical water level at a permanent station."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http = CachedHttpClient(
            cache_dir=settings.paths.raw / "kartverket",
            timeout_seconds=settings.ingestion.timeout_seconds,
            retries=settings.ingestion.retries,
            backoff_seconds=settings.ingestion.backoff_seconds,
            user_agent=settings.ingestion.user_agent,
        )

    def fetch(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        try:
            for start, end in chunk_period(
                self.settings.period.start,
                self.settings.period.end,
                self.settings.ingestion.water_chunk_days,
            ):
                params = {
                    "tide_request": "stationdata",
                    "stationcode": self.settings.location.station_code,
                    "fromtime": start.strftime("%Y-%m-%dT%H:%M"),
                    "totime": end.strftime("%Y-%m-%dT%H:%M"),
                    "datatype": "all",
                    "interval": 60,
                    "refcode": self.settings.location.reference_level.lower(),
                    "tzone": 0,
                    "dst": 0,
                    "lang": "en",
                }
                payload = self.http.get(KARTVERKET_URL, params=params, suffix="xml")
                frame = parse_kartverket(payload)
                if frame.empty:
                    LOGGER.warning("No water-level records returned for %s to %s", start, end)
                else:
                    frames.append(frame)
        finally:
            self.http.close()
        if not frames:
            raise ValueError("Kartverket returned no usable water-level records")
        result = pd.concat(frames, ignore_index=True)
        return result.drop_duplicates(["timestamp", "series"], keep="last").sort_values("timestamp")


def parse_kartverket(payload: bytes) -> pd.DataFrame:
    root = ET.fromstring(payload)
    error = root.find(".//error")
    if error is not None:
        raise ValueError(f"Kartverket API error: {error.text}")

    rows: list[dict[str, object]] = []
    for location in root.findall(".//stationdata/location"):
        station_code = location.attrib.get("code")
        for data in location.findall("data"):
            series = data.attrib.get("type", "unknown").lower()
            unit = data.attrib.get("unit", "cm")
            reference_level = data.attrib.get("reflevelcode")
            for point in data.findall("waterlevel"):
                rows.append(
                    {
                        "timestamp": point.attrib["time"],
                        "value_cm": float(point.attrib["value"]),
                        "series": series,
                        "flag": point.attrib.get("flag"),
                        "unit": unit,
                        "reference_level": reference_level,
                        "station_code": station_code,
                    }
                )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    return frame


class OpenMeteoClient:
    """Retrieve hourly meteorological reanalysis for the gauge coordinates."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.http = CachedHttpClient(
            cache_dir=settings.paths.raw / "open_meteo",
            timeout_seconds=settings.ingestion.timeout_seconds,
            retries=settings.ingestion.retries,
            backoff_seconds=settings.ingestion.backoff_seconds,
            user_agent=settings.ingestion.user_agent,
        )

    def fetch(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        try:
            for start, end in chunk_period(
                self.settings.period.start,
                self.settings.period.end,
                self.settings.ingestion.weather_chunk_days,
            ):
                params = {
                    "latitude": self.settings.location.latitude,
                    "longitude": self.settings.location.longitude,
                    "start_date": start.date().isoformat(),
                    "end_date": end.date().isoformat(),
                    "hourly": ",".join(self.settings.ingestion.weather_variables),
                    "models": self.settings.ingestion.weather_model,
                    "timezone": "UTC",
                    "wind_speed_unit": "ms",
                    "cell_selection": "nearest",
                }
                payload = self.http.get(OPEN_METEO_URL, params=params, suffix="json")
                frames.append(parse_open_meteo(payload))
        finally:
            self.http.close()
        result = pd.concat(frames, ignore_index=True)
        start_utc = pd.Timestamp(self.settings.period.start)
        end_utc = pd.Timestamp(self.settings.period.end)
        result = result[result["timestamp"].between(start_utc, end_utc)]
        return result.drop_duplicates("timestamp", keep="last").sort_values("timestamp")


def parse_open_meteo(payload: bytes) -> pd.DataFrame:
    response = json.loads(payload.decode("utf-8"))
    if "error" in response:
        raise ValueError(f"Open-Meteo API error: {response.get('reason', response['error'])}")
    hourly = response.get("hourly", {})
    if "time" not in hourly:
        raise ValueError("Open-Meteo response has no hourly time axis")
    frame = pd.DataFrame(hourly)
    frame["timestamp"] = pd.to_datetime(frame.pop("time"), utc=True)
    frame["source_latitude"] = float(response["latitude"])
    frame["source_longitude"] = float(response["longitude"])
    frame["source_elevation_m"] = float(response.get("elevation", 0.0))
    return frame
