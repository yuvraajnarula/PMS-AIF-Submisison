from app.ingest.amfi import parse_navall


def test_parse_navall_rejects_bad_nav():
    text = "Fund House\n123;INF;INF; Direct Plan - Growth;0.000000;18-Nov-2026"
    assert parse_navall(text) == []
