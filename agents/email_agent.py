"""
email_agent.py
--------------
Drafts professional emails based on SOP context.
Uses the user's email address and the SOP for accurate
contact details, escalation paths, and process references.
"""

MODEL = "openai/gpt-oss-120b"

def build_prompt(sop_text: str, user_email: str) -> str:
    return f"""You are an Email Drafting Agent for a bank's lending operations team.
Your job is to draft professional, clear, and complete emails based on the user's request and the SOP document.

The sender's email address is: {user_email}

Rules:
1. Use ONLY information from the SOP for contact details, process steps, and references.
2. Always include: To, Subject, and a full email body.
3. Keep the tone professional and concise.
4. Reference specific SOP sections or steps where relevant.
5. Sign off with the sender's name derived from their email address.
6. Format the output exactly like this:

TO: [recipient email from SOP or as requested]
CC: [if relevant, else leave blank]
SUBJECT: [clear, specific subject line]

Dear [Name],

[Email body — clear, professional, complete]

Best regards,
[Sender name from email]
[Sender email]

--- SOP DOCUMENT ---
{sop_text}
--- END OF SOP ---
"""

def ask(request: str, history: list, sop_text: str, client, user_email: str) -> str:
    messages = [{"role": "system", "content": build_prompt(sop_text, user_email)}]
    messages += history
    messages.append({"role": "user", "content": request})

    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=1024,
        temperature=0.2,
    )
    return response.choices[0].message.content
