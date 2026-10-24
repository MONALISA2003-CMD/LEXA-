"""Explainable demand-forecast baseline with a rolling-origin evaluation.

This module has no database/network access and performs no business writes. It
expects the caller to prove that the complete daily history window was refreshed
before filling absent daily rows with zero. Sales-derived demand is censored by
stockouts and is not a substitute for inventory availability data.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from statistics import median
from typing import Sequence, Any

HISTORY_DAYS = 56
BACKTEST_DAYS = 14
MIN_ACTIVE_DEMAND_DAYS = 6
MIN_WEEKDAY_OBSERVATIONS = 4
FORECAST_VERSION = "phase4.weekday_seasonal_median.v1"


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("daily units must be finite non-negative decimal values") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("daily units must be finite non-negative decimal values")
    return result


def _fmt(value: Decimal | None, *, places: str = "0.001") -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal(places)), "f")


def _wape(errors: Sequence[Decimal], actuals: Sequence[Decimal]) -> Decimal | None:
    total_actual = sum(actuals, Decimal(0))
    if total_actual <= 0:
        return None
    return sum(errors, Decimal(0)) / total_actual * Decimal(100)


def _weekday_history(
    history: Sequence[Decimal],
    *,
    history_start: date,
    target_date: date,
    end_index: int,
) -> list[Decimal]:
    """Prior observations for target weekday; end_index is exclusive (no leakage)."""
    return [
        history[index]
        for index in range(max(0, end_index - HISTORY_DAYS), end_index)
        if (history_start + timedelta(days=index)).weekday() == target_date.weekday()
    ]


def _quantile_nearest_rank(values: Sequence[Decimal], q: Decimal) -> Decimal:
    ordered = sorted(values)
    index = int((Decimal(len(ordered)) * q).to_integral_value(rounding=ROUND_CEILING)) - 1
    return ordered[max(0, min(len(ordered) - 1, index))]


def seasonal_weekday_forecast(
    daily_units: Sequence[Any],
    *,
    history_start: date,
    as_of_date: date,
    horizon_days: int = 14,
) -> dict[str, Any]:
    """Forecast using the median of previous observations for the same weekday.

    A 14-day rolling-origin holdout compares this method with the last-week-same-
    weekday baseline. Returns an explicit unavailable result for sparse history;
    it never converts a missing/incomplete history window into a zero forecast.
    """
    if not 7 <= horizon_days <= 28:
        raise ValueError("horizon_days must be between 7 and 28")
    if len(daily_units) != HISTORY_DAYS:
        return {
            "status": "unavailable",
            "reason_code": "INCOMPLETE_HISTORY_WINDOW",
            "message": f"A complete {HISTORY_DAYS}-day history window is required.",
            "forecast_version": FORECAST_VERSION,
        }
    if history_start + timedelta(days=HISTORY_DAYS - 1) != as_of_date:
        raise ValueError("history_start and as_of_date must describe a consecutive 56-day window")

    history = [_decimal(value) for value in daily_units]
    active_days = sum(value > 0 for value in history)
    if active_days < MIN_ACTIVE_DEMAND_DAYS:
        return {
            "status": "unavailable",
            "reason_code": "INSUFFICIENT_DEMAND_HISTORY",
            "message": f"At least {MIN_ACTIVE_DEMAND_DAYS} days with recorded demand are required for this baseline.",
            "history_days": HISTORY_DAYS,
            "active_demand_days": active_days,
            "forecast_version": FORECAST_VERSION,
        }

    # Rolling-origin holdout: the forecast for each target sees only observations
    # strictly before it. The last-week baseline uses the previous matching weekday.
    model_errors: list[Decimal] = []
    baseline_errors: list[Decimal] = []
    test_actuals: list[Decimal] = []
    for index in range(HISTORY_DAYS - BACKTEST_DAYS, HISTORY_DAYS):
        target_date = history_start + timedelta(days=index)
        weekday_values = _weekday_history(
            history, history_start=history_start, target_date=target_date, end_index=index
        )
        if len(weekday_values) < MIN_WEEKDAY_OBSERVATIONS:
            continue
        predicted = max(Decimal(0), median(weekday_values))
        baseline = history[index - 7]
        actual = history[index]
        model_errors.append(abs(actual - predicted))
        baseline_errors.append(abs(actual - baseline))
        test_actuals.append(actual)

    if not test_actuals:
        return {
            "status": "unavailable",
            "reason_code": "BACKTEST_NOT_MEASURABLE",
            "message": "There was not enough prior weekday history to evaluate this series.",
            "history_days": HISTORY_DAYS,
            "active_demand_days": active_days,
            "forecast_version": FORECAST_VERSION,
        }

    absolute_error = sum(model_errors, Decimal(0))
    mae = absolute_error / Decimal(len(model_errors))
    model_wape = _wape(model_errors, test_actuals)
    baseline_wape = _wape(baseline_errors, test_actuals)
    comparison: str | None = None
    if model_wape is not None and baseline_wape is not None:
        if model_wape < baseline_wape:
            comparison = "BETTER_THAN_LAST_WEEK_BASELINE"
        elif model_wape > baseline_wape:
            comparison = "WORSE_THAN_LAST_WEEK_BASELINE"
        else:
            comparison = "TIED_WITH_LAST_WEEK_BASELINE"

    future: list[dict[str, str]] = []
    total = Decimal(0)
    for offset in range(1, horizon_days + 1):
        target_date = as_of_date + timedelta(days=offset)
        values = _weekday_history(
            history,
            history_start=history_start,
            target_date=target_date,
            end_index=HISTORY_DAYS,
        )
        # Eight weeks normally yield eight observations per weekday. The guard is
        # retained so future changes to history lengths cannot silently invent data.
        if len(values) < MIN_WEEKDAY_OBSERVATIONS:
            continue
        predicted = max(Decimal(0), median(values))
        low = _quantile_nearest_rank(values, Decimal("0.10"))
        high = _quantile_nearest_rank(values, Decimal("0.90"))
        low = min(low, predicted)
        high = max(high, predicted)
        total += predicted
        future.append({
            "date": target_date.isoformat(),
            "forecast_units": _fmt(predicted) or "0.000",
            "historical_same_weekday_low": _fmt(low) or "0.000",
            "historical_same_weekday_high": _fmt(high) or "0.000",
        })

    if len(future) != horizon_days:
        return {
            "status": "unavailable",
            "reason_code": "INSUFFICIENT_WEEKDAY_BASELINE",
            "message": "There were not enough matching weekdays to calculate the full requested horizon.",
            "history_days": HISTORY_DAYS,
            "active_demand_days": active_days,
            "forecast_version": FORECAST_VERSION,
        }

    return {
        "status": "available" if model_wape is not None else "partial",
        "reason_code": None if model_wape is not None else "BACKTEST_WAPE_UNAVAILABLE_NO_TEST_DEMAND",
        "history_days": HISTORY_DAYS,
        "active_demand_days": active_days,
        "horizon_days": horizon_days,
        "forecast_version": FORECAST_VERSION,
        "method": "Median recorded units for the same weekday across the previous eight weeks",
        "forecast": future,
        "total_forecast_units": _fmt(total),
        "backtest": {
            "method": "14-day rolling-origin holdout; each test day uses prior data only",
            "test_days_evaluated": len(test_actuals),
            "mae_units": _fmt(mae),
            "wape_percent": _fmt(model_wape, places="0.01"),
            "last_week_baseline_wape_percent": _fmt(baseline_wape, places="0.01"),
            "comparison_to_baseline": comparison,
            "wape_unavailable_when_test_actuals_are_zero": True,
        },
    }
