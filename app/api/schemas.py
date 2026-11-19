from datetime import date
from typing import Any

from pydantic import BaseModel

DISCLAIMER = (
    "Mutual Fund investments are subject to market risks. "
    "Read all scheme-related documents carefully. "
    "Past performance may or may not be sustained in the future. "
    "This API is informational and not investment advice."
)


class Envelope(BaseModel):
    as_of: date | None = None
    methodology_version: str
    disclaimer: str = DISCLAIMER


class HealthResponse(Envelope):
    status: str
    database: str
    latest_nav_date: date | None
    scheme_count: int


class SchemeItem(BaseModel):
    scheme_code: int
    name: str
    amc: str | None
    category: str | None
    category_group: str | None
    plan: str
    option: str
    first_nav_date: date | None
    last_nav_date: date | None
    nav_count: int
    is_active: bool


class SchemesListResponse(Envelope):
    total: int
    limit: int
    offset: int
    items: list[SchemeItem]


class SchemeDetailResponse(Envelope):
    scheme_code: int
    name: str
    amc: str | None
    category_raw: str | None
    category: str | None
    category_group: str | None
    plan: str
    option: str
    first_nav_date: date | None
    last_nav_date: date | None
    nav_count: int
    is_active: bool
    as_of: date | None


class NavItem(BaseModel):
    date: date
    nav: float


class NavResponse(Envelope):
    scheme_code: int
    total: int
    limit: int
    offset: int
    items: list[NavItem]
    as_of: date | None


class PeriodReturn(BaseModel):
    value: float | None
    status: str
    reason: str | None
    post_tax: float | None = None


class ReturnsResponse(Envelope):
    scheme_code: int
    returns: dict[str, PeriodReturn]
    as_of: date | None
    tax_regime_used: str | None = None


class RollingResponse(Envelope):
    scheme_code: int
    window: str
    summary: dict[str, Any]
    as_of: date | None


class RiskResponse(Envelope):
    scheme_code: int
    window: str
    rf: float
    volatility: dict[str, Any]
    max_drawdown: dict[str, Any]
    sharpe: dict[str, Any]
    as_of: date | None


class CategoryItem(BaseModel):
    category_group: str
    category: str
    scheme_count: int


class CategoriesResponse(Envelope):
    items: list[CategoryItem]


class CategoryMetricsResponse(Envelope):
    category: str
    metric: str
    median: float | None
    mean: float | None
    p25: float | None
    p75: float | None
    n: int
    as_of: date | None
