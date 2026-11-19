from app.metrics.tax import post_tax_return


def test_equity_stcg_15_percent():
    # 20% return in 6 months on 1 lakh = 20000 gains, STCG 15% = 3000 tax
    result = post_tax_return(0.20, 180, "equity")
    assert result.status == "ok"
    expected = (20000 - 3000) / 100000
    assert abs(result.value - expected) < 1e-12


def test_equity_ltcg_above_exemption():
    # 50% return in 2 years on 1 lakh = 50000 gains, below 1 lakh exemption = 0 tax
    result = post_tax_return(0.50, 400, "equity")
    assert result.status == "ok"
    assert abs(result.value - 0.50) < 1e-12


def test_equity_ltcg_with_exemption():
    # 200% return in 2 years on 1 lakh = 200000 gains, 100k exempt, 10% on 100k = 10000 tax
    result = post_tax_return(2.0, 400, "equity")
    assert result.status == "ok"
    expected = (200000 - 10000) / 100000
    assert abs(result.value - expected) < 1e-12


def test_debt_stcg_at_slab():
    # 20% return in 1 year on 1 lakh = 20000 gains, slab 30% = 6000 tax
    result = post_tax_return(0.20, 300, "debt", slab_rate=0.30)
    assert result.status == "ok"
    expected = (20000 - 6000) / 100000
    assert abs(result.value - expected) < 1e-12


def test_debt_ltcg_20_percent():
    # 50% return in 4 years on 1 lakh = 50000 gains, LTCG 20% = 10000 tax
    result = post_tax_return(0.50, 1500, "debt")
    assert result.status == "ok"
    expected = (50000 - 10000) / 100000
    assert abs(result.value - expected) < 1e-12


def test_invalid_scheme_type():
    result = post_tax_return(0.10, 365, "hybrid")
    assert result.status == "null"
    assert result.value is None


def test_negative_returns_no_tax():
    # -10% return means no gains, no tax
    result = post_tax_return(-0.10, 400, "equity")
    assert result.status == "ok"
    assert abs(result.value - (-0.10)) < 1e-12
