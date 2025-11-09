"""Time-aware training, selection, uncertainty calibration, and artifact storage."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, os.cpu_count() or 1))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from coastcast.config import Settings
from coastcast.features import model_feature_columns

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HorizonResult:
    horizon: int
    estimator: HistGradientBoostingRegressor
    conformal_multiplier: float
    champion: str
    validation_metrics: dict[str, float]
    backtest_metrics: list[dict[str, Any]]
    calibration_metrics: dict[str, float]
    test_metrics: dict[str, Any]


def _metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    radius: float | np.ndarray | None = None,
) -> dict[str, float]:
    output = {
        "mae_cm": float(mean_absolute_error(actual, predicted)),
        "rmse_cm": float(mean_squared_error(actual, predicted) ** 0.5),
        "bias_cm": float(np.mean(predicted - actual)),
    }
    if radius is not None:
        output["interval_coverage"] = float(np.mean(np.abs(predicted - actual) <= radius))
        output["mean_interval_width_cm"] = float(2 * np.mean(radius))
    return output


def _conformal_radius(residuals: np.ndarray, alpha: float) -> float:
    n = len(residuals)
    level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(np.abs(residuals), level, method="higher"))


def _conformal_multiplier(
    residuals: np.ndarray,
    local_scale: np.ndarray,
    timestamps: pd.Series,
    alpha: float,
) -> float:
    """Calibrate normalized residuals with conservative monthly robustness."""
    safe_scale = np.maximum(local_scale, 1.0)
    scores = residuals / safe_scale
    candidates = [_conformal_radius(scores, alpha)]
    month = pd.to_datetime(timestamps, utc=True).dt.month
    for month_number in sorted(month.unique()):
        group_scores = scores[month.to_numpy() == month_number]
        if len(group_scores) >= 100:
            candidates.append(_conformal_radius(group_scores, alpha))
    return max(candidates)


def _new_estimator(settings: Settings) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=settings.model.learning_rate,
        max_iter=settings.model.n_estimators,
        max_depth=settings.model.max_depth,
        min_samples_leaf=settings.model.min_samples_leaf,
        l2_regularization=0.1,
        random_state=settings.model.random_state,
    )


def _validation_windows(settings: Settings) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = pd.Timestamp(settings.model.validation_start)
    calibration_start = pd.Timestamp(settings.model.calibration_start)
    while cursor < calibration_start:
        end = min(
            cursor + pd.DateOffset(months=settings.model.validation_window_months),
            calibration_start,
        )
        windows.append((cursor, end))
        cursor = end
    return windows


def _daily_block_bootstrap(
    actual: np.ndarray,
    selected: np.ndarray,
    persistence: np.ndarray,
    timestamps: pd.Series,
    *,
    seed: int,
    repetitions: int = 500,
) -> dict[str, list[float]]:
    days = pd.to_datetime(timestamps, utc=True).dt.floor("D").to_numpy()
    unique_days = np.unique(days)
    indices_by_day = [np.flatnonzero(days == day) for day in unique_days]
    rng = np.random.default_rng(seed)
    selected_scores: list[float] = []
    improvements: list[float] = []
    for _ in range(repetitions):
        sampled_day_indices = rng.integers(0, len(unique_days), size=len(unique_days))
        indices = np.concatenate([indices_by_day[index] for index in sampled_day_indices])
        selected_mae = float(mean_absolute_error(actual[indices], selected[indices]))
        persistence_mae = float(mean_absolute_error(actual[indices], persistence[indices]))
        selected_scores.append(selected_mae)
        improvements.append(persistence_mae - selected_mae)
    return {
        "mae_daily_block_bootstrap_95_ci_cm": [
            float(value) for value in np.quantile(selected_scores, [0.025, 0.975])
        ],
        "mae_reduction_vs_persistence_daily_block_bootstrap_95_ci_cm": [
            float(value) for value in np.quantile(improvements, [0.025, 0.975])
        ],
    }


def _log_mlflow_run(
    settings: Settings,
    metrics: dict[str, dict[str, Any]],
    artifact_dir: Path,
) -> None:
    """Record the run when MLflow is installed, without making local execution fragile."""
    try:
        import mlflow
    except ImportError:
        LOGGER.warning("MLflow is not installed, so experiment tracking was skipped")
        return

    try:
        configured_uri = os.getenv("MLFLOW_TRACKING_URI")
        if configured_uri and "://" in configured_uri:
            tracking_uri = configured_uri
        else:
            database_path = Path(configured_uri or settings.root / "mlflow.db").resolve()
            tracking_uri = f"sqlite:///{database_path.as_posix()}"
        mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment("coastcast-vestland")
        with mlflow.start_run(run_name="historical-multi-horizon"):
            mlflow.log_params(
                {
                    "station_code": settings.location.station_code,
                    "data_start": settings.period.start.date().isoformat(),
                    "data_end": settings.period.end.date().isoformat(),
                    "validation_start": settings.model.validation_start.date().isoformat(),
                    "test_start": settings.model.test_start.date().isoformat(),
                    "interval_alpha": settings.model.interval_alpha,
                    "weather_model": settings.ingestion.weather_model,
                }
            )
            for horizon, result in metrics.items():
                if horizon == "study":
                    continue
                mlflow.log_param(f"h{horizon}_champion", result["champion"])
                for metric_name, value in result["test"].items():
                    if isinstance(value, (int, float)):
                        mlflow.log_metric(f"h{horizon}_test_{metric_name}", float(value))
            for artifact_name in ("metrics.json", "signature.json", "model_bundle.joblib"):
                mlflow.log_artifact(str(artifact_dir / artifact_name), artifact_path="runtime")
    except Exception:
        LOGGER.warning("MLflow tracking failed after model artifacts were saved", exc_info=True)


def train(settings: Settings) -> Path:
    path = settings.paths.gold / "features.parquet"
    if not path.exists():
        raise FileNotFoundError("Gold feature table does not exist. Build the lakehouse first.")
    frame = pd.read_parquet(path).sort_values("timestamp")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    features = model_feature_columns(frame)
    trained: dict[int, HorizonResult] = {}
    prediction_frames: list[pd.DataFrame] = []
    validation_windows = _validation_windows(settings)

    for horizon in settings.features.horizons:
        lead = pd.Timedelta(hours=horizon)
        target = f"target_surge_h{horizon}"
        tide_target = f"target_tide_h{horizon}"
        usable = frame.dropna(subset=[target, tide_target, "surge_residual_cm"]).copy()
        backtest_metrics: list[dict[str, Any]] = []
        validation_actual: list[np.ndarray] = []
        validation_model_predictions: list[np.ndarray] = []
        validation_persistence_predictions: list[np.ndarray] = []
        for origin, window_end in validation_windows:
            origin_train = usable[usable["timestamp"] < origin - lead]
            validation_rows = usable[
                (usable["timestamp"] >= origin) & (usable["timestamp"] < window_end - lead)
            ]
            if min(len(origin_train), len(validation_rows)) < 100:
                raise ValueError(
                    f"Insufficient rows for horizon {horizon} at validation origin "
                    f"{origin.date().isoformat()}"
                )
            origin_estimator = _new_estimator(settings)
            origin_estimator.fit(origin_train[features], origin_train[target])
            model_prediction = origin_estimator.predict(validation_rows[features])
            persistence_prediction = validation_rows["surge_residual_cm"].to_numpy()
            actual = validation_rows[target].to_numpy()
            validation_actual.append(actual)
            validation_model_predictions.append(model_prediction)
            validation_persistence_predictions.append(persistence_prediction)
            backtest_metrics.append(
                {
                    "origin": origin.isoformat(),
                    "window_end": window_end.isoformat(),
                    "train_rows": len(origin_train),
                    "validation_rows": len(validation_rows),
                    "model": _metrics(actual, model_prediction),
                    "persistence": _metrics(actual, persistence_prediction),
                }
            )

        combined_actual = np.concatenate(validation_actual)
        combined_model = np.concatenate(validation_model_predictions)
        combined_persistence = np.concatenate(validation_persistence_predictions)
        model_validation_metrics = _metrics(combined_actual, combined_model)
        baseline_validation_metrics = _metrics(combined_actual, combined_persistence)
        champion = (
            "gradient_boosting"
            if model_validation_metrics["mae_cm"] <= baseline_validation_metrics["mae_cm"]
            else "persistence"
        )

        calibration_start = pd.Timestamp(settings.model.calibration_start)
        calibration_rows = usable[
            (usable["timestamp"] >= calibration_start)
            & (usable["timestamp"] < settings.model.test_start - lead)
        ]
        test_rows = usable[usable["timestamp"] >= settings.model.test_start]
        final_fit_rows = usable[usable["timestamp"] < calibration_start - lead]
        if min(len(final_fit_rows), len(calibration_rows), len(test_rows)) < 100:
            raise ValueError(
                f"Insufficient rows for horizon {horizon}: final fitting, calibration, and test "
                "splits need at least 100 each"
            )

        estimator = _new_estimator(settings)
        estimator.fit(final_fit_rows[features], final_fit_rows[target])
        calibration_model_prediction = estimator.predict(calibration_rows[features])
        calibration_persistence = calibration_rows["surge_residual_cm"].to_numpy()
        calibration_prediction = (
            calibration_model_prediction
            if champion == "gradient_boosting"
            else calibration_persistence
        )
        multiplier = _conformal_multiplier(
            calibration_rows[target].to_numpy() - calibration_prediction,
            calibration_rows["surge_std_24h"].to_numpy(),
            calibration_rows["timestamp"],
            settings.model.interval_alpha,
        )
        calibration_radius = multiplier * np.maximum(
            calibration_rows["surge_std_24h"].to_numpy(), 1.0
        )
        calibration_metrics = _metrics(
            calibration_rows[target].to_numpy(),
            calibration_prediction,
            calibration_radius,
        )
        calibration_metrics.update(
            {
                "model_mae_cm": _metrics(
                    calibration_rows[target].to_numpy(), calibration_model_prediction
                )["mae_cm"],
                "persistence_mae_cm": _metrics(
                    calibration_rows[target].to_numpy(), calibration_persistence
                )["mae_cm"],
            }
        )

        test_model = estimator.predict(test_rows[features])
        test_baseline = test_rows["surge_residual_cm"].to_numpy()
        selected_test = test_model if champion == "gradient_boosting" else test_baseline
        actual_test = test_rows[target].to_numpy()
        test_radius = multiplier * np.maximum(test_rows["surge_std_24h"].to_numpy(), 1.0)
        test_metrics = _metrics(actual_test, selected_test, test_radius)
        test_metrics.update(
            {
                "model_mae_cm": _metrics(actual_test, test_model)["mae_cm"],
                "persistence_mae_cm": _metrics(actual_test, test_baseline)["mae_cm"],
            }
        )
        test_metrics.update(
            _daily_block_bootstrap(
                actual_test,
                selected_test,
                test_baseline,
                test_rows["timestamp"],
                seed=settings.model.random_state + horizon,
            )
        )
        validation_metrics = {
            **{f"model_{key}": value for key, value in model_validation_metrics.items()},
            **{f"persistence_{key}": value for key, value in baseline_validation_metrics.items()},
            "rolling_origin_count": float(len(backtest_metrics)),
        }
        trained[horizon] = HorizonResult(
            horizon=horizon,
            estimator=estimator,
            conformal_multiplier=multiplier,
            champion=champion,
            validation_metrics=validation_metrics,
            backtest_metrics=backtest_metrics,
            calibration_metrics=calibration_metrics,
            test_metrics=test_metrics,
        )
        prediction_frames.append(
            pd.DataFrame(
                {
                    "timestamp": test_rows["timestamp"],
                    "horizon_hours": horizon,
                    "actual_surge_cm": actual_test,
                    "predicted_surge_cm": selected_test,
                    "lower_surge_cm": selected_test - test_radius,
                    "upper_surge_cm": selected_test + test_radius,
                    "tide_cm": test_rows[tide_target].to_numpy(),
                    "actual_total_cm": test_rows[f"target_total_h{horizon}"].to_numpy(),
                    "predicted_total_cm": selected_test + test_rows[tide_target].to_numpy(),
                    "champion": champion,
                }
            )
        )

    artifact_dir = settings.paths.artifacts
    artifact_dir.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {
        "project": settings.name,
        "station_code": settings.location.station_code,
        "reference_level": settings.location.reference_level,
        "allowed_years": settings.allowed_years,
        "period_start": settings.period.start.isoformat(),
        "period_end": settings.period.end.isoformat(),
        "features": features,
        "validation_start": settings.model.validation_start.isoformat(),
        "validation_window_months": settings.model.validation_window_months,
        "validation_origins": [origin.isoformat() for origin, _ in validation_windows],
        "calibration_start": settings.model.calibration_start.isoformat(),
        "test_start": settings.model.test_start.isoformat(),
        "interval_alpha": settings.model.interval_alpha,
        "models": {
            horizon: {
                "estimator": result.estimator,
                "conformal_multiplier": result.conformal_multiplier,
                "scale_feature": "surge_std_24h",
                "minimum_scale_cm": 1.0,
                "calibration_method": "monthly_robust_volatility_normalized_split_conformal",
                "champion": result.champion,
            }
            for horizon, result in trained.items()
        },
    }
    bundle_path = artifact_dir / "model_bundle.joblib"
    joblib.dump(bundle, bundle_path)
    metrics: dict[str, Any] = {
        "study": {
            "period_start": settings.period.start.isoformat(),
            "period_end": settings.period.end.isoformat(),
            "validation_origins": [origin.isoformat() for origin, _ in validation_windows],
            "calibration_start": settings.model.calibration_start.isoformat(),
            "test_start": settings.model.test_start.isoformat(),
        }
    }
    metrics.update(
        {
            str(horizon): {
                "champion": result.champion,
                "validation": result.validation_metrics,
                "rolling_origins": result.backtest_metrics,
                "calibration": result.calibration_metrics,
                "test": result.test_metrics,
            }
            for horizon, result in trained.items()
        }
    )
    (artifact_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    (artifact_dir / "signature.json").write_text(
        json.dumps(
            {
                "feature_columns": features,
                "horizons": list(settings.features.horizons),
                "target_unit": "centimetres relative to mean sea level",
                "data_scope": {
                    "start": settings.period.start.isoformat(),
                    "end": settings.period.end.isoformat(),
                    "station_code": settings.location.station_code,
                },
                "temporal_evaluation": {
                    "validation_origins": [origin.isoformat() for origin, _ in validation_windows],
                    "calibration_start": settings.model.calibration_start.isoformat(),
                    "test_start": settings.model.test_start.isoformat(),
                },
                "runtime_versions": {
                    package: version(package)
                    for package in ("joblib", "numpy", "pandas", "scikit-learn")
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    pd.concat(prediction_frames, ignore_index=True).to_parquet(
        artifact_dir / "test_predictions.parquet", index=False
    )
    _log_mlflow_run(settings, metrics, artifact_dir)
    LOGGER.info("Trained %d horizon models", len(trained))
    return bundle_path
