from datetime import date
from math import sqrt

from app.metrics.conventions import TRADING_DAYS
from app.metrics.result import MetricResult


def volatility(series: list[tuple[date, float]], window_days: int | None = None) -> MetricResult:
    if window_days:
        if not series:
            return MetricResult(None, "null", "insufficient_history")
        cutoff = series[-1][0].fromordinal(series[-1][0].toordinal() - window_days)
        series = [(d, nav) for d, nav in series if d >= cutoff]
    returns = [
        curr[1] / prev[1] - 1
        for prev, curr in zip(series, series[1:])
        if prev[1] > 0
    ]
    if len(returns) < 60:
        return MetricResult(None, "null", "insufficient_observations")
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return MetricResult(sqrt(variance) * sqrt(TRADING_DAYS))


def max_drawdown(series: list[tuple[date, float]]) -> MetricResult:
    if not series:
        return MetricResult(None, "null", "insufficient_history")
    peak_nav = series[0][1]
    peak_date = series[0][0]
    trough_nav = peak_nav
    trough_date = peak_date
    mdd = 0.0
    recovered_date: date | None = None

    for nav_date, nav in series:
        if nav > peak_nav:
            peak_nav = nav
            peak_date = nav_date
        dd = nav / peak_nav - 1
        if dd < mdd:
            mdd = dd
            trough_nav = nav
            trough_date = nav_date
    for nav_date, nav in series:
        if nav_date >= trough_date and nav >= peak_nav:
            recovered_date = nav_date
            break

    return MetricResult({
        "value": mdd,
        "peak_date": peak_date.isoformat(),
        "trough_date": trough_date.isoformat(),
        "recovery_date": recovered_date.isoformat() if recovered_date else None,
    })


def sharpe(series: list[tuple[date, float]], rf: float) -> MetricResult:
    returns = [
        curr[1] / prev[1] - 1
        for prev, curr in zip(series, series[1:])
        if prev[1] > 0
    ]
    if len(returns) < 60:
        return MetricResult(None, "null", "insufficient_observations")
    rf_daily = (1 + rf) ** (1 / TRADING_DAYS) - 1
    excess = [r - rf_daily for r in returns]
    mean = sum(excess) / len(excess)
    variance = sum((r - mean) ** 2 for r in excess) / (len(excess) - 1)
    volatility = sqrt(variance) * sqrt(TRADING_DAYS)
    if volatility == 0:
        return MetricResult(None, "null", "zero_volatility")
    return MetricResult(mean / (sqrt(variance) or 1e-12) * sqrt(TRADING_DAYS))
