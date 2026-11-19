import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import date, timedelta

from app.metrics.returns import as_of, point_return
from app.metrics.risk import max_drawdown, sharpe, volatility
from app.metrics.rolling import rolling_summary


def dated(values, start=date(2020, 1, 1)):
    return [(start + timedelta(days=index), nav) for index, nav in enumerate(values)]


cases = []

# Exact 365-calendar-day doubling.
series = [(date(2021, 1, 1), 10.0), (date(2022, 1, 1), 20.0)]
return_result = point_return(series, date(2022, 1, 1), 1)
cases.append(("365-day doubling", "CAGR", return_result.value, 1.0, 1e-12))

# Six months at 10% must remain absolute, not annualised.
series = [(date(2024, 1, 1), 100.0), (date(2024, 7, 1), 110.0)]
start = as_of(series, date(2024, 1, 1))
end = as_of(series, date(2024, 7, 1))
assert start and end
absolute = end[1] / start[1] - 1
cases.append(("6-month increase", "Absolute return", absolute, 0.10, 1e-12))

# Known peak, trough, and recovery.
series = dated([100, 110, 80, 90, 110])
mdd = max_drawdown(series)
cases.append(("Peak/trough/recovery", "MDD", mdd.value["value"], 80 / 110 - 1, 1e-12))

# Constant NAV: zero volatility and null Sharpe.
constant = dated([100] * 70)
constant_vol = volatility(constant)
constant_sharpe = sharpe(constant, 0.055)
cases.append(("Constant NAV", "Volatility", constant_vol.value, 0.0, 1e-12))
cases.append(("Constant NAV", "Sharpe", constant_sharpe.value, None, 0.0))

# Rolling window is a distribution rather than a single average.
rolling_series = dated([100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120])
rolling = rolling_summary(rolling_series, window_days=3, step_days=1)
cases.append(("3-day rolling fixture", "Rolling count", rolling.value["count"], 8, 0))


def close(actual, expected, tolerance):
    if expected is None:
        return actual is None
    return actual is not None and abs(actual - expected) <= tolerance


failed = False
print("Golden validation")
for name, metric, actual, expected, tolerance in cases:
    passed = close(actual, expected, tolerance)
    failed |= not passed
    print(f"- {name}: {metric} actual={actual!r}, expected={expected!r}, {'PASS' if passed else 'FAIL'}")

if failed:
    raise SystemExit(1)
