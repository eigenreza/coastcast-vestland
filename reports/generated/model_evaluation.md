# Model evaluation

Expanding-window validation begins on 2020-01-01 in 12-month steps.
The independent uncertainty-calibration period begins on 2024-01-01.
The final test period begins on 2025-01-01.
The test period is not used for fitting, uncertainty calibration, or champion selection.

| Horizon | Champion | Test MAE | Daily-block 95% CI | Persistence MAE | MAE reduction 95% CI | RMSE | Coverage |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 h | gradient boosting | 1.42 cm | 1.38-1.47 cm | 1.51 cm | 0.07-0.10 cm | 1.85 cm | 90.1% |
| 3 h | gradient boosting | 2.20 cm | 2.11-2.30 cm | 2.54 cm | 0.30-0.38 cm | 2.95 cm | 95.2% |
| 6 h | gradient boosting | 2.89 cm | 2.76-3.05 cm | 3.40 cm | 0.41-0.60 cm | 3.93 cm | 95.6% |
| 12 h | gradient boosting | 3.90 cm | 3.67-4.16 cm | 4.81 cm | 0.73-1.08 cm | 5.29 cm | 97.0% |

## Interpretation

A learned model is deployed only when it beats persistence on the validation period.
This rule prevents additional model complexity from being rewarded without evidence.
Coverage should be interpreted alongside interval width and event-specific errors.

## Acceptance checks

- Every deployed champion has passed an out-of-time selection step.
- The untouched test period reports both champion and persistence error.
- The prediction interval target is 90 percent marginal coverage.
- Daily-block bootstrap intervals preserve within-day dependence in test errors.
- All analytical observations are restricted to the configured study window.
