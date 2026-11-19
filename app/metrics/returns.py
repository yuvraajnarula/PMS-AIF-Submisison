from collections.abc import Iterable
from datetime import date

from app.metrics.conventions import DAYS_PER_YEAR
from app.metrics.result import MetricResult


def as_of(series: Iterable[tuple[date, float]], target: date) -> tuple[date, float] | None:
    matches = [(d, nav) for d, nav in series if d <= target]
    return max(matches, key=lambda item: item[0]) if matches else None


def point_return(
    series: Iterable[tuple[date, float]],
    end_date: date,
    period_years: float,
) -> MetricResult:
    points = sorted(series)
    end = as_of(points, end_date)
    if end is None:
        return MetricResult(None, "null", "insufficient_history")

    end_nav_date, end_nav = end
    target = end_nav_date.replace(
        year=max(1, end_nav_date.year - int(period_years))
    ) if period_years >= 1 else date(
        end_nav_date.year,
        end_nav_date.month,
        end_nav_date.day,
    )
    # Month/year periods are applied by callers through exact target dates.
    start = as_of(points, target)
    if start is None:
        return MetricResult(None, "null", "insufficient_history")
    start_date, start_nav = start
    if start_nav <= 0:
        return MetricResult(None, "null", "invalid_nav")
    days = (end_nav_date - start_date).days
    if days <= 0:
        return MetricResult(None, "null", "insufficient_history")
    absolute = end_nav / start_nav - 1
    if days <= DAYS_PER_YEAR:
        return MetricResult(absolute)
    value = (end_nav / start_nav) ** (DAYS_PER_YEAR / days) - 1
    return MetricResult(value)
