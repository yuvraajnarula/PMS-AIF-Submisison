import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.models import Base, NavDaily, Scheme

CATEGORIES = [
    ("Equity", "Large Cap"),
    ("Equity", "Mid Cap"),
    ("Equity", "Small Cap"),
    ("Debt", "Low Duration"),
    ("Hybrid", "Balanced Advantage"),
]


def build():
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.query(NavDaily).delete()
        session.query(Scheme).delete()
        rng = random.Random(20261118)
        start = date(2018, 1, 1)
        end = date(2026, 11, 18)
        for code in range(100001, 100101):
            index = code - 100001
            group, category = CATEGORIES[index % len(CATEGORIES)]
            plan = "direct" if index % 3 else "regular"
            option = "growth"
            amc = f"AMC {(index % 10) + 1}"
            session.add(Scheme(
                scheme_code=code,
                name=f"{amc} {category} Fund {index + 1} {plan.title()} Growth",
                amc=amc,
                category_raw=f"{group} - {category}",
                category_group=group,
                category=category,
                family_key=f"{amc.lower()} {category.lower()} fund {index + 1}",
                plan=plan,
                option=option,
                is_active=True,
            ))

            nav = 10.0
            drift = 0.00016 + (index % 7) * 0.00003
            vol = 0.0008 if group == "Debt" else 0.0018
            d = start
            while d <= end:
                if d.weekday() < 5:
                    nav *= math.exp(drift + rng.gauss(0, vol))
                    nav = round(nav, 6)
                    session.add(NavDaily(
                        scheme_code=code,
                        nav_date=d,
                        nav=nav,
                        source=2,
                    ))
                d += timedelta(days=1)
        session.flush()
        for scheme in session.query(Scheme).all():
            navs = session.query(NavDaily).filter_by(
                scheme_code=scheme.scheme_code
            ).order_by(NavDaily.nav_date)
            first = navs.first()
            last = session.query(NavDaily).filter_by(
                scheme_code=scheme.scheme_code
            ).order_by(NavDaily.nav_date.desc()).first()
            if first and last:
                scheme.first_nav_date = first.nav_date
                scheme.nav_count = navs.count()
                scheme.last_nav_date = last.nav_date
        session.commit()


if __name__ == "__main__":
    build()
    print("Built demo database with 100 schemes.")
