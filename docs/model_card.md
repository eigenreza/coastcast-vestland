# Model card

## Model details

Name: CoastCast Vestland surge residual forecaster

Version: 0.1.0

Location: Bergen permanent tide gauge, station BGO

Horizons: 1, 3, 6, and 12 hours

Reference level: mean sea level

## Intended use

The model supports retrospective analysis, method evaluation, and interactive exploration of coastal operating thresholds. It can help analysts understand how wind, pressure, tide, and recent water-level behavior combine over short horizons.

## Uses outside scope

The model is not approved for:

- navigation
- emergency warning
- flood evacuation decisions
- design-code compliance
- autonomous vessel or infrastructure control
- direct transfer to another station without validation

Official provider forecasts and warnings remain authoritative.

## Data

The analytical build contains 78,888 hourly rows from 1 January 2017 through 31 December 2025. Kartverket supplies observed water level and astronomical tide. Open-Meteo supplies ECMWF IFS meteorological analysis at the gauge coordinates. The final learned estimators use pre-2024 rows only; later years are isolated for calibration and testing.

## Evaluation design

Champion selection pools four expanding annual validations: models trained on 2017-2019, 2017-2020, 2017-2021, and 2017-2022 predict calendar years 2020, 2021, 2022, and 2023 respectively. The selected learned method is refitted on 2017-2023. Calendar year 2024 calibrates uncertainty, and the full calendar year 2025 is the untouched test. Horizon-length boundary purges prevent label overlap. The test year is not used for fitting, champion selection, or interval calibration.

## Delivered test results

| Horizon | Champion | MAE | Daily-block 95% MAE CI | Persistence MAE | Interval coverage | Mean width |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 hour | Gradient boosting | 1.42 cm | 1.38-1.47 cm | 1.51 cm | 90.1% | 7.64 cm |
| 3 hours | Gradient boosting | 2.20 cm | 2.11-2.30 cm | 2.54 cm | 95.2% | 14.46 cm |
| 6 hours | Gradient boosting | 2.89 cm | 2.76-3.05 cm | 3.40 cm | 95.6% | 18.83 cm |
| 12 hours | Gradient boosting | 3.90 cm | 3.67-4.16 cm | 4.81 cm | 97.0% | 27.07 cm |

The daily-block bootstrap 95% confidence interval for MAE reduction relative to persistence is positive at every horizon: 0.07-0.10 cm, 0.30-0.38 cm, 0.41-0.60 cm, and 0.73-1.08 cm from 1 through 12 hours. These intervals resample complete days to retain short-range dependence in hourly errors.

## Uncertainty

Intervals target 90 percent marginal coverage. They are scaled by recent surge volatility and calibrated conservatively across months. Test coverage ranges from 90.1 to 97.0 percent. Coverage is empirical, not a guarantee for any individual event; the conservative monthly rule trades wider intervals for seasonal robustness.

## Validated scope and extension priorities

The published evidence supports a clearly defined use case: short-horizon analysis at Bergen station
BGO over the 2017 to 2025 study period. Within that scope, CoastCast provides reproducible model
selection, baseline comparison, and uncertainty evaluation. The following boundaries identify the
data and validation needed for broader use:

- Rare return-period events require a longer event record and an extreme-value analysis designed for that purpose.
- Additional Vestland gauges require site-specific validation before a regional model can be claimed.
- The current meteorological inputs represent a numerical analysis grid rather than a collocated instrument.
- Archived future meteorological trajectories are the natural next input for prospective multi-hour forecasts.
- Seasonal or storm-regime shifts should be tracked through rolling error and interval-coverage monitoring.
- Operational thresholds remain user-defined because their meaning depends on the decision context.

## Monitoring recommendations

If moved to prospective use, monitor:

- source freshness and missingness
- residual MAE by horizon and month
- interval coverage over a rolling 30-day window
- pressure, wind, and surge feature drift
- threshold-event recall
- model performance relative to persistence

Retraining should occur only after a documented review of drift, source changes, and holdout design.
