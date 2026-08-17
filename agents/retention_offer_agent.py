"""
retention_offer_agent.py
------------------------
Generates a personalized retention offer for a high-risk customer
using the SOP as the rulebook for what offers are allowed.
"""

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are a Retention Offer Agent for a bank's lending operations team.
Your job is to generate a personalized, SOP-compliant retention offer for a customer who is
at risk of refinancing their loan with a competitor after a rate change.

Rules:
1. Offers must stay within the rate bands defined in the SOP rate tables.
2. Any rate reduction below Tier 1 floor requires CLO approval — flag this clearly.
3. Fee waivers are allowed up to $500 without approval; above that needs manager sign-off.
4. Always include: a specific offer, talking points for the relationship manager, and urgency level.
5. Keep the tone professional and customer-focused.
6. Reference which SOP section supports your offer recommendation.

Output format — always use this exact structure:

RECOMMENDED OFFER:
[specific offer — e.g. rate reduction to X%, fee waiver of $Y, loyalty bonus]

TALKING POINTS FOR RM:
• [point 1]
• [point 2]
• [point 3]

URGENCY: [High / Medium / Low] — [one sentence reason]

APPROVAL NEEDED: [Yes / No] — [who needs to approve if yes]

SOP REFERENCE: [section name that supports this offer]
"""

def generate(customer: dict, churn_score: float, sop_text: str, client) -> str:
    """
    customer: dict with CustomerName, Product, CreditTier, LoanBalance,
              CurrentRate, NewRate, BestCompRate, RateGap, FICO, MonthsRemaining
    churn_score: 0-100
    """
    prompt = f"""Generate a retention offer for this customer:

Customer: {customer.get('CustomerName', 'N/A')}
Product: {customer.get('Product', 'N/A')}
Credit Tier: {customer.get('CreditTier', 'N/A')}
FICO Score: {customer.get('FICO', 'N/A')}
Loan Balance: ${float(customer.get('LoanBalance', 0)):,.0f}
Current Rate: {customer.get('CurrentRate', 'N/A')}%
New Rate (post Fed change): {customer.get('NewRate', 'N/A')}%
Best Competitor Rate: {customer.get('BestCompRate', 'N/A')}%
Rate Gap vs Competitor: {customer.get('RateGap', 'N/A')}%
Months Remaining: {customer.get('MonthsRemaining', 'N/A')}
Churn Risk Score: {churn_score}/100
Relationship Manager: {customer.get('RelationshipMgr', 'N/A')}
State: {customer.get('State', 'N/A')}

--- SOP CONTEXT ---
{sop_text[:3000]}
--- END SOP ---
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=600,
        temperature=0.2,
    )
    return response.choices[0].message.content
