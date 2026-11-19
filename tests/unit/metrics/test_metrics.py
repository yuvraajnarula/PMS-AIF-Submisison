from datetime import date, timedelta

from app.metrics.risk import max_drawdown, sharpe, volatility


def series(values):
    start = date(2020, 1, 1)
    return [(start + timedelta(days=i), value) for i, value in enumerate(values)]


def test_strictly_increasing_nav_has_zero_drawdown():
    points = series([10, 11, 12, 13])
    result = max_drawdown(points)
    assert result.value["value"] == 0


def test_peak_trough_recovery_dates():
    points = series([100, 110, 80, 90, 110])
    result = max_drawdown(points)
    assert abs(result.value["value"] - (80 / 110 - 1)) < 1e-12
    assert result.value["peak_date"] == "2020-01-02"
    assert result.value["trough_date"] == "2020-01-03"
    assert result.value["recovery_date"] == "2020-01-05"


def test_constant_nav_has_zero_volatility_and_sharpe_null():
    points = series([100] * 70)
    vol = volatility(points)
    sharp = sharpe(points, 0.055)
    assert vol.value == 0
    assert sharp.value is None
    assert sharp.reason == "zero_volatility"


def test_volatility_needs_minimum_observations():
    points = series([100] * 59)
    assert volatility(points).reason == "insufficient_observations"
