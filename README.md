# CoastCast Vestland

**[Explore the live CoastCast dashboard on Azure](https://coastcast-bergen.azurewebsites.net/)**

CoastCast Vestland turns Bergen tide-gauge and weather data into short-horizon coastal water-level forecasts that can be explored directly in a browser. I built it as a complete, reproducible forecasting system rather than a standalone modeling notebook: the repository covers data ingestion, analytical transformations, feature engineering, time-aware model selection, calibrated uncertainty, API serving, an interactive dashboard, automated tests, containerization, and Azure deployment.

## What CoastCast answers

For a selected issue time, CoastCast estimates:

- the total water level 1, 3, 6, or 12 hours ahead
- the weather-driven surge contribution
- the known astronomical tide component
- a calibrated 90% prediction interval
- whether that interval reaches a user-defined decision threshold

The dashboard also includes wind and pressure controls for focused what-if analysis. Each change runs the forecasting engine on demand, so it is easy to see how the estimate and its uncertainty respond.

## How the forecast is built

The primary modeling target is observed water level minus astronomical tide at the Bergen tide gauge. This weather-driven remainder is the surge residual. CoastCast forecasts the residual and then reconstructs total water level as:

```text
forecast total water level = known astronomical tide + forecast surge residual
```

This decomposition keeps the machine-learning problem physically interpretable. The regular tide remains explicit, while wind, atmospheric pressure, recent water-level behavior, and seasonal structure explain the less predictable component.

At every forecast horizon, gradient boosting competes with a strong persistence baseline across four annual expanding-window validations. The better out-of-time method becomes the champion. A separate calendar year converts forecast errors into prediction intervals, and the full calendar year 2025 remains untouched until final evaluation.

## What is inside the project

- resilient Kartverket and Open-Meteo clients with caching and retry logic
- bronze, silver, and gold analytical layers built with Parquet, DuckDB, and dbt
- feature and data contracts that guard timestamps, ranges, uniqueness, and leakage
- horizon-specific champion selection against persistence
- calibrated uncertainty that responds to recent surge volatility
- a versioned FastAPI prediction service
- an interactive Streamlit decision-support dashboard
- Airflow orchestration and command-line pipeline entry points
- automated tests, linting, container builds, and Azure infrastructure definitions

MLflow experiment tracking is available as an optional training integration. It is intentionally excluded from the public serving image because the deployed inference path does not require the tracking stack.

## Data scope

The reproducible study window runs from 1 January 2017 through 31 December 2025 and contains 78,888 hourly observations from each source. Pipeline validation rejects analytical observations outside that versioned window.

Evaluation follows the clock rather than randomly mixing hours. The first model fits 2017-2019 and predicts 2020. The training window then expands, producing separate out-of-time validations for 2021, 2022, and 2023. The selected method is refitted on information available through 2023. Calendar year 2024 is reserved for uncertainty calibration, and calendar year 2025 is the untouched final test. A horizon-length purge at every boundary prevents a target from crossing into the next split.

| Horizon | Champion | 2025 MAE | Persistence MAE | Daily-block 95% MAE CI | 90% interval coverage |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 hour | Gradient boosting | 1.42 cm | 1.51 cm | 1.38-1.47 cm | 90.1% |
| 3 hours | Gradient boosting | 2.20 cm | 2.54 cm | 2.11-2.30 cm | 95.2% |
| 6 hours | Gradient boosting | 2.89 cm | 3.40 cm | 2.76-3.05 cm | 95.6% |
| 12 hours | Gradient boosting | 3.90 cm | 4.81 cm | 3.67-4.16 cm | 97.0% |

For every horizon, a daily-block bootstrap 95% confidence interval for the MAE reduction relative to persistence remains above zero on the final test year. Resampling whole days preserves short-range dependence better than treating 8,760 hourly errors as independent observations.

| Source | Variables | Role |
| --- | --- | --- |
| Kartverket water-level API | Observed water level, astronomical tide | Target and deterministic component |
| Open-Meteo Historical Weather API | Pressure, wind, gusts, precipitation, temperature | Meteorological covariates |

Both clients retain an immutable local request cache. Full attribution, provenance, and interpretation notes are available in [`docs/data_sources.md`](docs/data_sources.md).

## Architecture

```text
Source APIs
    -> immutable JSON and XML cache
    -> bronze Parquet
    -> dbt and DuckDB silver models
    -> analytics-ready gold feature table
    -> time-aware training and calibrated intervals
    -> FastAPI and Streamlit
    -> Azure App Service
```

The live Azure dashboard uses the same packaged model bundle and feature contract as the local application. Its container runs as an unprivileged user, HTTPS is enforced by Azure, and registry access uses a managed identity rather than stored registry credentials. The free App Service plan releases inactive compute and starts the application again when it receives a new visit.

## Run CoastCast locally

Python 3.11 or 3.12 is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
python -m coastcast.cli pipeline --config configs/base.yml
```

Start the API:

```powershell
uvicorn coastcast.api.main:app --host 0.0.0.0 --port 8000
```

Start the dashboard in another terminal:

```powershell
streamlit run src/coastcast/dashboard/app.py
```

Focused pipeline commands are also available:

```powershell
python -m coastcast.cli ingest --config configs/base.yml
python -m coastcast.cli build --config configs/base.yml
python -m coastcast.cli train --config configs/base.yml
python -m coastcast.cli evaluate --config configs/base.yml
```

## A faster demonstration run

`configs/demo.yml` limits ingestion to 2022-2025. It still uses real source data and preserves distinct validation, calibration, and test years while keeping a complete laptop run conveniently short.

```powershell
python -m coastcast.cli pipeline --config configs/demo.yml
```

## Containers

```powershell
docker compose up --build
```

The dashboard is available on port 8501 and the API on port 8000. Run the pipeline profile separately when fresh artifacts are needed:

```powershell
docker compose --profile pipeline run pipeline
```

## Quality checks

```powershell
ruff check src tests orchestration
pytest
dbt test --project-dir transform --profiles-dir transform
```

Data contracts check allowed years, timestamps, uniqueness, physical ranges, missingness, and join coverage. Model evaluation uses expanding-window validation, an independent uncertainty-calibration window, and a final untouched holdout. Persistence is the required baseline rather than an easy comparison model.

## Documentation map

- [`docs/architecture.md`](docs/architecture.md): components and data flow
- [`docs/data_sources.md`](docs/data_sources.md): source provenance and interpretation boundaries
- [`docs/methodology.md`](docs/methodology.md): feature, validation, and calibration design
- [`docs/model_card.md`](docs/model_card.md): intended use, metrics, and validated scope
- [`docs/runbook.md`](docs/runbook.md): operations, failures, and recovery
- [`docs/api.md`](docs/api.md): prediction service contract
- [`docs/deployment.md`](docs/deployment.md): container and Azure release process
- [`reports/technical_report.md`](reports/technical_report.md): analytical narrative and acceptance evidence

## Validated scope and responsible use

The current evidence base covers Bergen station BGO over the fixed 2017-2025 study window. Keeping that window and its chronological evaluation fixed makes the published metrics, charts, and model comparisons reproducible. The live application recomputes forecasts and scenarios on demand; connecting continuously arriving observations and archived operational weather forecasts is the next step toward prospective current-data operation.

CoastCast is an independent analytical decision-support system. It adds value by making forecast decomposition, uncertainty, baseline comparisons, and scenario sensitivity transparent. Official Kartverket and MET Norway products remain the appropriate sources for navigation, warnings, emergency response, and other safety-critical decisions.
