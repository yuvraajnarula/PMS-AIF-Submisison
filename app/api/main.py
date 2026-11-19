from contextlib import asynccontextmanager
from datetime import date, timedelta
from math import sqrt
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import bindparam, func, text
from sqlalchemy.orm import Session

from app.api.schemas import (
    DISCLAIMER,
    CategoriesResponse,
    CategoryMetricsResponse,
    HealthResponse,
    NavResponse,
    ReturnsResponse,
    RiskResponse,
    RollingResponse,
    SchemeDetailResponse,
    SchemesListResponse,
)
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.models import NavDaily, Scheme
from app.metrics.conventions import METHODOLOGY_VERSION, MIN_VOL_OBSERVATIONS, TRADING_DAYS
from app.metrics.risk import max_drawdown, sharpe
from app.metrics.rolling import rolling_summary
from app.metrics.tax import post_tax_return


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Indian Mutual Fund Analytics API",
    version="0.1.0",
    description="NAV returns and risk metrics for informational use, not investment advice.",
    lifespan=lifespan,
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": "https://example.invalid/problems/" + str(exc.status_code),
            "title": exc.detail,
            "status": exc.status_code,
            "instance": str(request.url),
        },
    )


def db_session() -> Session:
    return SessionLocal()


def series(db: Session, code: int, from_date: date | None = None, to_date: date | None = None):
    query = db.query(NavDaily).filter(NavDaily.scheme_code == code)
    if from_date:
        query = query.filter(NavDaily.nav_date >= from_date)
    if to_date:
        query = query.filter(NavDaily.nav_date <= to_date)
    rows = query.order_by(NavDaily.nav_date).all()
    return [(row.nav_date, float(row.nav)) for row in rows]


def nav_at_or_before(db: Session, code: int, target: date):
    row = (
        db.query(NavDaily)
        .filter(NavDaily.scheme_code == code, NavDaily.nav_date <= target)
        .order_by(NavDaily.nav_date.desc())
        .first()
    )
    if row is None:
        return None
    return (row.nav_date, float(row.nav))


def subtract_months(d: date, months: int) -> date:
    month_index = d.year * 12 + d.month - 1 - months
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    day = min(d.day, {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}.get(month, 31))
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        day = min(d.day, 29 if leap else 28)
    return date(year, month, day)


QUERY_FROM = Query(default=None, alias="from")
QUERY_LIMIT = Query(default=100, ge=1, le=10000)
QUERY_OFFSET = Query(default=0, ge=0)


def subtract_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


@app.get("/v1/health", response_model=HealthResponse)
def health():
    db = db_session()
    try:
        latest = db.query(func.max(NavDaily.nav_date)).scalar()
        scheme_count = db.query(func.count(Scheme.scheme_code)).scalar()
        return {
            "status": "ok",
            "database": "connected",
            "latest_nav_date": latest,
            "scheme_count": scheme_count,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/schemes", response_model=SchemesListResponse)
def list_schemes(
    q: str | None = None,
    category: str | None = None,
    category_group: str | None = None,
    amc: str | None = None,
    plan: Literal["direct", "regular", "unknown"] | None = None,
    option: Literal["growth", "idcw", "bonus", "unknown"] | None = None,
    active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    db = db_session()
    try:
        query = db.query(Scheme)
        if q:
            query = query.filter(Scheme.name.ilike(f"%{q}%"))
        if category:
            query = query.filter(Scheme.category == category)
        if category_group:
            query = query.filter(Scheme.category_group == category_group)
        if amc:
            query = query.filter(Scheme.amc.ilike(f"%{amc}%"))
        if plan:
            query = query.filter(Scheme.plan == plan)
        if option:
            query = query.filter(Scheme.option == option)
        if active is not None:
            query = query.filter(Scheme.is_active == active)
        total = query.count()
        rows = query.order_by(Scheme.scheme_code).offset(offset).limit(limit).all()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "scheme_code": r.scheme_code,
                    "name": r.name,
                    "amc": r.amc,
                    "category": r.category,
                    "category_group": r.category_group,
                    "plan": r.plan,
                    "option": r.option,
                    "first_nav_date": r.first_nav_date,
                    "last_nav_date": r.last_nav_date,
                    "nav_count": r.nav_count,
                    "is_active": r.is_active,
                }
                for r in rows
            ],
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/schemes/{code}", response_model=SchemeDetailResponse)
def get_scheme(code: int):
    db = db_session()
    try:
        row = db.query(Scheme).filter(Scheme.scheme_code == code).first()
        if not row:
            raise HTTPException(404, "Scheme not found")
        return {
            "scheme_code": row.scheme_code,
            "name": row.name,
            "amc": row.amc,
            "category_raw": row.category_raw,
            "category": row.category,
            "category_group": row.category_group,
            "plan": row.plan,
            "option": row.option,
            "first_nav_date": row.first_nav_date,
            "last_nav_date": row.last_nav_date,
            "nav_count": row.nav_count,
            "is_active": row.is_active,
            "as_of": row.last_nav_date,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/schemes/{code}/nav", response_model=NavResponse)
def get_nav(
    code: int,
    from_date: date | None = QUERY_FROM,
    to: date | None = None,
    limit: int = QUERY_LIMIT,
    offset: int = QUERY_OFFSET,
):
    db = db_session()
    try:
        row = db.query(Scheme).filter(Scheme.scheme_code == code).first()
        if not row:
            raise HTTPException(404, "Scheme not found")
        query = db.query(NavDaily).filter(NavDaily.scheme_code == code)
        if from_date:
            query = query.filter(NavDaily.nav_date >= from_date)
        if to:
            query = query.filter(NavDaily.nav_date <= to)
        if from_date and to and from_date > to:
            raise HTTPException(422, "from must be on or before to")
        total = query.count()
        rows = query.order_by(NavDaily.nav_date).offset(offset).limit(limit).all()
        return {
            "scheme_code": code,
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [{"date": r.nav_date, "nav": float(r.nav)} for r in rows],
            "as_of": row.last_nav_date,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/schemes/{code}/returns", response_model=ReturnsResponse)
def get_returns(
    code: int,
    periods: str = "1m,3m,6m,ytd,1y,3y,5y,10y,si",
    as_of: date | None = None,
    include_tax: bool = False,
    tax_regime: str = "auto",
):
    db = db_session()
    try:
        row = db.query(Scheme).filter(Scheme.scheme_code == code).first()
        if not row:
            raise HTTPException(404, "Scheme not found")
        end = nav_at_or_before(db, code, as_of) if as_of else None
        if end is None:
            latest = db.query(func.max(NavDaily.nav_date)).filter(
                NavDaily.scheme_code == code
            ).scalar()
            if latest is None:
                return {
                    "scheme_code": code,
                    "returns": {},
                    "as_of": None,
                    "methodology_version": METHODOLOGY_VERSION,
                    "disclaimer": DISCLAIMER,
                }
            end_date = latest
            end = nav_at_or_before(db, code, end_date)
        else:
            end_date = as_of
        end_nav_date = end[0]
        period_set = {p.strip().lower() for p in periods.split(",")}
        unknown = period_set - {"1m","3m","6m","ytd","1y","3y","5y","10y","si"}
        if unknown:
            raise HTTPException(422, f"Unknown period(s): {', '.join(sorted(unknown))}")
        # Determine scheme type for tax computation.
        scheme_type = None
        if include_tax:
            if tax_regime in ("equity", "debt"):
                scheme_type = tax_regime
            else:
                cg = (row.category_group or "").lower()
                if "equity" in cg:
                    scheme_type = "equity"
                elif "debt" in cg:
                    scheme_type = "debt"
                elif "hybrid" in cg:
                    scheme_type = "equity"
                else:
                    scheme_type = "debt" if tax_regime == "debt" else "equity"
        results = {}
        for period in period_set:
            if period == "si":
                first = db.query(NavDaily).filter(
                    NavDaily.scheme_code == code
                ).order_by(NavDaily.nav_date.asc()).first()
                if not first:
                    results[period] = {"value": None, "status": "null", "reason": "insufficient_history"}
                    continue
                target = first.nav_date
            elif period == "ytd":
                target = date(end_nav_date.year, 1, 1)
            elif period.endswith("m"):
                target = subtract_months(end_nav_date, int(period[:-1]))
            else:
                target = subtract_years(end_nav_date, int(period[:-1]))
            start = nav_at_or_before(db, code, target)
            if not start:
                results[period] = {"value": None, "status": "null", "reason": "insufficient_history"}
                continue
            start_date, start_nav = start
            if abs((target - start_date).days) > 45:
                results[period] = {"value": None, "status": "null", "reason": "stale_start"}
                continue
            days = (end_nav_date - start_date).days
            if days <= 0:
                results[period] = {"value": None, "status": "null", "reason": "insufficient_history"}
            elif days <= 365:
                pre_tax = end[1] / start_nav - 1
                entry = {"value": pre_tax, "status": "ok", "reason": None}
                if include_tax and scheme_type:
                    pt = post_tax_return(pre_tax, days, scheme_type)
                    entry["post_tax"] = pt.value
                results[period] = entry
            else:
                pre_tax = (end[1] / start_nav) ** (365 / days) - 1
                entry = {"value": pre_tax, "status": "ok", "reason": None}
                if include_tax and scheme_type:
                    pt = post_tax_return(pre_tax, days, scheme_type)
                    entry["post_tax"] = pt.value
                results[period] = entry
        response = {
            "scheme_code": code,
            "returns": results,
            "as_of": end_nav_date,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
        if include_tax:
            response["tax_regime_used"] = scheme_type
        return response
    finally:
        db.close()


@app.get("/v1/schemes/{code}/rolling-returns", response_model=RollingResponse)
def get_rolling(code: int, window: Literal["1y","3y","5y"] = "3y",
                step: Literal["daily","monthly"] = "monthly",
                as_of: date | None = None):
    db = db_session()
    try:
        row = db.query(Scheme).filter(Scheme.scheme_code == code).first()
        if not row:
            raise HTTPException(404, "Scheme not found")
        points = series(db, code)
        if as_of:
            points = [p for p in points if p[0] <= as_of]
        window_days = {"1y":365, "3y":365*3, "5y":365*5}[window]
        result = rolling_summary(points, window_days, 1 if step == "daily" else 30)
        return {
            "scheme_code": code,
            "window": window,
            "summary": result.to_dict(),
            "as_of": points[-1][0] if points else as_of,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/schemes/{code}/risk", response_model=RiskResponse)
def get_risk(code: int, window: Literal["1y","3y","5y"] = "3y",
             rf: float = settings.default_rf,
             as_of: date | None = None):
    db = db_session()
    try:
        row = db.query(Scheme).filter(Scheme.scheme_code == code).first()
        if not row:
            raise HTTPException(404, "Scheme not found")
        days = {"1y": 365, "3y": 365 * 3, "5y": 365 * 5}[window]
        latest_q = db.query(func.max(NavDaily.nav_date)).filter(
            NavDaily.scheme_code == code
        )
        if as_of:
            latest_q = latest_q.filter(NavDaily.nav_date <= as_of)
        latest = latest_q.scalar()
        cutoff = latest - timedelta(days=days) if latest else None
        if cutoff is None:
            return {
                "scheme_code": code,
                "window": window,
                "rf": rf,
                "volatility": {"value": None, "status": "null", "reason": "insufficient_history"},
                "max_drawdown": {"value": None, "status": "null", "reason": "insufficient_history"},
                "sharpe": {"value": None, "status": "null", "reason": "insufficient_history"},
                "as_of": as_of,
                "methodology_version": METHODOLOGY_VERSION,
                "disclaimer": DISCLAIMER,
            }

        # Volatility computed in SQL via window functions (avoids loading all history into Python).
        vol_row = db.execute(
            text(
                "SELECT COUNT(*), AVG(r), AVG(r * r) "
                "FROM ("
                "  SELECT nav / lag(nav) OVER (ORDER BY nav_date) - 1.0 AS r "
                "  FROM nav_daily "
                "  WHERE scheme_code = :code AND nav_date >= :cutoff AND nav > 0"
                ") "
                "WHERE r IS NOT NULL"
            ),
            {"code": code, "cutoff": cutoff},
        ).first()
        if vol_row and vol_row[0] and vol_row[0] >= MIN_VOL_OBSERVATIONS:
            _n, mean_r, mean_r2 = vol_row
            variance = mean_r2 - mean_r * mean_r
            vol_value = sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS) if variance > 0 else 0.0
            volatility_result = {"value": vol_value, "status": "ok", "reason": None}
        else:
            volatility_result = {"value": None, "status": "null", "reason": "insufficient_observations"}

        window_rows = db.query(NavDaily).filter(
            NavDaily.scheme_code == code,
            NavDaily.nav_date >= cutoff,
        ).order_by(NavDaily.nav_date).all()
        window_points = [(r.nav_date, float(r.nav)) for r in window_rows]
        points = series(db, code)
        if as_of:
            points = [p for p in points if p[0] <= as_of]

        return {
            "scheme_code": code,
            "window": window,
            "rf": rf,
            "volatility": volatility_result,
            "max_drawdown": max_drawdown(window_points).to_dict(),
            "sharpe": sharpe(window_points, rf).to_dict(),
            "as_of": points[-1][0] if points else as_of,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/categories", response_model=CategoriesResponse)
def categories():
    db = db_session()
    try:
        rows = db.query(Scheme.category_group, Scheme.category, func.count(Scheme.scheme_code)).group_by(
            Scheme.category_group, Scheme.category
        ).all()
        return {
            "items": [
                {"category_group": group, "category": category, "scheme_count": count}
                for group, category, count in rows
            ],
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


@app.get("/v1/categories/{category}/metrics", response_model=CategoryMetricsResponse)
def category_metrics(category: str, metric: Literal["1y","3y","5y"] = "1y"):
    db = db_session()
    try:
        days_map = {"1y": 365, "3y": 365 * 3, "5y": 365 * 5}
        days = days_map[metric]
        latest = db.query(func.max(NavDaily.nav_date)).scalar()
        cutoff = latest - timedelta(days=days) if latest else None
        if cutoff is None:
            return {
                "category": category,
                "metric": "volatility_" + metric,
                "median": None,
                "mean": None,
                "p25": None,
                "p75": None,
                "n": 0,
                "as_of": None,
                "methodology_version": METHODOLOGY_VERSION,
                "disclaimer": DISCLAIMER,
            }

        scheme_codes = [
            s.scheme_code
            for s in db.query(Scheme.scheme_code).filter(
                Scheme.category == category,
                Scheme.is_active == True,
                Scheme.plan == "direct",
                Scheme.option == "growth",
            ).all()
        ]
        if not scheme_codes:
            return {
                "category": category,
                "metric": "volatility_" + metric,
                "median": None,
                "mean": None,
                "p25": None,
                "p75": None,
                "n": 0,
                "as_of": latest,
                "methodology_version": METHODOLOGY_VERSION,
                "disclaimer": DISCLAIMER,
            }

        rows = db.execute(
            text(
                "SELECT scheme_code, COUNT(*) AS n, AVG(r) AS mean_r, AVG(r * r) AS mean_r2 "
                "FROM ("
                "  SELECT scheme_code, "
                "         nav / lag(nav) OVER (PARTITION BY scheme_code ORDER BY nav_date) - 1.0 AS r "
                "  FROM nav_daily "
                "  WHERE scheme_code IN :codes AND nav_date >= :cutoff AND nav > 0"
                ") "
                "WHERE r IS NOT NULL "
                "GROUP BY scheme_code "
                "HAVING COUNT(*) >= 60"
            ).bindparams(bindparam("codes", expanding=True)),
            {"codes": tuple(scheme_codes), "cutoff": cutoff},
        ).all()

        values = []
        for _, n, mean_r, mean_r2 in rows:
            if mean_r is None or mean_r2 is None:
                continue
            variance = mean_r2 - mean_r * mean_r
            if variance <= 0:
                values.append(0.0)
            else:
                values.append(sqrt(variance) * sqrt(TRADING_DAYS))

        values.sort()
        if not values:
            return {
                "category": category,
                "metric": "volatility_" + metric,
                "median": None,
                "mean": None,
                "p25": None,
                "p75": None,
                "n": 0,
                "as_of": latest,
                "methodology_version": METHODOLOGY_VERSION,
                "disclaimer": DISCLAIMER,
            }
        n_val = len(values)
        p25 = values[(n_val - 1) // 4]
        p75 = values[(3 * (n_val - 1)) // 4]
        median = values[n_val // 2] if n_val % 2 else (values[n_val // 2 - 1] + values[n_val // 2]) / 2
        return {
            "category": category,
            "metric": "volatility_" + metric,
            "median": median,
            "mean": sum(values) / n_val,
            "p25": p25,
            "p75": p75,
            "n": n_val,
            "as_of": latest,
            "methodology_version": METHODOLOGY_VERSION,
            "disclaimer": DISCLAIMER,
        }
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8000)
