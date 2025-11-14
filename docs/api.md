# Prediction API

Base URL for local development: `http://127.0.0.1:8000`

Interactive OpenAPI documentation: `/docs`

## Health

`GET /v1/health`

```json
{
  "status": "ok",
  "model_loaded": true,
  "data_loaded": true
}
```

## Model metadata

`GET /v1/model`

Returns station, reference level, supported years, exact data scope, temporal-evaluation boundaries, horizons, selected champions, and interval-calibration methods.

## Forecast

`POST /v1/forecast`

Request:

```json
{
  "issue_time": "2025-12-01T12:00:00Z",
  "horizon_hours": 6,
  "threshold_cm": 100,
  "wind_speed_multiplier": 1.15,
  "pressure_delta_hpa": -5
}
```

Response:

```json
{
  "issue_time": "2025-12-01T12:00:00Z",
  "valid_time": "2025-12-01T18:00:00Z",
  "horizon_hours": 6,
  "tide_cm": 18.7,
  "predicted_surge_cm": 12.4,
  "predicted_total_cm": 31.1,
  "lower_total_cm": 20.2,
  "upper_total_cm": 42.0,
  "threshold_cm": 100,
  "threshold_exceeded": false,
  "champion": "gradient_boosting"
}
```

The numerical values above illustrate the schema. They are not a recorded forecast.

## Scenario controls

`wind_speed_multiplier` scales current wind speed and gust while preserving direction. `pressure_delta_hpa` shifts current mean sea-level pressure. These controls create analytical what-if scenarios. They do not replace a meteorological forecast trajectory.

## Error responses

- `404`: no analytical feature row exists for the requested issue time
- `422`: unsupported horizon, invalid control range, missing future tide, or unavailable runtime artifact
- `503`: model metadata cannot be loaded

## Versioning

The current contract is under `/v1`. Breaking schema or semantic changes require a new path version. Adding optional response metadata does not require a new version.
