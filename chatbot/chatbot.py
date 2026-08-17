"""
chatbot.py
----------
SOP Intelligence Chatbot — powered by Groq (LLaMA 3)
Answers questions ONLY from the SOP document content.

Usage:
    python chatbot/chatbot.py
"""

import os
from groq import Groq

# ── Config ─────────────────────────────────────────────────────────────
SOP_FILE   = os.path.join("data", "SOP_extracted.txt")
MODEL      = "llama3-70b-8192"   # Groq's LLaMA 3 70B model (free)
MAX_TOKENS = 1024


# ── Load SOP ───────────────────────────────────────────────────────────
def load_sop(filepath):
    if not os.path.exists(filepath):
        print(f"ERROR: SOP file not found at '{filepath}'")
        print("Run 'python scripts/read_sop.py' first.")
        exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


# ── System prompt ──────────────────────────────────────────────────────
def build_system_prompt(sop_text):
    return f"""You are an expert SOP Assistant for a bank's lending operations team.
Your job is to answer questions ONLY using the SOP document provided below.

Rules you must follow:
1. Only use information from the SOP document. Do not use outside knowledge.
2. If the answer is not in the SOP, say: "This information is not covered in the SOP."
3. Be specific — mention step numbers, role names, contact emails, and timeframes when available.
4. Keep answers concise and practical. The user is an operations staff member who needs quick guidance.
5. If a question mentions a product category (Indirect Auto, Direct Auto, Business Banking), focus your answer on that category.

--- SOP DOCUMENT START ---
{sop_text}
--- SOP DOCUMENT END ---
"""


# ── Ask a question ─────────────────────────────────────────────────────
def ask(client, messages):
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=0.1,   # Low temperature = more factual, less creative
    )
    return response.choices[0].message.content


# ── Main chat loop ─────────────────────────────────────────────────────
def main():
    # Check API key
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY environment variable not set.")
        print("Run: $env:GROQ_API_KEY = 'your-key-here'")
        exit(1)

    # Load SOP
    print("Loading SOP document...")
    sop_text = load_sop(SOP_FILE)
    print(f"✅ SOP loaded ({len(sop_text.split())} words)\n")

    # Set up Groq client
    client = Groq(api_key=api_key)

    # Conversation history (keeps context across messages)
    messages = [
        {"role": "system", "content": build_system_prompt(sop_text)}
    ]

    # Welcome message
    print("=" * 60)
    print("  SOP Intelligence Assistant — Bank Rate Change Process")
    print("=" * 60)
    print("Ask any question about the SOP. Type 'exit' to quit.\n")
    print("Example questions:")
    print("  - What is the first step in the rate change process?")
    print("  - Who approves rate changes?")
    print("  - What should I do if a dealer didn't receive the rate sheet?")
    print("  - What are the SLA timelines for a P1 issue?")
    print("  - How do I handle a floating rate business loan change?")
    print("-" * 60)

    # Chat loop
    while True:
        user_input = input("\nYou: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "bye"):
            print("Goodbye!")
            break

        # Add user message to history
        messages.append({"role": "user", "content": user_input})

        print("\nAssistant: ", end="", flush=True)

        try:
            answer = ask(client, messages)
            print(answer)

            # Add assistant reply to history (enables follow-up questions)
            messages.append({"role": "assistant", "content": answer})

        except Exception as e:
            print(f"\nERROR: {e}")
            print("Check your GROQ_API_KEY and internet connection.")
            # Remove the failed user message from history
            messages.pop()


if __name__ == "__main__":
    main()
