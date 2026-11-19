# Track Selection

## Track A: Backend — Selected

We chose **Track A: Backend**.

### Scope

Load the full daily NAV history of every mutual fund scheme into a database (running into millions of rows), and build a documented REST API that returns, for any scheme or category, returns over standard periods, rolling returns, volatility, maximum drawdown, and Sharpe ratio. It supports filtering and pagination, copes with rate limits, missing dates, and bad data from the source, and includes tests and a README.

### Implementation

- **Language/framework:** Python 3.12, FastAPI, SQLAlchemy
- **Databases:** SQLite (local deterministic sample), PostgreSQL (Docker Compose)
- **Data sources:** AMFI latest NAV; MFAPI bulk history (`/mf`, `/mf/{code}`, `/mf/{code}/latest`) with retry on HTTP 429/5xx and `Retry-After` honouring
- **Metrics:** point-to-point and CAGR returns, rolling-return distributions, volatility (sample std dev `ddof=1`, annualised by `sqrt(252)`, min 60 observations), maximum drawdown with peak/trough/recovery dates, Sharpe ratio (default risk-free rate 5.5%, configurable via `rf`)
- **API routes:** `GET /v1/health`, `/v1/schemes` (filter + pagination), `/v1/schemes/{code}`, `/v1/schemes/{code}/nav`, `/v1/schemes/{code}/returns`, `/v1/schemes/{code}/rolling-returns`, `/v1/schemes/{code}/risk`, `/v1/categories`, `/v1/categories/{category}/metrics`
- **Error handling:** RFC 7807 `application/problem+json`; insufficient metric history is a normal `null` with a machine-readable reason
- **Testing:** unit tests for ingestion parsing and metrics, golden fixtures (`make golden`), GitHub Actions CI on push/PR
- **Documentation:** exported `openapi.json`, methodology, limitations, ingestion guide, local benchmark

### Status

Complete. See README.md for quick start, API tour, methodology, validation, and the local benchmark.

## Track B: Frontend — Not Selected

Track B would build and deploy a fund screener and comparison app: a quick sorted/filtered table of thousands of schemes, side-by-side comparison of up to four funds with return and drawdown charts, and clear loading/empty/error states. Not implemented in this submission.

## Submission

Add your GitHub repo link, and the live link if you chose Track B, to your submission folder. In the interview, you'll extend your own code live.

Deadline: Friday, 20 November 2026, 11:59 pm IST.
