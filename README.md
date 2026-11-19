# Indian Mutual Fund Analytics

Backend MVP for NAV history, point-to-point returns, rolling-return distributions,
volatility, maximum drawdown, Sharpe ratio, category aggregates, and data-quality
handling.

## Track

This submission implements **Track A: Backend**. See [TRACK.md](TRACK.md) for the track
selection and scope.

## Quick start

```bash
python -m pip install .
python scripts/build_sample.py
python -m app.api.main
```

Open `http://localhost:8000/docs`. The sample database contains 100 deterministic
schemes and roughly eight years of weekday NAV observations.

For PostgreSQL and Docker:

```bash
docker compose up --build
```

Run tests:

```bash
python -m pip install '.[test]'
pytest -q
```

## API tour

- `GET /v1/health`
- `GET /v1/schemes?q=&category=&plan=&option=&limit=&offset=`
- `GET /v1/schemes/{code}`
- `GET /v1/schemes/{code}/nav?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /v1/schemes/{code}/returns?periods=1m,3m,1y,3y,5y`
- `GET /v1/schemes/{code}/rolling-returns?window=3y&step=monthly`
- `GET /v1/schemes/{code}/risk?window=3y&rf=0.055`
- `GET /v1/categories`
- `GET /v1/categories/{category}/metrics?metric=3y`

Every payload includes `methodology_version`, `as_of` where applicable, and an
informational disclaimer. Unknown schemes and malformed requests use RFC 7807
`application/problem+json`; insufficient metric history is a normal `null` result
with a machine-readable reason.

## Methodology

`METHODOLOGY_VERSION=2026.1`.

- NAV is net of the fund's recurring expenses and excludes exit load, stamp duty,
  and tax. Labelled returns are pre-tax and net of TER.
- A period is absolute for 365 calendar days or fewer and CAGR for longer periods.
- CAGR uses 365 calendar days per year and calendar days between actual NAV dates.
- The start NAV is the last observed NAV on or before the target date. Missing
  history returns `null`; a snapped start more than 45 days from the target also
  returns `null`.
- Daily return is the NAV ratio between consecutive observed NAV dates. Gaps are
  not forward-filled.
- Annualised volatility is the sample standard deviation (`ddof=1`) of observed
  NAV returns multiplied by `sqrt(252)`. At least 60 observations are required.
- MDD uses the running NAV peak and reports peak, trough, and recovery dates.
- Sharpe uses mean of daily excess NAV return divided by sample standard deviation
  of excess returns, annualised by `sqrt(252)`. Default risk-free rate is 5.5%;
  it is configurable with `rf`.
- Rolling windows report overlapping-window count, min, p25, median, mean, p75,
  max, and percentage negative. The observations are serially correlated.
- Category aggregates use equal-weighted median-like statistics for Direct Growth
  active schemes only.
- Post-tax returns (optional, `?include_tax=true&tax_regime=auto|equity|debt` on
  `/v1/schemes/{code}/returns`) apply Indian mutual fund taxation:
  equity — STCG 15% (<1yr), LTCG 10% above Rs 1 lakh exemption (>=1yr);
  debt — STCG at slab rate (<3yr), LTCG 20% (>=3yr). Assumes Rs 1 lakh invested.

## Limitations

The data pipeline is vulnerable to category drift and survivorship bias:
current live scheme lists omit merged and wound-up funds. Raw NAV strings and
`is_active` are preserved. IDCW and bonus NAV histories are not mixed into default
Growth comparisons. Direct and Regular plans are separate. No benchmark TRI,
recommendations, or personal data are implemented. Post-tax returns are available
as an optional extension on the returns endpoint.

## Ingestion

AMFI latest NAV:

```bash
python -m app.ingest.cli --source amfi --limit 100
```

The AMFI `NAVAll.txt` dump carries only the latest NAV per scheme, not full history.
For multi-year daily history (the millions of rows Track A requires), use the MFAPI path:

```bash
python -m app.ingest.cli --source mfapi --limit 100
```

MFAPI bulk history:

```bash
python -m app.ingest.cli --source mfapi --limit 100
```

The MFAPI ingestion path uses the documented `/mf` offset pagination, `/mf/{code}`
history and `/mf/{code}/latest` endpoints, scheme metadata, and `dd-mm-yyyy`
NAV dates. It retries HTTP 429/5xx responses and honours `Retry-After`.

The command is resumable at the database row level because NAVs use
`(scheme_code, nav_date)` as a key. Raw-source terms must be reviewed before
redistributing a full dataset.

## Validation

Run the hand-computed golden fixtures:

```bash
make golden
```

The fixtures cover exact 365-day CAGR, a sub-one-year absolute return, peak/trough/recovery
drawdown dates, constant-NAV volatility/Sharpe handling, and rolling-window counts. These
are implementation and convention checks, not claims about external fund factsheets.

| Fixture | Result |
|---|---|
| 365-calendar-day doubling | PASS: CAGR = 100% |
| 6-month 10% increase | PASS: absolute return = 10% |
| Peak 110, trough 80, recovery 110 | PASS: MDD = -27.2727% |
| 70 constant NAV observations | PASS: volatility = 0; Sharpe = null |
| 11-observation rolling fixture | PASS: 8 overlapping 3-day windows |

External AMC factsheet and live AMFI-vs-MFAPI reconciliation runs were not added because
the live source values were not independently available and must not be fabricated.

## Local benchmark

```bash
make benchmark
```

The benchmark rebuilds the deterministic 100-scheme SQLite sample and measures 50 requests
for each public route. Results vary with the host and should be treated as a smoke
performance check, not a production sizing result.

Measured on the local machine:

| Route | p50 | p95 |
|---|---:|---:|
| `GET /v1/health` | 4.08 ms | 5.33 ms |
| `GET /v1/schemes?limit=100` | 7.80 ms | 8.61 ms |
| `GET /v1/schemes/100001` | 3.99 ms | 5.12 ms |
| `GET /v1/schemes/100001/nav?limit=10000` | 37.94 ms | 56.81 ms |
| `GET /v1/schemes/100001/returns` | 27.79 ms | 55.86 ms |
| `GET /v1/schemes/100001/rolling-returns?window=5y&step=monthly` | 40.23 ms | 58.86 ms |
| `GET /v1/schemes/100001/risk?window=5y` | 21.86 ms | 38.23 ms |
| `GET /v1/categories` | 4.31 ms | 5.13 ms |
| `GET /v1/categories/Large%20Cap/metrics?metric=5y` | 36.92 ms | 67.87 ms |

Results vary with the host and should be treated as a smoke
performance check, not a production sizing result. The `category metrics`
and `risk` routes now compute daily returns and variance in a single SQL
query (window functions over `nav_daily`) instead of loading every scheme's
history into Python.

The NAV history query uses a compound primary key and date ordering:

```sql
CREATE TABLE nav_daily (
  scheme_code INTEGER NOT NULL,
  nav_date DATE NOT NULL,
  nav NUMERIC(18, 6) NOT NULL,
  PRIMARY KEY (scheme_code, nav_date)
);
```

For the scheme-range query, SQLite reports `SEARCH nav_daily USING PRIMARY KEY
(scheme_code=? AND nav_date>?)` and then applies the ordered limit.

### Optimization status

Done:

1. **SQL-side volatility** — `category_metrics` and `/risk` compute daily returns
   and variance in one window-function query instead of per-scheme Python loops.
2. **Connection pooling** — SQLAlchemy engine uses `pool_size`, `max_overflow`,
   `pool_pre_ping`, and `pool_recycle` for PostgreSQL deploys
   (`app/core/database.py`).

Remaining for production scale (millions of rows):

3. **Precomputed daily-returns column** — store `daily_return` on `nav_daily`
   during ingestion so volatility/Sharpe don't recompute ratios at query time.
4. **Materialized category aggregates** — a `category_daily_metrics` table
   refreshed after ingestion (per category, window, date) makes `/categories/{category}/metrics`
   an O(1) lookup regardless of scheme count.
5. **Read replicas / caching** — cache category metrics (slowest route) with a
   short TTL; route read traffic to a read replica.

## Submission package

GitHub repository — should contain:

- source code (`app/`, `scripts/`)
- tests (`tests/`)
- Docker setup (`Dockerfile`, `docker-compose.yml`)
- documentation (`README.md`, `TRACK.md`, `demo/index.html`)
- CI workflow (`.github/workflows/ci.yml`)
- generated OpenAPI spec (`openapi.json`)

Drive sample archive — should contain only:

- the deterministic SQLite database (`mf.db`)
- a short README explaining the data is synthetic (`data/sample/README.md`)

Do not publish or redistribute the upstream NAV dataset unless its source terms permit it.

To build the sample archive:

```bash
python scripts/build_sample.py
Compress-Archive -Path mf.db, data/sample/README.md -DestinationPath mf-analytics-sample.zip
```