"""
confidence_agent.py
-------------------
Confidence scoring blending retrieval quality (60%) + LLM self-assessment (40%).

The primary signal is the cosine similarity of the top retrieved chunk —
a grounded, objective measure of how well the SOP covers the question.
The LLM self-rating is a secondary signal weighted at 40%.

On LLM failure, returns the retrieval-only score — no hardcoded fallback.
"""

from __future__ import annotations

import json

MODEL = "openai/gpt-oss-120b"

_LLM_PROMPT = """\
You are a quality checker for an SOP-based AI assistant.
Given a user question and the assistant's answer, rate how well
the answer is grounded in SOP content.

Return ONLY valid JSON — no extra text, no markdown fences:
{
  "score": <integer 1 to 10>,
  "reasoning": "<one short sentence>"
}

10 = directly and completely in the SOP
8-9 = mostly in the SOP, minor inference
6-7 = partial SOP coverage, some gaps
4-5 = loosely related to SOP content
1-3 = not properly sourced from the SOP
"""


# ── Retrieval-based signal (primary, no LLM call) ─────────────────────────────

def score_from_retrieval(search_results: list) -> dict:
    """
    Derive confidence purely from retrieval quality.
    search_results: list of SearchResult objects or serialized dicts.

    Returns {"score": float, "reasoning": str}.
    """
    if not search_results:
        return {
            "score": 1.0,
            "reasoning": "No relevant SOP content found for this question.",
        }

    def _sim(r) -> float:
        return r["cosine_sim"] if isinstance(r, dict) else r.cosine_sim

    top_sim       = _sim(search_results[0])
    n_supporting  = sum(1 for r in search_results if _sim(r) >= 0.40)

    # Map cosine similarity [0, 1] → [0, 10], capped at 10
    retrieval_score = min(round(top_sim * 10, 1), 10.0)

    # Small boost when multiple chunks independently corroborate the answer
    if n_supporting >= 3:
        retrieval_score = min(retrieval_score + 0.5, 10.0)

    reasoning = (
        f"Top SOP match: {int(top_sim * 100)}% similarity, "
        f"{n_supporting} corroborating excerpt(s) found."
    )
    return {"score": retrieval_score, "reasoning": reasoning}


# ── LLM self-assessment (secondary) ──────────────────────────────────────────

def _llm_score(question: str, answer: str, client) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _LLM_PROMPT},
            {"role": "user",   "content": f"QUESTION: {question}\n\nANSWER: {answer}"},
        ],
        max_tokens=100,
        temperature=0.0,
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


# ── Blended scorer (public API) ───────────────────────────────────────────────

def score(
    question: str,
    answer: str,
    client,
    search_results: list = None,
) -> dict:
    """
    Blended confidence: 60% retrieval signal + 40% LLM self-assessment.

    Falls back to retrieval-only score if the LLM call fails.
    search_results: list of SearchResult objects or serialized dicts with cosine_sim.
    """
    retrieval_conf = score_from_retrieval(search_results or [])

    try:
        llm_conf = _llm_score(question, answer, client)
        blended  = round(0.6 * retrieval_conf["score"] + 0.4 * float(llm_conf["score"]), 1)
        return {
            "score":     blended,
            "reasoning": retrieval_conf["reasoning"],
        }
    except Exception:
        # No hardcoded fallback — retrieval signal alone is meaningful
        return retrieval_conf
