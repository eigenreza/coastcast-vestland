# CoastCast Vestland technical report

## Executive summary

CoastCast is a reproducible coastal forecasting system centered on the Bergen tide gauge. It separates total water level into astronomical tide and a weather-driven residual, then forecasts that residual at four short horizons.

The delivered analytical build contains 78,888 hourly records covering 1 January 2017 through 31 December 2025. Kartverket water-level data joined historical weather covariates with 100 percent timestamp coverage. The full calendar year 2025 remained untouched until evaluation.

Gradient boosting earned deployment at all four horizons by beating persistence across four expanding annual validations. On the final test year, every learned champion reduced mean absolute error relative to persistence, and every daily-block bootstrap 95 percent confidence interval for that reduction remained above zero.

## Operational question

Coastal operators often care less about a raw forecast than whether a planned window remains below a context-specific water-level threshold. CoastCast therefore produces a total water-level estimate, an uncertainty interval, and a threshold assessment. The dashboard lets an analyst vary the threshold, wind intensity, and pressure state while retaining the selected historical issue time.

## Data foundation

Kartverket supplies both measured water level and astronomical tide at station BGO. Their difference forms the surge residual. ECMWF IFS historical analysis supplied through Open-Meteo provides wind, pressure, gust, precipitation, and temperature context.

All timestamps are normalized to UTC. Data contracts reject duplicates, values outside broad physical limits, unacceptable missingness, insufficient join coverage, and event timestamps outside 2017-2025. Source manifests record coverage, row counts, retrieval metadata, and SHA-256 checksums.

## Analytical approach

The feature set combines physical context and recent system state:

- current tide and surge residual
- pressure and pressure changes
- wind speed, gust, direction, and vector components
- precipitation and temperature
- lags through 48 hours
- rolling surge mean and volatility
- daily and annual cyclic encodings

The model is a histogram gradient-boosted regressor. It handles nonlinear interactions and missing feature values without requiring a deep neural architecture. A persistence forecast provides a demanding operational baseline.

## Validation discipline

The chronology is fixed before evaluation:

1. Fit on 2017-2019 and validate on 2020.
2. Expand the fit by one year at a time and validate separately on 2021, 2022, and 2023.
3. Select between gradient boosting and persistence from the pooled out-of-time errors.
4. Refit the selected learned approach on 2017-2023.
5. Calibrate volatility-sensitive intervals on calendar year 2024.
6. Evaluate once on the untouched calendar year 2025.

A purge equal to each forecast horizon keeps labels from crossing a split boundary. The test year never determines champion selection or interval width.

## Results

| Horizon | Champion | Test MAE | Daily-block 95% MAE CI | Baseline MAE | Test RMSE | Coverage |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 hour | Gradient boosting | 1.42 cm | 1.38-1.47 cm | 1.51 cm | 1.85 cm | 90.1% |
| 3 hours | Gradient boosting | 2.20 cm | 2.11-2.30 cm | 2.54 cm | 2.95 cm | 95.2% |
| 6 hours | Gradient boosting | 2.89 cm | 2.76-3.05 cm | 3.40 cm | 3.93 cm | 95.6% |
| 12 hours | Gradient boosting | 3.90 cm | 3.67-4.16 cm | 4.81 cm | 5.29 cm | 97.0% |

Forecast error grows predictably with lead time. The 1-hour improvement is small, confirming that persistence is difficult to beat at very short horizons, while the absolute improvement grows with lead time. Daily-block bootstrap confidence intervals for the MAE reduction versus persistence are 0.07-0.10 cm, 0.30-0.38 cm, 0.41-0.60 cm, and 0.73-1.08 cm respectively.

The target interval coverage is 90 percent. Volatility-normalized conformal calibration achieved at least 90.1 percent coverage at every horizon. The conservative monthly calibration rule produces wider intervals at longer horizons in exchange for seasonal robustness. The public application exposes interval width so users can see that uncertainty directly.

## Engineering outcome

The project includes:

- cached and retryable provider clients
- Parquet bronze, silver, and gold layers
- DuckDB analytical tables
- dbt models and tests
- Airflow orchestration
- model selection and calibrated uncertainty
- versioned artifacts and signatures
- a FastAPI service
- an interactive Streamlit dashboard
- Docker and Azure App Service definitions
- automated tests, linting, and CI/CD configuration
- a model card, data dictionary, runbook, and deployment guide

## Validated scope and next steps

The current evidence base is deliberately specific: Bergen station BGO, the 2017 to 2025 study window, and short-horizon water-level forecasting. That boundary keeps the reported model comparison and uncertainty results reproducible. Regulatory return levels require a dedicated extreme-value design, while transfer to other locations requires site-specific validation. The weather covariates in this release are numerical analysis values rather than collocated observations.

The most valuable next improvement is to ingest archived meteorological forecast trajectories that were actually available at each issue time. That would give the 6-hour and 12-hour models explicit information about future wind and pressure instead of relying entirely on current state and lags. A second validated gauge could then test spatial transfer and support a multi-site Vestland view.

## Conclusion

CoastCast demonstrates that careful decomposition, strong baselines, strict time splits, and transparent uncertainty produce a useful forecasting system without unnecessary model complexity. The delivered application makes the results explorable while keeping source provenance, validated scope, and responsible-use boundaries visible.
