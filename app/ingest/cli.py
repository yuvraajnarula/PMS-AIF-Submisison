import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.core.models import NavDaily, Scheme
from app.ingest.amfi import parse_navall
from app.ingest.mfapi import MFAPIClient


def load_amfi():
    response = httpx.get(
        "https://www.amfiindia.com/spages/NAVAll.txt",
        timeout=60,
        headers={"User-Agent": "mf-analytics/0.1 (educational-data-pipeline)"},
        follow_redirects=True,
    )
    response.raise_for_status()
    return parse_navall(response.text)


def refresh_scheme_metadata(db: Session, scheme_code: int):
    row = db.query(NavDaily).filter(NavDaily.scheme_code == scheme_code)
    scheme = db.get(Scheme, scheme_code)
    if scheme is None:
        return
    scheme.first_nav_date = row.with_entities(func.min(NavDaily.nav_date)).scalar()
    scheme.last_nav_date = row.with_entities(func.max(NavDaily.nav_date)).scalar()
    scheme.nav_count = row.count()


_thread_local = threading.local()


def _thread_client() -> MFAPIClient:
    client = getattr(_thread_local, "client", None)
    if client is None:
        client = MFAPIClient()
        _thread_local.client = client
    return client


def fetch_scheme_history(item):
    code = int(item["schemeCode"])
    client = _thread_client()
    meta, history = client.history(code)
    return code, item, meta, history


def main():
    parser = argparse.ArgumentParser(description="Load mutual fund NAV data")
    parser.add_argument("--source", choices=["amfi", "mfapi"], default="amfi")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="parallel workers for mfapi history fetch",
    )
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if args.source == "amfi":
            rows = load_amfi()
            for row in rows[:args.limit]:
                code = row["scheme_code"]
                scheme = db.get(Scheme, code)
                if scheme is None:
                    scheme = Scheme(scheme_code=code)
                scheme.name = row["name"]
                scheme.amc = row["amc"] or scheme.amc
                scheme.category_raw = row["category_raw"]
                scheme.plan = row["plan"]
                scheme.option = row["option"]
                scheme.is_active = True
                db.merge(scheme)
                db.merge(NavDaily(
                    scheme_code=code,
                    nav_date=row["nav_date"],
                    nav=row["nav"],
                    source=1,
                ))
                refresh_scheme_metadata(db, code)
            db.commit()
            print(f"Loaded AMFI latest NAV for up to {args.limit} schemes.")
        else:
            client = MFAPIClient()
            try:
                items = list(client.schemes_all(args.limit))
            finally:
                client.close()

            print(
                f"Fetched {len(items)} scheme list entries; fetching history with {args.workers} workers..."
            )
            results = []
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(fetch_scheme_history, item) for item in items]
                for fut in as_completed(futures):
                    results.append(fut.result())

            results.sort(key=lambda r: r[0])

            count = 0
            nav_total = 0
            for code, item, meta, history in results:
                scheme = db.get(Scheme, code)
                if scheme is None:
                    scheme = Scheme(scheme_code=code, name=item.get("schemeName", str(code)))
                scheme.name = meta.get("scheme_name", item.get("schemeName", scheme.name))
                scheme.amc = meta.get("fund_house", scheme.amc)
                scheme.category_raw = meta.get("scheme_category", scheme.category_raw)
                scheme.category_group = (
                    "Equity" if "equity" in (scheme.category_raw or "").lower()
                    else "Debt" if "debt" in (scheme.category_raw or "").lower()
                    else "Hybrid" if "hybrid" in (scheme.category_raw or "").lower()
                    else "Other"
                )
                scheme.plan = (
                    "direct"
                    if "direct" in scheme.name.lower()
                    else "regular" if "regular" in scheme.name.lower()
                    else "unknown"
                )
                scheme.option = (
                    "growth" if "growth" in scheme.name.lower() else "unknown"
                )
                scheme.is_active = True
                db.merge(scheme)

                # Idempotent re-runs: replace existing navs for this scheme.
                db.query(NavDaily).filter(NavDaily.scheme_code == code).delete()

                nav_rows = []
                for point in history:
                    try:
                        nav_date = datetime.strptime(point["date"], "%d-%m-%Y").date()
                        nav = float(point["nav"])
                    except (ValueError, KeyError, TypeError):
                        continue
                    if nav <= 0:
                        continue
                    nav_rows.append(
                        NavDaily(scheme_code=code, nav_date=nav_date, nav=nav, source=2)
                    )

                if nav_rows:
                    db.bulk_save_objects(nav_rows, return_defaults=False)
                    db.flush()
                    nav_total += len(nav_rows)

                refresh_scheme_metadata(db, code)
                count += 1
                if count % 25 == 0:
                    db.commit()
                    print(f"  ... {count}/{len(results)} schemes, {nav_total} navs")

            db.commit()
            print(f"Loaded MFAPI history for {count} schemes ({nav_total} nav observations).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
