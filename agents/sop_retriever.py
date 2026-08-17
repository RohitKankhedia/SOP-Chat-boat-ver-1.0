"""
sop_retriever.py
----------------
Public retrieval API for the SOP Assistant.

Replaces the naive "dump entire SOP file into LLM context" approach.

Pipeline per query:
  1. Embed query (BGE-small-en-v1.5)
  2. FAISS top-20 + BM25 top-20 → RRF top-5 chunks
  3. Guardrail: if max cosine_sim < SIMILARITY_THRESHOLD → no LLM call,
     return hardcoded "not covered in SOP" message
  4. Build context from top-5 chunk texts + metadata
  5. Call Groq LLaMA 3.3 70B
  6. On LLM failure → return best chunk verbatim (graceful degradation)
"""

from __future__ import annotations

from agents.retrieval.indexer  import load_or_build, build_index
from agents.retrieval.hybrid_search import SearchResult, hybrid_search
from agents.retrieval import embedder, faiss_index, bm25_index
from agents.guardrails import check_input, check_output

MODEL = "openai/gpt-oss-120b"

SIMILARITY_THRESHOLD = 0.25   # cosine sim below this = guardrail fires, no LLM call
TOP_K = 5                      # chunks sent to LLM context

# ── Module-level state (initialized once) ────────────────────────────────────

_faiss_idx   = None
_bm25_idx    = None
_all_chunks  = []
_initialized = False


# ── Initialization ────────────────────────────────────────────────────────────

def initialize(data_dir: str = "data") -> None:
    """Load or build indexes. Call once at app startup."""
    global _faiss_idx, _bm25_idx, _all_chunks, _initialized
    _faiss_idx, _bm25_idx, _all_chunks = load_or_build(data_dir)
    _initialized = True
    print(f"[sop_retriever] Ready — {len(_all_chunks)} chunks indexed.")


def rebuild(data_dir: str = "data") -> None:
    """Force a full re-index (called when SOP files change)."""
    global _faiss_idx, _bm25_idx, _all_chunks
    _faiss_idx, _bm25_idx, _all_chunks = build_index(data_dir)
    print(f"[sop_retriever] Re-indexed — {len(_all_chunks)} chunks.")


def _ensure_initialized() -> None:
    if not _initialized or not _all_chunks:
        initialize()


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str) -> list[SearchResult]:
    """
    Hybrid search: FAISS + BM25 → RRF → top-5 chunks.
    Returns [] if max cosine_sim < SIMILARITY_THRESHOLD (guardrail trigger).
    """
    _ensure_initialized()
    if not _all_chunks:
        return []

    query_vec     = embedder.encode_query(query)
    faiss_results = faiss_index.search(_faiss_idx, _all_chunks, query_vec, top_k=20)
    bm25_results  = bm25_index.search(_bm25_idx,  _all_chunks, query,     top_k=20)
    results       = hybrid_search(faiss_results, bm25_results, top_k=TOP_K)

    # Code-level guardrail — fires before LLM call
    if not results or results[0].cosine_sim < SIMILARITY_THRESHOLD:
        return []

    return results


# ── Context formatting ────────────────────────────────────────────────────────

def _format_context(results: list[SearchResult]) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[Excerpt {i}]\n"
            f"Source: {r.chunk.source_file} | "
            f"Section: {r.chunk.section_heading} | "
            f"Match: {int(r.cosine_sim * 100)}%\n\n"
            f"{r.chunk.text}"
        )
    return "\n\n---\n\n".join(parts)


_SYSTEM_TEMPLATE = """\
You are an expert SOP assistant for a bank's operations team.
Answer the user's question using ONLY the SOP excerpts provided below.
{category_note}
Reference the specific Section name from the excerpts when you quote or paraphrase.
If the answer is not in these excerpts, say so clearly — do not guess or use outside knowledge.

{context}
"""

_GUARDRAIL_MESSAGE = (
    "⚠️ **Not covered in SOP documents.**\n\n"
    "The available SOP content does not appear to cover this topic sufficiently "
    "to provide a reliable answer. Please consult your supervisor or the "
    "relevant policy owner directly."
)


def _fallback_message(results: list[SearchResult], error: Exception) -> str:
    if not results:
        return "❌ The AI assistant is temporarily unavailable and no relevant SOP excerpts were found."
    best = results[0]
    return (
        f"⚠️ **AI assistant temporarily unavailable** ({type(error).__name__}).\n\n"
        f"Here is the most relevant SOP excerpt:\n\n"
        f"**{best.chunk.source_file}** → _{best.chunk.section_heading}_ "
        f"({int(best.cosine_sim * 100)}% match)\n\n"
        f"{best.chunk.text}"
    )


# ── Main ask function ─────────────────────────────────────────────────────────

def ask(
    question: str,
    history: list,
    client,
    category_filter: str = "All Categories",
) -> tuple[str, list[SearchResult]]:
    """
    Full RAG pipeline:
      1. Retrieve relevant chunks (hybrid search)
      2. Guardrail: empty results → return message without calling LLM
      3. Build chunk-based context, call Groq
      4. LLM failure → return best chunk verbatim

    Returns (answer_text, search_results_used).
    search_results is [] if the guardrail fired.
    """
    # ── INPUT GUARDRAIL (code-level, not prompt-based) ────────────────
    input_check = check_input(question)
    if not input_check.safe:
        return input_check.user_message, []

    results = retrieve(question)

    # Retrieval guardrail — no LLM call at all
    if not results:
        return _GUARDRAIL_MESSAGE, []

    category_note = (
        f"The user is asking about: {category_filter}. "
        f"Focus on that product category where relevant."
        if category_filter != "All Categories"
        else ""
    )

    system_msg = _SYSTEM_TEMPLATE.format(
        category_note=category_note,
        context=_format_context(results),
    )

    messages = [{"role": "system", "content": system_msg}]
    messages += history
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = _fallback_message(results, e)

    # ── OUTPUT GUARDRAIL (PII redaction, length cap, retrieval hard-block) ─
    top_confidence = results[0].cosine_sim if results else 0.0
    output_check = check_output(answer, retrieval_confidence=top_confidence)
    return output_check.text, results
