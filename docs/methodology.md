# Forecasting methodology

## Problem formulation

Let observed total water level at time `t` be `W(t)` and astronomical tide be `T(t)`. The surge residual is:

```text
S(t) = W(t) - T(t)
```

For each horizon `h`, the model estimates `S(t+h)` from information available at issue time `t`. Total water level is reconstructed with the known future tide:

```text
W_hat(t+h) = S_hat(t+h) + T(t+h)
```

This separates the deterministic tidal cycle from the weather-sensitive quantity the model needs to learn.

## Features

The model receives:

- current surge residual and astronomical tide
- pressure, wind, gust, precipitation, and temperature
- eastward and northward wind components
- surge, pressure, and wind lags from 1 to 48 hours
- rolling surge mean and standard deviation
- pressure change over several windows
- cyclic hour-of-day and day-of-year encodings

Meteorological wind direction describes where wind comes from. The vector conversion follows that convention.

## Forecast horizons

Separate estimators are trained for 1, 3, 6, and 12 hours. Independent models let selection, calibration, and failure analysis vary by horizon.

## Temporal validation

The full configuration uses an expanding annual evaluation followed by two independent holdouts:

| Model fit available at issue time | Out-of-time validation |
| --- | --- |
| 2017-2019 | Calendar year 2020 |
| 2017-2020 | Calendar year 2021 |
| 2017-2021 | Calendar year 2022 |
| 2017-2022 | Calendar year 2023 |

The four validation years are pooled for champion selection while the year-specific results remain available for stability analysis. The selected learned estimator is then refitted on 2017-2023. Calendar year 2024 is used only for uncertainty calibration, and the full calendar year 2025 is the untouched final test.

No random row split is used. Lag construction occurs before splitting, and each feature row contains only present or past information. A purge equal to the forecast horizon is applied at each boundary so a training or calibration label cannot cross into the next period. Future tide is used only to reconstruct a forecast valid time, not as a learned weather signal.

## Baseline and champion rule

Persistence predicts that the current surge residual will continue through the forecast horizon. It is a strong short-horizon baseline.

The gradient-boosted model becomes champion only when its pooled expanding-window mean absolute error is no worse than persistence. The rule is applied independently to each horizon. More complex behavior is therefore deployed only when it has earned its place.

## Final fitting

After champion selection, the learned estimator is refitted on all rows before 2024. The calibration year remains untouched. This uses the complete pre-calibration history without contaminating the uncertainty scores.

## Uncertainty

Absolute calibration residuals are divided by the rolling 24-hour surge standard deviation. A conformal quantile is calculated globally and for each calibration month. The largest valid quantile is retained. At prediction time:

```text
interval radius = conformal multiplier * current rolling surge volatility
```

The approach is distribution-free under standard exchangeability assumptions, but coastal weather is not fully exchangeable across seasons. Monthly robustness and local scaling reduce that risk without using the test period.

## Metrics

- MAE in centimetres for operational interpretability
- RMSE in centimetres for sensitivity to large errors
- bias in centimetres for systematic overprediction or underprediction
- empirical interval coverage
- mean interval width
- persistence MAE for every horizon
- daily-block bootstrap 95% confidence intervals for test MAE
- daily-block bootstrap 95% confidence intervals for MAE reduction relative to persistence

The bootstrap resamples whole calendar days rather than individual hours. This preserves the within-day dependence structure in forecast errors and avoids pretending that every hourly error is independent.

## Reproducibility

The configuration fixes the random seed, data period, feature windows, model parameters, and split dates. Cached raw responses and a manifest record the source scope. The artifact signature records exact feature order and supported horizons.
