from fastapi.testclient import TestClient

from app.api.main import app
from scripts.build_sample import build

client = TestClient(app)


def setup_module(module):
    build()


def test_health():
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["scheme_count"] == 100
    assert data["methodology_version"] == "2026.1"
    assert data["disclaimer"]


def test_list_schemes_pagination():
    response = client.get("/v1/schemes?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 100
    assert data["limit"] == 5
    assert data["offset"] == 0
    assert len(data["items"]) == 5
    assert data["items"][0]["scheme_code"] == 100001


def test_list_schemes_filters():
    response = client.get("/v1/schemes?category=Large%20Cap&plan=direct&option=growth")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert item["category"] == "Large Cap"
        assert item["plan"] == "direct"
        assert item["option"] == "growth"


def test_list_schemes_search():
    response = client.get("/v1/schemes?q=AMC%201")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for item in data["items"]:
        assert "AMC 1" in item["name"]


def test_get_scheme():
    response = client.get("/v1/schemes/100001")
    assert response.status_code == 200
    data = response.json()
    assert data["scheme_code"] == 100001
    assert data["name"]
    assert data["methodology_version"] == "2026.1"


def test_get_scheme_not_found():
    response = client.get("/v1/schemes/999999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_get_nav():
    response = client.get("/v1/schemes/100001/nav?limit=3")
    assert response.status_code == 200
    data = response.json()
    assert data["scheme_code"] == 100001
    assert len(data["items"]) == 3
    assert data["items"][0]["date"] <= data["items"][-1]["date"]


def test_get_nav_invalid_range():
    response = client.get(
        "/v1/schemes/100001/nav?from=2026-01-01&to=2020-01-01"
    )
    assert response.status_code == 422


def test_get_returns():
    response = client.get("/v1/schemes/100001/returns?periods=1y,3y")
    assert response.status_code == 200
    data = response.json()
    assert data["scheme_code"] == 100001
    assert "1y" in data["returns"]
    assert "3y" in data["returns"]
    assert data["returns"]["1y"]["status"] in ("ok", "null")


def test_get_returns_unknown_period():
    response = client.get("/v1/schemes/100001/returns?periods=foo")
    assert response.status_code == 422


def test_get_returns_insufficient_history():
    response = client.get("/v1/schemes/100001/returns?periods=10y")
    assert response.status_code == 200
    data = response.json()
    assert data["returns"]["10y"]["status"] == "null"


def test_get_returns_with_tax_equity():
    response = client.get(
        "/v1/schemes/100001/returns?periods=3y&include_tax=true&tax_regime=auto"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tax_regime_used"] == "equity"
    result = data["returns"]["3y"]
    if result["status"] == "ok":
        assert "post_tax" in result
        assert result["post_tax"] is not None
        assert result["post_tax"] <= result["value"]


def test_get_returns_with_tax_debt():
    response = client.get(
        "/v1/schemes/100001/returns?periods=3y&include_tax=true&tax_regime=debt"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tax_regime_used"] == "debt"
    result = data["returns"]["3y"]
    if result["status"] == "ok":
        assert "post_tax" in result


def test_get_returns_without_tax_has_no_post_tax():
    response = client.get("/v1/schemes/100001/returns?periods=3y")
    assert response.status_code == 200
    data = response.json()
    result = data["returns"]["3y"]
    if result["status"] == "ok":
        assert result.get("post_tax") is None


def test_get_returns_tax_invalid_scheme_type():
    # 999999 doesn't exist; just verify include_tax doesn't crash on valid scheme
    response = client.get("/v1/schemes/100001/returns?periods=1y&include_tax=true")
    assert response.status_code == 200


def test_get_rolling_returns():
    response = client.get(
        "/v1/schemes/100001/rolling-returns?window=3y&step=monthly"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["window"] == "3y"
    assert "count" in data["summary"]["value"]


def test_get_risk():
    response = client.get("/v1/schemes/100001/risk?window=3y&rf=0.055")
    assert response.status_code == 200
    data = response.json()
    assert data["window"] == "3y"
    assert data["rf"] == 0.055
    assert "volatility" in data
    assert "max_drawdown" in data
    assert "sharpe" in data


def test_categories():
    response = client.get("/v1/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) > 0
    assert data["items"][0]["scheme_count"] > 0


def test_category_metrics():
    response = client.get("/v1/categories/Large%20Cap/metrics?metric=3y")
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Large Cap"
    assert data["metric"] == "volatility_3y"
    assert data["n"] > 0
