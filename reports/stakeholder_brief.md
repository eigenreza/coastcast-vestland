---
marp: true
theme: default
paginate: true
title: CoastCast Vestland
---

# CoastCast Vestland

Short-horizon coastal water-level forecasting for Bergen

Nine years of public hourly data, 2017-2025

---

# The operational question

When is a coastal operating window likely to remain below a chosen water-level threshold?

CoastCast combines:

- measured water level
- known astronomical tide
- wind and atmospheric pressure
- calibrated forecast uncertainty

---

# A physically meaningful target

```text
surge residual = observed water level - astronomical tide
```

The model forecasts the weather-driven residual.

Known future tide is added back to obtain total water level.

---

# Production-shaped data flow

```text
Public APIs -> cached raw data -> Parquet lakehouse
            -> tested feature table -> forecast models
            -> API and interactive dashboard
```

78,888 hourly records

100 percent source join coverage

---

# Models must earn deployment

Every learned model competes with persistence.

| Horizon | Selected method |
| ---: | --- |
| 1 hour | Gradient boosting |
| 3 hours | Gradient boosting |
| 6 hours | Gradient boosting |
| 12 hours | Gradient boosting |

The final test period never determines champion selection.

---

# Final test accuracy

| Horizon | CoastCast MAE | Persistence MAE |
| ---: | ---: | ---: |
| 1 hour | 1.42 cm | 1.51 cm |
| 3 hours | 2.20 cm | 2.54 cm |
| 6 hours | 2.89 cm | 3.40 cm |
| 12 hours | 3.90 cm | 4.81 cm |

Daily-block bootstrap confidence intervals confirm a positive MAE reduction at every horizon.

---

# Uncertainty changes with conditions

Prediction intervals scale with recent surge volatility.

- quiet period: narrower interval
- unsettled period: wider interval
- 90 percent target coverage
- 90.1 to 97.0 percent coverage across all horizons on the final test year

---

# Interactive decision support

Users can change:

- issue time
- forecast horizon
- operating threshold
- wind intensity
- atmospheric pressure

The dashboard updates prediction, uncertainty, and threshold status immediately.

---

# Responsible use

CoastCast is an independent analytical decision-support system. It complements official services by
making short-horizon model behavior, uncertainty, and threshold sensitivity visible and testable.

Navigation, warnings, emergency response, and engineering compliance should continue to use the
authoritative operational products and standards intended for those decisions.

---

# Next step

Add archived forecast trajectories for future wind and pressure.

Then validate transfer to additional Vestland gauges.
