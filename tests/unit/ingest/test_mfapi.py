from datetime import date

from app.ingest.mfapi import MFAPIClient


def test_history_accepts_live_documented_shape(monkeypatch):
    client = MFAPIClient()

    def fake_get_json(url, params=None):
        assert url == "https://api.mfapi.in/mf/125497"
        assert params == {
            "startDate": "2023-01-01",
            "endDate": "2023-12-31",
        }
        return {
            "meta": {
                "scheme_code": 125497,
                "scheme_name": "SBI SMALL CAP FUND - Direct Plan - Growth",
            },
            "data": [{"date": "29-12-2023", "nav": "161.23570"}],
            "status": "SUCCESS",
        }

    monkeypatch.setattr(client, "_get_json", fake_get_json)
    meta, data = client.history(
        125497,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )
    assert meta["scheme_code"] == 125497
    assert data == [{"date": "29-12-2023", "nav": "161.23570"}]
    client.close()
