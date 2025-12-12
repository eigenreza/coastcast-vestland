# Operational runbook

## Normal pipeline run

```powershell
.\.venv\Scripts\Activate.ps1
python -m coastcast.cli pipeline --config configs/base.yml
```

Expected outputs:

- bronze, silver, and gold Parquet tables
- `data/lakehouse.duckdb`
- `artifacts/runtime/model_bundle.joblib`
- metrics, signature, and test predictions
- generated model evaluation report

## Fast demonstration run

```powershell
python -m coastcast.cli pipeline --config configs/demo.yml
```

This profile has a shorter source period and is suitable for verifying infrastructure. The full profile should be used for the delivered model artifacts.

## Start services

```powershell
uvicorn coastcast.api.main:app --host 127.0.0.1 --port 8000
```

```powershell
streamlit run src/coastcast/dashboard/app.py
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/v1/health
```

## Common failures

### Provider request fails

The HTTP client retries transient errors with exponential backoff. Check provider status and the request metadata in `data/raw`. Successful earlier windows remain cached. Rerun ingestion after the provider recovers.

### Missing weather join coverage

If coverage falls below 90 percent, inspect timestamp time zones and provider gaps. Do not fill a large outage automatically. Record the cause and decide whether a narrower period is scientifically defensible.

### Data contract rejects a year

Confirm the configured period and raw response. The allowed analytical years are deliberately strict. Changing them requires a reviewed configuration change and a new evaluation plan.

### Physical range failure

Inspect the raw provider payload before changing a limit. A unit or reference-datum change can resemble an extreme event. Never widen a rule solely to make the pipeline pass.

### Model does not beat persistence

This is a valid outcome. The pipeline deploys persistence for that horizon. Review data quality and feature availability, but do not select a model using final test results.

### Interval coverage degrades

Compare the current surge-volatility distribution with calibration. Check coverage by month and event severity. Recalibrate only with a new documented calibration period that remains separate from the final evaluation set.

### API reports degraded health

Verify that `model_bundle.joblib` and `features.parquet` exist and that `COASTCAST_CONFIG` and `COASTCAST_MODEL_DIR` point to the matching artifact set.

## Recovery order

1. Preserve raw cached responses and provider request metadata.
2. Rebuild bronze tables if parsing changed.
3. Rebuild silver and gold tables.
4. Run dbt and Python tests.
5. Retrain all horizons.
6. Regenerate the evaluation report.
7. Restart API and dashboard services.

## Data retention

Raw source responses should be kept with the artifact version they produced. Bronze, silver, and gold layers can be rebuilt from that cache. Never mix a model bundle with a gold feature table from a different run.

## Security

The current data sources require no secrets. The service should run as a non-root container user. Azure and registry credentials belong in the deployment platform secret store, not in `.env`, source files, or container images.
