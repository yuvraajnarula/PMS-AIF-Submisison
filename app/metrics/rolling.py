from datetime import date, timedelta
from statistics import median

from app.metrics.result import MetricResult
from app.metrics.returns import as_of


def rolling_summary(
    series: list[tuple[date, float]],
    window_days: int,
    step_days: int = 30,
) -> MetricResult:
    if len(series) < 2:
        return MetricResult(None, "null", "insufficient_history")
    values: list[float] = []
    first = series[0][0]
    last = series[-1][0]
    end = first + timedelta(days=window_days)
    while end <= last:
        end_nav = as_of(series, end)
        start_nav = as_of(series, end - timedelta(days=window_days))
        if end_nav and start_nav and start_nav[1] > 0:
            r = end_nav[1] / start_nav[1] - 1
            if window_days > 365:
                days = (end_nav[0] - start_nav[0]).days
                r = (1 + r) ** (365 / days) - 1 if days > 0 else r
            values.append(r)
        end += timedelta(days=step_days)
    if not values:
        return MetricResult(None, "null", "insufficient_history")
    values.sort()
    count = len(values)
    q25 = values[max(0, (count - 1) // 4)]
    q75 = values[min(count - 1, (3 * (count - 1)) // 4)]
    return MetricResult({
        "count": count,
        "min": values[0],
        "p25": q25,
        "median": median(values),
        "mean": sum(values) / count,
        "p75": q75,
        "max": values[-1],
        "pct_negative": sum(v < 0 for v in values) / count,
    })
