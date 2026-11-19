from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Scheme(Base):
    __tablename__ = "scheme"

    scheme_code: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    amc: Mapped[str | None] = mapped_column(Text)
    category_raw: Mapped[str | None] = mapped_column(Text)
    category_group: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    family_key: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(String(16), default="unknown")
    option: Mapped[str] = mapped_column(String(16), default="unknown")
    first_nav_date: Mapped[date | None] = mapped_column(Date)
    last_nav_date: Mapped[date | None] = mapped_column(Date)
    nav_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    navs: Mapped[list["NavDaily"]] = relationship(back_populates="scheme")


class NavDaily(Base):
    __tablename__ = "nav_daily"
    __table_args__ = (UniqueConstraint("scheme_code", "nav_date"),)

    scheme_code: Mapped[int] = mapped_column(
        ForeignKey("scheme.scheme_code"), primary_key=True, index=True
    )
    nav_date: Mapped[date] = mapped_column(Date, primary_key=True, index=True)
    nav: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source: Mapped[int] = mapped_column(Integer, default=2)

    scheme: Mapped[Scheme] = relationship(back_populates="navs")
