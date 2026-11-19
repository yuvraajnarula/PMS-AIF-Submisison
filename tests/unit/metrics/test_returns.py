from datetime import date

from app.metrics.returns import as_of


def test_as_of_uses_last_nav_on_or_before_target():
    points = [
        (date(2024, 1, 1), 10),
        (date(2024, 1, 3), 11),
        (date(2024, 1, 5), 12),
    ]
    assert as_of(points, date(2024, 1, 4)) == (date(2024, 1, 3), 11)
