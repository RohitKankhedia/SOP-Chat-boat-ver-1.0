"""
multi_sop_agent.py
------------------
SOP question answering — now backed by real RAG retrieval via sop_retriever.py.

ask() is a thin wrapper that delegates to sop_retriever.ask().
The old full-file extraction code is kept for backward compatibility
(used by sop_watcher.load_sop_text and Tab 1's retention offer agent).
"""

from __future__ import annotations

import os

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table

import agents.sop_retriever as sop_retriever
from agents.retrieval.hybrid_search import SearchResult

MODEL    = "openai/gpt-oss-120b"
DATA_DIR = "data"


# ── Legacy extraction (used by Tab 1 retention offer + sop_watcher) ───────────

def load_all_sops() -> dict:
    """
    Legacy: returns {filename: full_text}. No longer used by ask().
    Kept so existing callers (app.py's get_all_sops cache) don't break.
    """
    sops = {}
    if not os.path.exists(DATA_DIR):
        return sops
    for fname in os.listdir(DATA_DIR):
        if fname.endswith(".docx"):
            path = os.path.join(DATA_DIR, fname)
            try:
                sops[fname] = _extract(path)
            except Exception as e:
                print(f"[MultiSOP] Could not load {fname}: {e}")
    return sops


def _extract(filepath: str) -> str:
    doc   = Document(filepath)
    lines = []
    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            text = "".join(
                node.text or ""
                for node in block.iter()
                if node.tag == qn("w:t")
            )
            if text.strip():
                lines.append(text.strip())
        elif tag == "tbl":
            tbl = Table(block, doc)
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
            lines.append("")
    return "\n".join(lines)


# ── Clarification check (unchanged) ──────────────────────────────────────────

def needs_clarification(question: str, client) -> tuple[bool, str]:
    """
    Only asks for clarification on truly ambiguous very-short queries.
    Long questions (5+ words) or questions with clear banking keywords: always CLEAR.
    """
    words = question.strip().split()
    if len(words) >= 5:
        return False, ""

    clear_keywords = [
        "email", "escalat", "rate", "loan", "wire", "ach", "kyc", "aml", "sar", "ctr",
        "eod", "batch", "step", "process", "contact", "who", "what", "how", "when",
        "approve", "compli", "regul", "ofac", "underwr", "disburse", "close"
    ]
    if any(kw in question.lower() for kw in clear_keywords):
        return False, ""

    prompt = """A user asked a very short question to a banking SOP chatbot.
Is it too vague to answer without clarification?

Reply CLARIFY: <one short question> if truly ambiguous.
Reply CLEAR if there is enough context to attempt an answer.

Rules:
- If the question has any banking or process keyword, reply CLEAR.
- Only reply CLARIFY for completely meaningless queries with no context.
"""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": question},
        ],
        max_tokens=60,
        temperature=0.0,
    )
    reply = response.choices[0].message.content.strip()
    if reply.startswith("CLARIFY:"):
        return True, reply[len("CLARIFY:"):].strip()
    return False, ""


# ── Main ask — delegates to RAG retriever ─────────────────────────────────────

def ask(
    question: str,
    history: list,
    sops: dict,              # kept for signature compatibility, no longer used
    client,
    category_filter: str = "All Categories",
) -> tuple[str, list[SearchResult]]:
    """
    Answer a question using hybrid RAG retrieval.
    Returns (answer_text, search_results) with chunk-level citations.

    The `sops` parameter is accepted but ignored — the retriever
    builds its own context from indexed chunks.
    """
    return sop_retriever.ask(question, history, client, category_filter)


# ── Legacy pick_sop (no longer called) ───────────────────────────────────────

def pick_sop(question: str, sop_names: list, client) -> str:
    """Legacy: LLM-based SOP picker. No longer used in the main path."""
    if len(sop_names) == 1:
        return sop_names[0]
    names_list = "\n".join(f"- {n}" for n in sop_names)
    prompt = (
        f"You are a document router. Pick the ONE most relevant SOP filename.\n"
        f"Reply with ONLY the exact filename.\n\nSOPs:\n{names_list}\n\nQuestion: {question}"
    )
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.0,
    )
    chosen = response.choices[0].message.content.strip()
    return chosen if chosen in sop_names else sop_names[0]
