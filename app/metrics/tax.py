from app.metrics.result import MetricResult

# Indian mutual fund taxation (simplified, for illustration only)
# Equity: STCG 15% (<1yr), LTCG 10% above Rs 1 lakh exemption (>=1yr)
# Debt:   STCG at slab rate (<3yr), LTCG 20% (>=3yr)
EQUITY_STCG_RATE = 0.15
EQUITY_LTCG_RATE = 0.10
EQUITY_LTCG_EXEMPTION = 100000.0
DEBT_LTCG_RATE = 0.20
DEBT_STCG_SLAB_RATE = 0.30

EQUITY_HOLDING_DAYS = 365
DEBT_HOLDING_DAYS = 3 * 365


def post_tax_return(
    absolute_return: float,
    holding_days: int,
    scheme_type: str,
    investment_amount: float = 100000.0,
    slab_rate: float = DEBT_STCG_SLAB_RATE,
) -> MetricResult:
    """Calculate post-tax return for Indian mutual funds.

    scheme_type: "equity" or "debt"
    investment_amount: assumed invested amount (default Rs 1 lakh)
    slab_rate: applicable income tax slab for debt STCG
    """
    if scheme_type not in ("equity", "debt"):
        return MetricResult(None, "null", "invalid_scheme_type")
    if investment_amount <= 0:
        return MetricResult(None, "null", "invalid_investment_amount")
    if holding_days <= 0:
        return MetricResult(None, "null", "invalid_holding_period")

    gains = absolute_return * investment_amount

    if scheme_type == "equity":
        if holding_days < EQUITY_HOLDING_DAYS:
            tax = gains * EQUITY_STCG_RATE
        else:
            taxable_gains = max(gains - EQUITY_LTCG_EXEMPTION, 0.0)
            tax = taxable_gains * EQUITY_LTCG_RATE
    else:
        if holding_days < DEBT_HOLDING_DAYS:
            tax = gains * slab_rate
        else:
            tax = gains * DEBT_LTCG_RATE

    post_tax_gains = gains - tax
    post_tax_value = post_tax_gains / investment_amount
    return MetricResult(post_tax_value, "ok", None)
