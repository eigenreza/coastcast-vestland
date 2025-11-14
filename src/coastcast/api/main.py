"""HTTP prediction service with explicit health and model metadata endpoints."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException

from coastcast.api.schemas import ForecastRequest, ForecastResponse, HealthResponse
from coastcast.config import load_settings
from coastcast.serving import ForecastEngine

app = FastAPI(
    title="CoastCast Vestland API",
    version="1.0.0",
    description="Short-horizon Bergen coastal water-level forecasts",
)


@lru_cache(maxsize=1)
def get_engine() -> ForecastEngine:
    config_path = os.getenv("COASTCAST_CONFIG", "configs/base.yml")
    settings = load_settings(config_path)
    model_dir = Path(os.getenv("COASTCAST_MODEL_DIR", str(settings.paths.artifacts)))
    return ForecastEngine(
        bundle_path=model_dir / "model_bundle.joblib",
        feature_path=settings.paths.gold / "features.parquet",
    )


@app.get("/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        engine = get_engine()
        return HealthResponse(
            status="ok",
            model_loaded=bool(engine.bundle),
            data_loaded=not engine.features.empty,
        )
    except (FileNotFoundError, ValueError, OSError):
        return HealthResponse(status="degraded", model_loaded=False, data_loaded=False)


@app.get("/v1/model")
def model_metadata() -> dict[str, object]:
    try:
        engine = get_engine()
    except (FileNotFoundError, ValueError, OSError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "project": engine.bundle["project"],
        "station_code": engine.bundle["station_code"],
        "reference_level": engine.bundle["reference_level"],
        "allowed_years": engine.bundle["allowed_years"],
        "data_scope": {
            "start": engine.bundle["period_start"],
            "end": engine.bundle["period_end"],
        },
        "temporal_evaluation": {
            "validation_origins": engine.bundle["validation_origins"],
            "calibration_start": engine.bundle["calibration_start"],
            "test_start": engine.bundle["test_start"],
        },
        "horizons": engine.horizons,
        "champions": {
            horizon: engine.bundle["models"][horizon]["champion"] for horizon in engine.horizons
        },
        "calibration_methods": {
            horizon: engine.bundle["models"][horizon]["calibration_method"]
            for horizon in engine.horizons
        },
    }


@app.post("/v1/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest) -> ForecastResponse:
    try:
        result = get_engine().forecast(
            issue_time=request.issue_time,
            horizon_hours=request.horizon_hours,
            threshold_cm=request.threshold_cm,
            wind_speed_multiplier=request.wind_speed_multiplier,
            pressure_delta_hpa=request.pressure_delta_hpa,
        )
        return ForecastResponse.model_validate(result.__dict__)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, FileNotFoundError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
