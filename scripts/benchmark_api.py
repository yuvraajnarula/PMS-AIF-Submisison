import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.main import app
from app.core.database import engine
from scripts.build_sample import build

build()
client = TestClient(app)
routes = [
    "/v1/health",
    "/v1/schemes?limit=100",
    "/v1/schemes/100001",
    "/v1/schemes/100001/nav?limit=10000",
    "/v1/schemes/100001/returns",
    "/v1/schemes/100001/rolling-returns?window=5y&step=monthly",
    "/v1/schemes/100001/risk?window=5y",
    "/v1/categories",
    "/v1/categories/Large%20Cap/metrics?metric=5y",
]


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return ordered[index]


print("API benchmark (local SQLite sample, 50 requests per route)")
for route in routes:
    timings = []
    for _ in range(50):
        started = time.perf_counter()
        response = client.get(route)
        elapsed = (time.perf_counter() - started) * 1000
        if response.status_code != 200:
            raise RuntimeError(f"{route}: HTTP {response.status_code}: {response.text}")
        timings.append(elapsed)
    print(
        f"- {route}: p50={percentile(timings, 0.50):.2f} ms "
        f"p95={percentile(timings, 0.95):.2f} ms"
    )

with engine.connect() as connection:
    plan = connection.execute(text(
        "EXPLAIN QUERY PLAN "
        "SELECT * FROM nav_daily "
        "WHERE scheme_code = 100001 "
        "ORDER BY nav_date "
        "LIMIT 10000"
    ))
    print("SQLite EXPLAIN QUERY PLAN:")
    for row in plan:
        print(f"- {row[3]}")
