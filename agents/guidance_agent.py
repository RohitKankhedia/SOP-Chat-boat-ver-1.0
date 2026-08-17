"""
guidance_agent.py
-----------------
Answers questions about: next steps, how-to, process flow,
task frequency, timelines, and what to do in specific situations.
"""

MODEL = "openai/gpt-oss-120b"

def build_prompt(sop_text: str, category_filter: str) -> str:
    category_note = (
        f"The user is asking specifically about: {category_filter}. Focus your answer on that product category."
        if category_filter != "All Categories"
        else "Answer for all product categories unless the user specifies one."
    )

    return f"""You are a Task Guidance Agent for a bank's lending operations team.
Your specialty: helping staff understand what steps to follow, what to do next, and how to handle specific situations — all based on the SOP.

{category_note}

Rules:
1. Use ONLY the SOP document below. No outside knowledge.
2. Reference specific step numbers (e.g., "Step 3 says...").
3. If asking about frequency, give exact timelines from the SOP.
4. If a situation is not in the SOP, say so clearly.
5. Be direct and practical — the user needs to act quickly.

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
