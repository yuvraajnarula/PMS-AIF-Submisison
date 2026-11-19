import time
from collections.abc import Iterable
from datetime import date

import httpx


class MFAPIClient:
    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "mf-analytics/0.1 (educational-data-pipeline)"},
        )
        self.max_retries = max_retries

    def close(self):
        self.client.close()

    def _get_json(self, url: str, params: dict | None = None) -> object:
        for attempt in range(self.max_retries + 1):
            response = self.client.get(url, params=params)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("MFAPI request retries exhausted")

    def schemes(self, limit: int = 100, offset: int = 0) -> list[dict]:
        payload = self._get_json(
            "https://api.mfapi.in/mf",
            params={"limit": limit, "offset": offset},
        )
        return payload if isinstance(payload, list) else []

    def schemes_all(self, limit: int, page_size: int = 100) -> Iterable[dict]:
        offset = 0
        yielded = 0
        while yielded < limit:
            page_limit = min(page_size, limit - yielded)
            page = self.schemes(limit=page_limit, offset=offset)
            if not page:
                break
            for item in page:
                yield item
                yielded += 1
                if yielded >= limit:
                    break
            if len(page) < page_limit:
                break
            offset += page_limit

    def search(self, query: str) -> list[dict]:
        payload = self._get_json(
            "https://api.mfapi.in/mf/search",
            params={"q": query},
        )
        return payload if isinstance(payload, list) else []

    def latest(self, scheme_code: int) -> dict:
        payload = self._get_json(f"https://api.mfapi.in/mf/{scheme_code}/latest")
        return payload if isinstance(payload, dict) else {}

    def history(
        self,
        scheme_code: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[dict, list[dict]]:
        params = {}
        if start_date:
            params["startDate"] = start_date.isoformat()
        if end_date:
            params["endDate"] = end_date.isoformat()
        payload = self._get_json(
            f"https://api.mfapi.in/mf/{scheme_code}",
            params=params or None,
        )
        if not isinstance(payload, dict):
            return {}, []
        meta = payload.get("meta", {})
        data = payload.get("data", [])
        if payload.get("status") != "SUCCESS" or not isinstance(data, list):
            return meta if isinstance(meta, dict) else {}, []
        return meta if isinstance(meta, dict) else {}, data
