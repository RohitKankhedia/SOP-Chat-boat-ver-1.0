"""
portfolio_risk_agent.py
-----------------------
Scores every customer in the loan portfolio on churn risk
after a Fed rate change.

Churn risk is calculated from 5 factors:
  1. Rate gap vs best competitor (bigger gap = higher risk)
  2. Loan balance (higher balance = more incentive to refinance)
  3. Months remaining (more months left = more savings possible)
  4. FICO score (better credit = more options elsewhere)
  5. Missed payments (delinquent customers can't easily refinance)

Returns a DataFrame with ChurnRiskScore (0-100) and RiskCategory.
"""

import pandas as pd
import os

PORTFOLIO_FILE    = os.path.join("data", "loan_portfolio.csv")
COMPETITOR_FILE   = os.path.join("data", "competitor_rates.csv")

# How much each factor contributes to the total score (must sum to 100)
WEIGHTS = {
    "rate_gap":         35,   # biggest driver
    "balance":          25,   # high balance = big savings from refinancing
    "months_remaining": 20,   # more time left = more benefit
    "fico":             15,   # better credit = more refi options
    "payment_history":   5,   # missed payments reduce refi ability
}


def load_data():
    portfolio   = pd.read_csv(PORTFOLIO_FILE)
    competitors = pd.read_csv(COMPETITOR_FILE)
    return portfolio, competitors


def get_best_competitor_rate(competitors: pd.DataFrame, product: str, tier: str) -> float:
    """Returns the lowest competitor rate for a given product + tier."""
    mask = (competitors["Product"] == product) & (competitors["CreditTier"] == tier)
    subset = competitors[mask]
    if subset.empty:
        return None
    return subset["CompetitorRate"].min()


def score_portfolio(rate_change_bps: float = 25) -> pd.DataFrame:
    """
    Main function. Takes the Fed rate change in basis points (e.g. 25 for +0.25%).
    Returns the full portfolio DataFrame with churn scores added.
    """
    portfolio, competitors = load_data()

    rate_change_pct = rate_change_bps / 100.0

    # Apply rate change to current customer rates
    # Business Banking = floating (moves with Fed immediately)
    # Auto loans = fixed (existing loans unchanged)
    # For rate cuts: competitor rates also drop proportionally
    portfolio["NewRate"] = portfolio.apply(
        lambda r: round(max(r["CurrentRate"] + rate_change_pct, 1.0), 2)
        if r["Product"] == "Business Banking"
        else r["CurrentRate"],
        axis=1
    )

    # For rate cuts, competitors also drop — reduce their rates too
    if rate_change_bps < 0:
        competitors = competitors.copy()
        competitors["CompetitorRate"] = (
            competitors["CompetitorRate"] + rate_change_pct
        ).clip(lower=1.0).round(2)

    scores = []

    for _, row in portfolio.iterrows():
        best_comp = get_best_competitor_rate(
            competitors, row["Product"], row["CreditTier"]
        )
        if best_comp is None:
            best_comp = row["NewRate"] - 0.25  # fallback: assume competitor is 0.25% lower

        # ── Factor 1: Rate Gap ───────────────────────────────────────
        # How much cheaper is the best competitor?
        gap = row["NewRate"] - best_comp
        # Gap of 0.5% or more = very high risk; negative gap = low risk
        gap_score = min(max(gap / 0.75 * 100, 0), 100)

        # ── Factor 2: Loan Balance ───────────────────────────────────
        # Normalise: $0 = 0 score, $500K+ = 100 score
        balance_score = min(row["LoanBalance"] / 500_000 * 100, 100)

        # ── Factor 3: Months Remaining ───────────────────────────────
        # More months left = more potential savings from refinancing
        months_score = min(row["MonthsRemaining"] / 72 * 100, 100)

        # ── Factor 4: FICO Score ─────────────────────────────────────
        # Better FICO = easier to get approved elsewhere
        # Scale 550-850 → 0-100
        fico_score = min(max((row["FICO"] - 550) / 300 * 100, 0), 100)

        # ── Factor 5: Payment History ────────────────────────────────
        # Missed payments REDUCE churn risk (can't refinance if delinquent)
        # 0 missed = 100 (fully able to refi), 2+ missed = 0
        payment_score = max(100 - row["MissedPayments"] * 50, 0)

        # ── Weighted total ───────────────────────────────────────────
        total = (
            gap_score         * WEIGHTS["rate_gap"]         / 100 +
            balance_score     * WEIGHTS["balance"]          / 100 +
            months_score      * WEIGHTS["months_remaining"] / 100 +
            fico_score        * WEIGHTS["fico"]             / 100 +
            payment_score     * WEIGHTS["payment_history"]  / 100
        )

        scores.append({
            "ChurnRiskScore":   round(total, 1),
            "BestCompRate":     best_comp,
            "RateGap":          round(row["NewRate"] - best_comp, 2),
            "GapScore":         round(gap_score, 1),
            "BalanceScore":     round(balance_score, 1),
            "MonthsScore":      round(months_score, 1),
            "FicoScore":        round(fico_score, 1),
            "PaymentScore":     round(payment_score, 1),
        })

    score_df = pd.DataFrame(scores)
    portfolio = pd.concat([portfolio.reset_index(drop=True), score_df], axis=1)

    # ── Risk category ─────────────────────────────────────────────────
    def categorise(score):
        if score >= 70: return "🔴 High Risk"
        if score >= 45: return "🟡 Medium Risk"
        return "🟢 Low Risk"

    portfolio["RiskCategory"] = portfolio["ChurnRiskScore"].apply(categorise)

    # Sort by churn risk descending
    portfolio = portfolio.sort_values("ChurnRiskScore", ascending=False).reset_index(drop=True)

    return portfolio


def get_summary(portfolio: pd.DataFrame) -> dict:
    """Returns a summary dict for the dashboard."""
    total      = len(portfolio)
    high_risk  = len(portfolio[portfolio["RiskCategory"] == "🔴 High Risk"])
    mid_risk   = len(portfolio[portfolio["RiskCategory"] == "🟡 Medium Risk"])
    low_risk   = len(portfolio[portfolio["RiskCategory"] == "🟢 Low Risk"])

    at_risk_balance = portfolio[
        portfolio["RiskCategory"].isin(["🔴 High Risk", "🟡 Medium Risk"])
    ]["LoanBalance"].sum()

    high_risk_balance = portfolio[
        portfolio["RiskCategory"] == "🔴 High Risk"
    ]["LoanBalance"].sum()

    return {
        "total_customers":    total,
        "high_risk":          high_risk,
        "medium_risk":        mid_risk,
        "low_risk":           low_risk,
        "at_risk_balance":    round(at_risk_balance, 2),
        "high_risk_balance":  round(high_risk_balance, 2),
        "estimated_loss":     round(high_risk_balance * 0.40, 2),  # assume 40% of high-risk actually leave
        "recoverable":        round(high_risk_balance * 0.40 * 0.50, 2),  # retain 50% with intervention
    }
