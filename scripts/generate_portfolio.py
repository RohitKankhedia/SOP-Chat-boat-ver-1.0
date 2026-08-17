"""
generate_portfolio.py
---------------------
Generates two CSV files:
  data/loan_portfolio.csv     — 500 synthetic customer loan records
  data/competitor_rates.csv   — competitor rate table (3 banks)

Usage:
    python scripts/generate_portfolio.py
"""

import csv
import random
import os
from datetime import datetime, timedelta

random.seed(42)
os.makedirs("data", exist_ok=True)

# ── Helper ─────────────────────────────────────────────────────────────
def rand_date(start_months_ago, end_months_ago):
    a = min(start_months_ago, end_months_ago) * 30
    b = max(start_months_ago, end_months_ago) * 30
    if a == b:
        b += 1
    days = random.randint(a, b)
    return (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")

FIRST_NAMES = ["James","Maria","David","Linda","Robert","Patricia","Michael","Barbara",
               "William","Jennifer","Richard","Susan","Joseph","Jessica","Thomas","Sarah",
               "Charles","Karen","Christopher","Lisa","Priya","Raj","Aisha","Mohammed",
               "Chen","Wei","Ana","Carlos","Fatima","Ivan","Yuki","Omar","Sofia","Luca"]

LAST_NAMES  = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
               "Martinez","Wilson","Anderson","Taylor","Thomas","Hernandez","Moore",
               "Patel","Nguyen","Kim","Chen","Singh","Sharma","Ali","Lopez","Scott",
               "Green","Adams","Baker","Nelson","Carter","Mitchell","Perez","Roberts"]

STATES = ["CA","TX","FL","NY","IL","PA","OH","GA","NC","MI","NJ","VA","WA","AZ","MA",
          "TN","IN","MO","MD","WI","CO","MN","SC","AL","LA","KY","OR","OK","CT","IA"]

def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

# ── Rate tables (bank's current rates post-change) ─────────────────────
BANK_RATES = {
    # (product, credit_tier): rate %
    ("Indirect Auto", "Tier 1 - Super Prime"):  5.99,
    ("Indirect Auto", "Tier 2 - Prime"):         6.74,
    ("Indirect Auto", "Tier 3 - Near Prime"):    8.99,
    ("Indirect Auto", "Tier 4 - Sub Prime"):    11.49,
    ("Indirect Auto", "Tier 5 - Deep Sub"):     14.99,
    ("Direct Auto",   "Tier 1 - Excellent"):     5.49,
    ("Direct Auto",   "Tier 2 - Good"):          6.24,
    ("Direct Auto",   "Tier 3 - Fair"):          8.74,
    ("Direct Auto",   "Tier 4 - Poor"):         11.24,
    ("Business Banking", "Prime Business"):     10.00,
    ("Business Banking", "Standard Business"):  11.25,
    ("Business Banking", "High Risk Business"): 13.50,
}

FICO_TIERS = {
    "Indirect Auto": [
        (750, 850, "Tier 1 - Super Prime"),
        (700, 749, "Tier 2 - Prime"),
        (650, 699, "Tier 3 - Near Prime"),
        (600, 649, "Tier 4 - Sub Prime"),
        (550, 599, "Tier 5 - Deep Sub"),
    ],
    "Direct Auto": [
        (750, 850, "Tier 1 - Excellent"),
        (700, 749, "Tier 2 - Good"),
        (650, 699, "Tier 3 - Fair"),
        (600, 649, "Tier 4 - Poor"),
    ],
    "Business Banking": [
        (720, 850, "Prime Business"),
        (650, 719, "Standard Business"),
        (580, 649, "High Risk Business"),
    ],
}

def get_tier(product, fico):
    for low, high, tier in FICO_TIERS[product]:
        if low <= fico <= high:
            return tier
    return FICO_TIERS[product][-1][2]

# ── Generate loan portfolio ────────────────────────────────────────────
def generate_portfolio(n=500):
    rows = []
    products = ["Indirect Auto", "Indirect Auto", "Direct Auto", "Business Banking"]
    # Indirect Auto weighted higher (most common)

    for i in range(1, n + 1):
        product = random.choice(products)

        if product in ("Indirect Auto", "Direct Auto"):
            fico = random.randint(550, 820)
            balance = round(random.uniform(5000, 65000), 2)
            term_months = random.choice([36, 48, 60, 72])
            months_remaining = random.randint(3, term_months - 1)
        else:  # Business Banking
            fico = random.randint(580, 800)
            balance = round(random.uniform(50000, 2000000), 2)
            term_months = random.choice([60, 84, 120])
            months_remaining = random.randint(6, term_months - 1)

        tier = get_tier(product, fico)
        current_rate = BANK_RATES.get((product, tier), 9.99)
        # Add some variation — some customers got slightly better rates historically
        current_rate = round(current_rate - random.uniform(0, 0.75), 2)

        origination_date = rand_date(months_remaining + 1, months_remaining + 2)
        last_payment = rand_date(1, 2)
        missed_payments = random.choices([0, 0, 0, 1, 2], weights=[70, 10, 5, 10, 5])[0]

        rows.append({
            "CustomerID":       f"CUST-{i:05d}",
            "CustomerName":     random_name(),
            "Product":          product,
            "CreditTier":       tier,
            "FICO":             fico,
            "LoanBalance":      balance,
            "CurrentRate":      current_rate,
            "LoanTermMonths":   term_months,
            "MonthsRemaining":  months_remaining,
            "OriginationDate":  origination_date,
            "LastPaymentDate":  last_payment,
            "MissedPayments":   missed_payments,
            "State":            random.choice(STATES),
            "RelationshipMgr":  random.choice(["Linda Cho","Marcus Webb","Anita Patel","James Okafor","Sarah Mitchell"]),
        })

    return rows


# ── Generate competitor rates ──────────────────────────────────────────
def generate_competitor_rates():
    rows = []
    competitors = {
        "Chase":          -0.35,   # Chase is 0.35% lower than our bank
        "Wells Fargo":    -0.20,   # Wells Fargo is 0.20% lower
        "Bank of America":-0.15,   # BoA is 0.15% lower
    }
    for (product, tier), our_rate in BANK_RATES.items():
        for bank, diff in competitors.items():
            comp_rate = round(our_rate + diff + random.uniform(-0.10, 0.10), 2)
            comp_rate = max(comp_rate, 3.0)
            rows.append({
                "Product":         product,
                "CreditTier":      tier,
                "OurCurrentRate":  our_rate,
                "CompetitorBank":  bank,
                "CompetitorRate":  comp_rate,
                "RateGap":         round(our_rate - comp_rate, 2),
            })
    return rows


# ── Save ───────────────────────────────────────────────────────────────
def save_csv(rows, filepath):
    if not rows:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

def main():
    portfolio = generate_portfolio(500)
    save_csv(portfolio, os.path.join("data", "loan_portfolio.csv"))
    print(f"✅ loan_portfolio.csv — {len(portfolio)} customers")

    # Print product breakdown
    from collections import Counter
    counts = Counter(r["Product"] for r in portfolio)
    for product, count in counts.items():
        print(f"   {product}: {count} customers")

    competitor = generate_competitor_rates()
    save_csv(competitor, os.path.join("data", "competitor_rates.csv"))
    print(f"✅ competitor_rates.csv — {len(competitor)} rate entries")

    total_balance = sum(r["LoanBalance"] for r in portfolio)
    print(f"\n📊 Portfolio summary:")
    print(f"   Total loan balance : ${total_balance:,.0f}")
    print(f"   Avg loan balance   : ${total_balance/len(portfolio):,.0f}")
    print(f"   Avg FICO           : {sum(r['FICO'] for r in portfolio)//len(portfolio)}")

if __name__ == "__main__":
    main()
