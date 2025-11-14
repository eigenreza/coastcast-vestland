"""Versioned API request and response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ForecastRequest(BaseModel):
    issue_time: datetime
    horizon_hours: int = Field(default=6)
    threshold_cm: float = Field(default=100.0, ge=-300.0, le=500.0)
    wind_speed_multiplier: float = Field(default=1.0, ge=0.0, le=3.0)
    pressure_delta_hpa: float = Field(default=0.0, ge=-50.0, le=50.0)

    @field_validator("horizon_hours")
    @classmethod
    def supported_horizon(cls, value: int) -> int:
        if value not in {1, 3, 6, 12}:
            raise ValueError("horizon_hours must be one of 1, 3, 6, or 12")
        return value


class ForecastResponse(BaseModel):
    issue_time: datetime
    valid_time: datetime
    horizon_hours: int
    tide_cm: float
    predicted_surge_cm: float
    predicted_total_cm: float
    lower_total_cm: float
    upper_total_cm: float
    threshold_cm: float
    threshold_exceeded: bool
    champion: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    data_loaded: bool
