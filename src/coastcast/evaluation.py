"""Generate a concise, reproducible model evaluation report."""

from __future__ import annotations

import json
from pathlib import Path

from coastcast.config import Settings


def generate_evaluation_report(settings: Settings) -> Path:
    metrics_path = settings.paths.artifacts / "metrics.json"
    if not metrics_path.exists():
        raise FileNotFoundError("Model metrics do not exist. Train the models first.")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    lines = [
        "# Model evaluation",
        "",
        "Expanding-window validation begins on "
        + settings.model.validation_start.date().isoformat()
        + f" in {settings.model.validation_window_months}-month steps.",
        "The independent uncertainty-calibration period begins on "
        + settings.model.calibration_start.date().isoformat()
        + ".",
        "The final test period begins on " + settings.model.test_start.date().isoformat() + ".",
        "The test period is not used for fitting, uncertainty calibration, or champion selection.",
        "",
        "| Horizon | Champion | Test MAE | Daily-block 95% CI | Persistence MAE | MAE reduction 95% CI | RMSE | Coverage |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for horizon in settings.features.horizons:
        result = metrics[str(horizon)]
        test = result["test"]
        interval = test["mae_daily_block_bootstrap_95_ci_cm"]
        improvement = test["mae_reduction_vs_persistence_daily_block_bootstrap_95_ci_cm"]
        lines.append(
            f"| {horizon} h | {result['champion'].replace('_', ' ')} | "
            f"{test['mae_cm']:.2f} cm | {interval[0]:.2f}-{interval[1]:.2f} cm | "
            f"{test['persistence_mae_cm']:.2f} cm | "
            f"{improvement[0]:.2f}-{improvement[1]:.2f} cm | "
            f"{test['rmse_cm']:.2f} cm | {test['interval_coverage']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "A learned model is deployed only when it beats persistence on the validation period.",
            "This rule prevents additional model complexity from being rewarded without evidence.",
            "Coverage should be interpreted alongside interval width and event-specific errors.",
            "",
            "## Acceptance checks",
            "",
            "- Every deployed champion has passed an out-of-time selection step.",
            "- The untouched test period reports both champion and persistence error.",
            "- The prediction interval target is 90 percent marginal coverage.",
            "- Daily-block bootstrap intervals preserve within-day dependence in test errors.",
            "- All analytical observations are restricted to the configured study window.",
            "",
        ]
    )
    output = settings.paths.reports / "model_evaluation.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    return output
