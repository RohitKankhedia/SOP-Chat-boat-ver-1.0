"""
router.py
---------
Reads the user's question and decides which specialist
agent should handle it.

Agents:
  guidance    — next steps, how-to, process, timelines
  escalation  — who to contact, escalation paths, ownership
  compliance  — regulations, legal, audit requirements
  email       — drafting emails, writing messages
  general     — anything else
"""

MODEL = "openai/gpt-oss-120b"

ROUTER_PROMPT = """You are a routing assistant. Read the user's question and decide which specialist agent should answer it.

Choose exactly ONE of these agents:
- guidance    : questions about steps, process, what to do next, how to handle a situation, timelines, frequency
- escalation  : questions about who to contact, who is responsible, escalation paths, contacts, emails, phone numbers
- compliance  : questions about regulations, legal requirements, compliance rules, audit, ECOA, Reg Z, MLA, usury
- email       : user wants to draft or write an email, message, or communication to someone
- general     : any other SOP question

Reply with ONLY the agent name. No explanation, no punctuation.
"""

def route(question: str, client) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ROUTER_PROMPT},
            {"role": "user",   "content": question},
        ],
        max_tokens=10,
        temperature=0.0,
    )
    agent = response.choices[0].message.content.strip().lower()
    valid = {"guidance", "escalation", "compliance", "email", "general"}
    return agent if agent in valid else "general"
