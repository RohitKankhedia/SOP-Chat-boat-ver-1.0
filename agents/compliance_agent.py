"""
compliance_agent.py
-------------------
Answers questions about: regulations, legal requirements,
compliance rules, audit requirements, and regulatory constraints
on rate changes — all based on the SOP.
"""

MODEL = "openai/gpt-oss-120b"

def build_prompt(sop_text: str, category_filter: str) -> str:
    category_note = (
        f"The user is asking specifically about: {category_filter}. Focus on compliance requirements for that product category."
        if category_filter != "All Categories"
        else "Cover compliance requirements across all product categories."
    )

    return f"""You are a Compliance & Regulatory Agent for a bank's lending operations team.
Your specialty: explaining which regulations apply, what the compliance requirements are, and what the bank must do to stay compliant during rate changes — all based on the SOP.

{category_note}

Rules:
1. Use ONLY the SOP document below. No outside knowledge.
2. Always name the specific regulation (e.g., Reg Z, ECOA, MLA, state usury laws).
3. State clearly what the requirement means in plain language.
4. If a rate or action might violate a regulation, flag it clearly with ⚠️.
5. If the compliance detail is not in the SOP, say so — do not guess.

--- SOP DOCUMENT ---
{sop_text}
--- END OF SOP ---
"""

def ask(question: str, history: list, sop_text: str, client, category_filter: str = "All Categories") -> str:
    messages = [{"role": "system", "content": build_prompt(sop_text, category_filter)}]
    messages += history
    messages.append({"role": "user", "content": question})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.1,
    )
    return response.choices[0].message.content
