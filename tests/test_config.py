from __future__ import annotations

from coastcast.config import load_settings


def test_base_config_covers_the_full_ifs_archive() -> None:
    settings = load_settings("configs/base.yml")
    assert settings.allowed_years == tuple(range(2017, 2026))
    assert settings.period.start.year == 2017
    assert settings.period.end.year == 2025
    assert settings.location.station_code == "BGO"


def test_model_splits_are_strictly_ordered() -> None:
    settings = load_settings("configs/base.yml")
    assert settings.period.start < settings.model.validation_start
    assert settings.model.validation_start < settings.model.calibration_start
    assert settings.model.calibration_start < settings.model.test_start
    assert settings.model.test_start <= settings.period.end
