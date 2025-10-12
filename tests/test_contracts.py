from __future__ import annotations

import pandas as pd
import pytest

from coastcast.data.contracts import (
    DataContractError,
    RangeRule,
    validate_ranges,
    validate_timestamp_contract,
)


def test_contract_rejects_a_record_outside_the_study_window() -> None:
    frame = pd.DataFrame({"timestamp": ["2017-01-01T00:00:00Z", "2026-01-01T00:00:00Z"]})
    with pytest.raises(DataContractError, match="disallowed years"):
        validate_timestamp_contract(frame, tuple(range(2017, 2026)), ["timestamp"])


def test_range_contract_reports_physical_violation() -> None:
    frame = pd.DataFrame({"pressure_msl": [1002.0, 1400.0]})
    with pytest.raises(DataContractError, match="pressure_msl"):
        validate_ranges(frame, [RangeRule("pressure_msl", 850.0, 1100.0)])
