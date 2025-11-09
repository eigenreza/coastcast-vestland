from __future__ import annotations

import numpy as np
import pandas as pd

from coastcast.config import load_settings
from coastcast.modeling import _daily_block_bootstrap, _validation_windows


def test_expanding_validation_windows_cover_2020_through_2023() -> None:
    settings = load_settings("configs/base.yml")

    windows = _validation_windows(settings)

    assert [start.year for start, _ in windows] == [2020, 2021, 2022, 2023]
    assert windows[-1][1] == pd.Timestamp("2024-01-01T00:00:00Z")


def test_daily_block_bootstrap_is_reproducible() -> None:
    actual = np.arange(96, dtype=float)
    selected = actual + np.tile([0.0, 1.0], 48)
    persistence = actual + 2.0
    timestamps = pd.Series(pd.date_range("2025-01-01", periods=96, freq="h", tz="UTC"))

    first = _daily_block_bootstrap(
        actual,
        selected,
        persistence,
        timestamps,
        seed=42,
        repetitions=50,
    )
    second = _daily_block_bootstrap(
        actual,
        selected,
        persistence,
        timestamps,
        seed=42,
        repetitions=50,
    )

    assert first == second
    assert first["mae_daily_block_bootstrap_95_ci_cm"][0] >= 0
    assert first["mae_reduction_vs_persistence_daily_block_bootstrap_95_ci_cm"][0] > 0
