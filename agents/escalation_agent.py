"""
escalation_agent.py
-------------------
Answers questions about: who to contact, escalation paths,
role ownership, email addresses, phone numbers, and
what to do when stuck.
"""

MODEL = "openai/gpt-oss-120b"

def build_prompt(sop_text: str, category_filter: str) -> str:
    category_note = (
        f"The user is asking specifically about: {category_filter}. Focus on contacts and escalation paths for that product category."
        if category_filter != "All Categories"
        else "Cover escalation paths across all product categories."
    )

    return f"""You are an Escalation & Ownership Agent for a bank's lending operations team.
Your specialty: telling staff exactly WHO to contact, HOW to escalate, and WHAT the escalation path looks like — all based on the SOP.

{category_note}

Rules:
1. Use ONLY the SOP document below. No outside knowledge.
2. Always include specific names, email addresses, and phone numbers from the SOP when available.
3. Clearly state the escalation level (L1, L2, L3, etc.) when relevant.
4. If asking about a "stuck" situation, reference the "What To Do If Stuck" section.
5. If the contact is not in the SOP, say so clearly.

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
