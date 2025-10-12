from __future__ import annotations

import json
from datetime import UTC, datetime

from coastcast.data.clients import chunk_period, parse_kartverket, parse_open_meteo


def test_kartverket_parser_pivots_supported_series() -> None:
    payload = b"""<tide><stationdata><location name="Bergen" code="BGO">
      <data type="observation" unit="cm" reflevelcode="MSL">
        <waterlevel value="12.3" time="2025-01-01T00:00:00+00:00" flag="obs"/>
      </data>
      <data type="prediction" unit="cm" reflevelcode="MSL">
        <waterlevel value="8.1" time="2025-01-01T00:00:00+00:00" flag="pre"/>
      </data>
    </location></stationdata></tide>"""
    frame = parse_kartverket(payload)
    assert len(frame) == 2
    assert set(frame["series"]) == {"observation", "prediction"}
    assert frame["timestamp"].dt.tz is not None


def test_open_meteo_parser_preserves_hourly_values() -> None:
    payload = json.dumps(
        {
            "latitude": 60.4,
            "longitude": 5.3,
            "elevation": 12.0,
            "hourly": {
                "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
                "pressure_msl": [1000.0, 999.0],
                "wind_speed_10m": [4.0, 5.0],
            },
        }
    ).encode()
    frame = parse_open_meteo(payload)
    assert list(frame["pressure_msl"]) == [1000.0, 999.0]
    assert str(frame["timestamp"].dt.tz) == "UTC"


def test_chunk_period_has_no_hourly_overlap() -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 4, 23, tzinfo=UTC)
    chunks = list(chunk_period(start, end, chunk_days=2))
    assert len(chunks) == 2
    assert chunks[0][1].hour == 23
    assert (chunks[1][0] - chunks[0][1]).total_seconds() == 3600
