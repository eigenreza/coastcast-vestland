"""Data contracts that fail fast before modeling."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class DataContractError(ValueError):
    """Raised when a source or analytical table violates its contract."""


@dataclass(frozen=True)
class RangeRule:
    column: str
    minimum: float
    maximum: float


def validate_timestamp_contract(
    frame: pd.DataFrame,
    allowed_years: tuple[int, ...],
    unique_by: list[str],
) -> None:
    if frame.empty:
        raise DataContractError("Dataset is empty")
    if "timestamp" not in frame:
        raise DataContractError("Dataset has no timestamp column")
    timestamps = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    if timestamps.isna().any():
        raise DataContractError("Dataset contains invalid timestamps")
    unexpected = sorted(set(timestamps.dt.year) - set(allowed_years))
    if unexpected:
        raise DataContractError(f"Dataset includes disallowed years: {unexpected}")
    if frame.duplicated(unique_by).any():
        count = int(frame.duplicated(unique_by).sum())
        raise DataContractError(f"Dataset contains {count} duplicate keys for {unique_by}")


def validate_ranges(frame: pd.DataFrame, rules: list[RangeRule]) -> None:
    violations: list[str] = []
    for rule in rules:
        if rule.column not in frame:
            violations.append(f"missing column {rule.column}")
            continue
        values = pd.to_numeric(frame[rule.column], errors="coerce").dropna()
        invalid = values[~values.between(rule.minimum, rule.maximum)]
        if not invalid.empty:
            violations.append(
                f"{rule.column}: {len(invalid)} values outside [{rule.minimum}, {rule.maximum}]"
            )
    if violations:
        raise DataContractError("; ".join(violations))


def validate_missingness(frame: pd.DataFrame, columns: list[str], maximum_fraction: float) -> None:
    excessive = {
        column: float(frame[column].isna().mean())
        for column in columns
        if column not in frame or frame[column].isna().mean() > maximum_fraction
    }
    if excessive:
        detail = ", ".join(f"{column}={fraction:.1%}" for column, fraction in excessive.items())
        raise DataContractError(f"Missingness exceeds contract: {detail}")
