from __future__ import annotations

from fastapi.testclient import TestClient

from coastcast.api import main
from coastcast.serving import Forecast


class FakeEngine:
    def forecast(self, **_: object) -> Forecast:
        return Forecast(
            issue_time="2025-12-01T12:00:00+00:00",
            valid_time="2025-12-01T18:00:00+00:00",
            horizon_hours=6,
            tide_cm=50.0,
            predicted_surge_cm=20.0,
            predicted_total_cm=70.0,
            lower_total_cm=60.0,
            upper_total_cm=80.0,
            threshold_cm=100.0,
            threshold_exceeded=False,
            champion="gradient_boosting",
        )


def test_forecast_contract(monkeypatch) -> None:
    monkeypatch.setattr(main, "get_engine", lambda: FakeEngine())
    client = TestClient(main.app)
    response = client.post(
        "/v1/forecast",
        json={
            "issue_time": "2025-12-01T12:00:00Z",
            "horizon_hours": 6,
            "threshold_cm": 100,
            "wind_speed_multiplier": 1.0,
            "pressure_delta_hpa": 0.0,
        },
    )
    assert response.status_code == 200
    assert response.json()["predicted_total_cm"] == 70.0
    assert response.json()["threshold_exceeded"] is False


def test_forecast_rejects_unsupported_horizon() -> None:
    client = TestClient(main.app)
    response = client.post(
        "/v1/forecast",
        json={"issue_time": "2025-12-01T12:00:00Z", "horizon_hours": 5},
    )
    assert response.status_code == 422
