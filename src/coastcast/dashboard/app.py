"""Interactive scenario explorer for historical CoastCast forecasts."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from coastcast.config import load_settings
from coastcast.serving import ForecastEngine

st.set_page_config(page_title="CoastCast Vestland", page_icon="🌊", layout="wide")


@st.cache_resource
def load_runtime() -> tuple[object, ForecastEngine, dict[str, object], pd.DataFrame]:
    settings = load_settings(os.getenv("COASTCAST_CONFIG", "configs/base.yml"))
    model_dir = Path(os.getenv("COASTCAST_MODEL_DIR", str(settings.paths.artifacts)))
    engine = ForecastEngine(
        bundle_path=model_dir / "model_bundle.joblib",
        feature_path=settings.paths.gold / "features.parquet",
    )
    metrics = json.loads((model_dir / "metrics.json").read_text(encoding="utf-8"))
    predictions = pd.read_parquet(model_dir / "test_predictions.parquet")
    predictions["timestamp"] = pd.to_datetime(predictions["timestamp"], utc=True)
    return settings, engine, metrics, predictions


st.title("CoastCast Vestland")
st.caption("Interactive Bergen coastal water-level forecasting with calibrated uncertainty")
st.markdown(
    "Built by **Reza Azad Gholami** · "
    "[My GitHub profile](https://github.com/eigenreza/EigenReza) · "
    "[Project repository](https://github.com/eigenreza/coastcast-vestland)"
)
st.caption(
    "On-demand inference · 1, 3, 6, and 12-hour horizons · "
    "90% prediction intervals · threshold and weather what-if tools"
)

try:
    settings, engine, metrics, predictions = load_runtime()
except (FileNotFoundError, ValueError, OSError) as exc:
    st.error("Runtime artifacts are not ready. Run the CoastCast pipeline first.")
    st.code(str(exc))
    st.stop()

available = engine.available_times()
minimum_date = available.min().date()
maximum_date = available.max().date()
default_date = max(minimum_date, maximum_date - pd.Timedelta(days=14))
date_range = (
    f"{minimum_date.day} {minimum_date:%B %Y} through {maximum_date.day} {maximum_date:%B %Y}"
)
study_range = (
    f"{settings.period.start:%-d %B %Y} through {settings.period.end:%-d %B %Y}"
    if os.name != "nt"
    else f"{settings.period.start.day} {settings.period.start:%B %Y} through "
    f"{settings.period.end.day} {settings.period.end:%B %Y}"
)

with st.expander("What CoastCast does and how to explore it"):
    st.markdown(
        f"""
        I built CoastCast to make a technically rigorous water-level forecast easy to explore. Pick
        a recorded moment in Bergen and the app answers three practical questions: **What water
        level does the model expect in the next few hours? How uncertain is that estimate? Could the
        plausible range reach a level that matters to me?**

        **Choose a starting point.** Select any day from **{date_range}**, then choose the issue hour
        in UTC. Near the edges of the data window, CoastCast may move to the nearest complete hour so
        it has the earlier observations and future tide value needed for a valid forecast.

        **Set the question.** Choose a 1, 3, 6, or 12-hour horizon and a decision threshold. The
        status banner checks the complete prediction interval, not only the central estimate, so the
        uncertainty is part of the decision rather than an afterthought.

        **Explore a weather scenario.** Leave wind at **1.00** and pressure at **0 hPa** to use the
        recorded conditions. Adjust either control to see the estimate update immediately and
        examine how a different issue-time weather state changes the surge contribution.

        Behind the interface, CoastCast separates the predictable astronomical tide from the harder
        weather-driven residual. A gradient-boosted model competes with a strong persistence
        baseline at each horizon, and a separate calibration period turns recent forecast errors
        into a 90% prediction interval.

        This Azure deployment is live, and every selection triggers **on-demand model inference**.
        The published data window is versioned so the results and performance figures remain
        reproducible. The **About** tab explains the multi-year evaluation design, each output, and
        how the cached pipeline can be refreshed without changing the analytical contract.
        """
    )

with st.sidebar:
    st.header("Forecast scenario")
    selected_date = st.date_input(
        "Issue date",
        value=default_date,
        min_value=minimum_date,
        max_value=maximum_date,
    )
    selected_hour = st.slider("Issue hour, UTC", 0, 23, 12)
    horizon = st.select_slider(
        "Forecast horizon", options=engine.horizons, value=6, format_func=lambda x: f"{x} hours"
    )
    threshold = st.slider("Decision threshold, cm MSL", -50, 250, 100, 5)
    st.subheader("What-if controls")
    wind_multiplier = st.slider("Wind intensity multiplier", 0.0, 2.0, 1.0, 0.05)
    pressure_delta = st.slider("Pressure adjustment, hPa", -30.0, 30.0, 0.0, 1.0)
    st.caption(
        "Use these controls to explore how a different issue-time weather state changes the model estimate."
    )

issue_time = pd.Timestamp(selected_date, tz="UTC") + pd.Timedelta(hours=selected_hour)
if issue_time not in available:
    nearest_position = available.get_indexer([issue_time], method="nearest")[0]
    issue_time = available[nearest_position]
    st.info(f"The nearest complete issue time was selected: {issue_time:%Y-%m-%d %H:%M UTC}")

result = engine.forecast(
    issue_time=issue_time,
    horizon_hours=horizon,
    threshold_cm=float(threshold),
    wind_speed_multiplier=wind_multiplier,
    pressure_delta_hpa=pressure_delta,
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Predicted total", f"{result.predicted_total_cm:.1f} cm")
col2.metric("Surge contribution", f"{result.predicted_surge_cm:.1f} cm")
col3.metric("Astronomical tide", f"{result.tide_cm:.1f} cm")
col4.metric("90% interval", f"{result.lower_total_cm:.0f} to {result.upper_total_cm:.0f} cm")

if result.threshold_exceeded:
    st.warning(
        "The prediction interval reaches the selected threshold. Review the operating window."
    )
else:
    st.success("The prediction interval remains below the selected threshold.")

forecast_tab, performance_tab, data_tab, about_tab = st.tabs(
    ["Forecast explorer", "Model performance", "Data context", "About"]
)

with forecast_tab:
    horizon_predictions = predictions[predictions["horizon_hours"] == horizon].copy()
    window = horizon_predictions[
        horizon_predictions["timestamp"].between(
            issue_time - pd.Timedelta(days=7), issue_time + pd.Timedelta(days=7)
        )
    ]
    figure = go.Figure()
    if window.empty:
        historical_window = engine.features[
            engine.features["timestamp"].between(
                issue_time - pd.Timedelta(days=7), issue_time + pd.Timedelta(days=7)
            )
        ]
        figure.add_trace(
            go.Scatter(
                x=historical_window["timestamp"],
                y=historical_window[f"target_total_h{horizon}"],
                name="Observed outcome",
                line={"color": "#222222"},
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[issue_time],
                y=[result.predicted_total_cm],
                mode="markers",
                marker={"color": "#1f77b4", "size": 11},
                name="Selected prediction",
                error_y={
                    "type": "data",
                    "symmetric": False,
                    "array": [result.upper_total_cm - result.predicted_total_cm],
                    "arrayminus": [result.predicted_total_cm - result.lower_total_cm],
                    "color": "#1f77b4",
                    "thickness": 2,
                    "width": 6,
                },
            )
        )
        figure_title = f"Observed {horizon}-hour outcomes and the selected historical forecast"
        st.info(
            "This date is outside the untouched test period. The chart therefore shows one "
            "on-demand forecast against historical outcomes, rather than presenting fitted-period "
            "predictions as independent test results."
        )
    else:
        figure.add_trace(
            go.Scatter(
                x=window["timestamp"],
                y=window["upper_surge_cm"] + window["tide_cm"],
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=window["timestamp"],
                y=window["lower_surge_cm"] + window["tide_cm"],
                fill="tonexty",
                fillcolor="rgba(45, 130, 180, 0.18)",
                line={"width": 0},
                name="90% interval",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=window["timestamp"],
                y=window["actual_total_cm"],
                name="Observed",
                line={"color": "#222222"},
            )
        )
        figure.add_trace(
            go.Scatter(
                x=window["timestamp"],
                y=window["predicted_total_cm"],
                name="Predicted",
                line={"color": "#1f77b4"},
            )
        )
        figure_title = f"{horizon}-hour total water-level forecasts near the selected date"
    figure.add_hline(
        y=threshold, line_dash="dash", line_color="#d62728", annotation_text="Selected threshold"
    )
    figure.update_layout(
        title=figure_title,
        xaxis_title="Issue time",
        yaxis_title="Centimetres relative to mean sea level",
        hovermode="x unified",
        legend={"orientation": "h"},
    )
    st.plotly_chart(figure, width="stretch")
    st.caption(f"Champion for this horizon: {result.champion.replace('_', ' ')}")

with performance_tab:
    horizon_metrics = metrics[str(horizon)]
    test = horizon_metrics["test"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Test MAE", f"{test['mae_cm']:.2f} cm")
    m2.metric("Test RMSE", f"{test['rmse_cm']:.2f} cm")
    m3.metric("Interval coverage", f"{test['interval_coverage']:.1%}")
    m4.metric("Persistence MAE", f"{test['persistence_mae_cm']:.2f} cm")
    mae_interval = test["mae_daily_block_bootstrap_95_ci_cm"]
    st.caption(
        f"Test MAE daily-block bootstrap 95% CI: {mae_interval[0]:.2f} to "
        f"{mae_interval[1]:.2f} cm. Blocks preserve within-day dependence in forecast errors."
    )
    improvement_interval = test["mae_reduction_vs_persistence_daily_block_bootstrap_95_ci_cm"]
    st.success(
        "Estimated MAE reduction versus persistence: "
        f"{test['persistence_mae_cm'] - test['mae_cm']:.2f} cm "
        f"(daily-block 95% CI {improvement_interval[0]:.2f} to "
        f"{improvement_interval[1]:.2f} cm)."
    )
    scatter_sample = horizon_predictions.sample(
        min(2000, len(horizon_predictions)), random_state=42
    )
    scatter = px.scatter(
        scatter_sample,
        x="actual_total_cm",
        y="predicted_total_cm",
        opacity=0.45,
        labels={
            "actual_total_cm": "Observed total, cm",
            "predicted_total_cm": "Predicted total, cm",
        },
        title="Observed versus predicted total water level",
    )
    bounds = [
        min(scatter_sample["actual_total_cm"].min(), scatter_sample["predicted_total_cm"].min()),
        max(scatter_sample["actual_total_cm"].max(), scatter_sample["predicted_total_cm"].max()),
    ]
    scatter.add_trace(
        go.Scatter(x=bounds, y=bounds, mode="lines", name="Ideal", line={"dash": "dash"})
    )
    st.plotly_chart(scatter, width="stretch")
    st.subheader("Expanding-window model selection")
    rolling_rows = []
    for origin in horizon_metrics["rolling_origins"]:
        rolling_rows.append(
            {
                "Validation year": pd.Timestamp(origin["origin"]).year,
                "Training rows": int(origin["train_rows"]),
                "Model MAE, cm": origin["model"]["mae_cm"],
                "Persistence MAE, cm": origin["persistence"]["mae_cm"],
            }
        )
    st.dataframe(pd.DataFrame(rolling_rows), hide_index=True, width="stretch")
    st.caption(
        "Each row trains only on earlier observations. The champion is selected from the pooled "
        "out-of-time predictions, then refitted through 2023 before interval calibration."
    )

with data_tab:
    source_row = engine.features.loc[issue_time]
    context = pd.DataFrame(
        {
            "Variable": [
                "Observed level",
                "Tide",
                "Surge residual",
                "Pressure",
                "Wind speed",
                "Wind direction",
                "Wind gust",
            ],
            "Value": [
                f"{source_row['observed_water_level_cm']:.1f} cm",
                f"{source_row['tide_cm']:.1f} cm",
                f"{source_row['surge_residual_cm']:.1f} cm",
                f"{source_row['pressure_msl']:.1f} hPa",
                f"{source_row['wind_speed_10m']:.1f} m/s",
                f"{source_row['wind_direction_10m']:.0f}°",
                f"{source_row['wind_gusts_10m']:.1f} m/s",
            ],
        }
    )
    st.dataframe(context, hide_index=True, width="stretch")
    st.map(
        pd.DataFrame({"lat": [settings.location.latitude], "lon": [settings.location.longitude]}),
        zoom=9,
    )
    st.caption(
        "Gauge coordinates: Kartverket Bergen station BGO. Weather covariates use the nearest configured historical model grid cell."
    )

with about_tab:
    st.markdown(
        f"""
        ### Why I built CoastCast

        CoastCast brings the complete forecasting workflow into one place: trusted source data,
        physically meaningful features, time-aware model selection, calibrated uncertainty, and an
        interface where the result can be examined rather than simply reported. I designed it around
        two practical questions: what total water level should we expect at the selected horizon,
        and how much uncertainty should accompany that estimate?

        ### How the forecast works

        1. Historical observations are separated into the predictable astronomical tide and a
           weather-driven surge residual.
        2. Lagged water-level conditions and local wind and pressure variables describe the state
           at the selected issue time.
        3. For each 1, 3, 6, and 12-hour horizon, a gradient-boosted model competes with a strong
           persistence baseline. The better method across the pooled expanding-window validations
           becomes the champion.
        4. Held-out calibration errors provide a 90% prediction interval. The interval is allowed
           to widen when recent residual behaviour is more volatile.
        5. The predicted surge residual is added to the future astronomical tide to reconstruct the
           total water-level forecast shown in the dashboard.

        ### How to use the dashboard

        - **Issue date and hour:** choose a recorded starting point between **{date_range}**. Times
          are shown in UTC. Boundary dates may use the nearest complete hour
          because lagged observations and future tide values are needed.
        - **Forecast horizon:** choose how far ahead to predict. For example, selecting 6 hours asks
          for the expected water level six hours after the issue time. Longer horizons are generally
          less certain.
        - **Decision threshold:** set a water level relevant to your question. The status banner
          warns when the prediction interval, not only the central estimate, reaches it.
        - **Wind and pressure controls:** leave them at 1.00 and 0 hPa for recorded conditions, then
          adjust them to study a hypothetical issue-time weather state. These controls isolate model
          sensitivity and are not a substitute for a future meteorological trajectory.
        - **Forecast explorer:** compare predictions with observations and inspect the uncertainty
          band around the selected period.
        - **Model performance:** review errors, interval coverage, and the persistence comparison on
          the untouched calendar-2025 test period.
        - **Data context:** inspect the gauge and weather inputs behind the selected issue time and
          see the Bergen gauge location.

        ### Reading the outputs

        **Predicted total** is the central total water-level forecast relative to mean sea level.
        **Surge contribution** is the estimated weather-driven component. **Astronomical tide** is
        the deterministic tide component. **90% interval** is the calibrated range intended to
        contain roughly 90% of comparable outcomes. The observed line on the chart is retrospective
        truth used for evaluation and would not be known at the original issue time.

        ### What is live in this application?

        The Azure application is live, and model inference runs on demand. Changing the time,
        horizon, threshold, wind multiplier, or pressure adjustment immediately produces a new result
        using the same forecasting engine exposed by the project's API. The public release uses a
        completed **{study_range}** input store so every result and evaluation figure can be reproduced.
        The pipeline, API, validation checks, and monitoring design provide a clear route to adding
        continuously arriving gauge and operational weather feeds.

        ### Validated scope and responsible use

        Training, model selection, uncertainty calibration, and final testing use separate
        chronological periods. The first model learns from 2017-2019. Annual expanding-window
        validations cover 2020, 2021, 2022, and 2023, with each model seeing only earlier data.
        The selected method is refitted on 2017-2023, calendar year 2024 calibrates the 90%
        prediction intervals, and calendar year 2025 is the untouched final test. No random row
        split is used. Performance is compared with persistence rather than with a weak random
        baseline. The reported evidence applies to Bergen station BGO over the 2017-2025 study
        window. Extending the system to rare extremes, additional gauges, or prospective operations
        calls for corresponding event data and out-of-sample validation. Weather inputs in this
        release are ECMWF IFS analysis fields; archived operational forecast trajectories are the
        natural next input for prospective testing.

        CoastCast is an independent analytical decision-support system. It complements authoritative
        services by making model behavior, uncertainty, and scenario sensitivity transparent. For
        navigation, warnings, emergency response, and other safety-critical decisions, use official
        Kartverket and MET Norway products.

        I am **Reza Azad Gholami**, and I built CoastCast Vestland. You can find more of my work on
        [my GitHub profile](https://github.com/eigenreza/EigenReza) and inspect the complete
        [project repository](https://github.com/eigenreza/coastcast-vestland).
        """
    )
