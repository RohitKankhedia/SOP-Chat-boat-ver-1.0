# SOP Assistant — RAG Upgrade Implementation Plan

**Project:** Agentic Rate Change Intelligence & Customer Retention System  
**Scope:** Tab 2 (SOP Assistant) only — Tab 1 (Rate Change Intelligence) untouched  
**Priority:** Changes #1 and #2 first (retrieval + citations), then #3–6 built on top

---

## Diagnosis of Current Problems

| File | What it does now | Why it breaks |
|---|---|---|
| `multi_sop_agent._extract()` | Dumps entire .docx as raw text | Business Banking SOP alone can be 4,000+ tokens; 5 SOPs = 20K+ tokens of noise in context |
| `multi_sop_agent.pick_sop()` | LLM guesses which whole file is relevant | Single-file granularity means irrelevant sections from chosen SOP are always included |
| `confidence_agent.score()` | LLM self-rates its own answer | Self-assessment inflates scores; hardcoded fallback of 7 is meaningless |
| `sop_watcher.py` | Watches one hardcoded path | Ignores 4 of 5 SOP files |

---

## Target Architecture

```
FILE INGESTION (at startup + on file change)
  data/*.docx  ──► chunker.py ──► embedder.py ──► FAISS index
  data/*.pdf   ──►              └──────────────► BM25 index
                                  (chunks stored with metadata)

QUERY PATH (per user question)
  question ──► embed query ──► FAISS top-20 ──┐
           └──► BM25 top-20 ──────────────────┴──► RRF fusion ──► top-5 chunks
                                                         │
                                               guardrail check
                                          (max_sim < 0.25?) ──YES──► "not in SOP" (no LLM call)
                                                         │NO
                                                         ▼
                                              Groq LLaMA 3.3 70B
                                          (context = top-5 chunks only)
                                                         │
                                             try/except ─┤
                                         LLM fails?  YES─┴──► return best chunk verbatim
                                                         │NO
                                                         ▼
                                           answer + chunk citations + grounding confidence
```

---

## New File Structure

Only new/changed files are listed. Everything in `agents/` not mentioned stays identical.

```
agents/
  retrieval/                     ← NEW PACKAGE
    __init__.py
    chunker.py                   ← docx/pdf → List[Chunk]
    embedder.py                  ← sentence-transformers wrapper
    faiss_index.py               ← build, search, persist FAISS
    bm25_index.py                ← build, search rank_bm25
    hybrid_search.py             ← RRF fusion
    indexer.py                   ← orchestrates full ingestion pipeline
  sop_retriever.py               ← NEW: public API replacing multi_sop_agent.ask()
  multi_sop_agent.py             ← CHANGED: ask() now calls sop_retriever
  confidence_agent.py            ← CHANGED: blend retrieval signal + LLM score
  sop_watcher.py                 ← CHANGED: watch all files, trigger index rebuild
requirements.txt                 ← CHANGED: add new deps
chatbot/app.py                   ← CHANGED: Tab 2 citation display only
```

---

## Change #1 + #2: Real Retrieval & Citations (implement first)

### 1a. `agents/retrieval/chunker.py`

**Responsibility:** Convert a single document (docx or PDF) into a list of `Chunk` objects with metadata.

**`Chunk` dataclass:**
```python
@dataclass
class Chunk:
    chunk_id: int            # sequential, globally unique across all docs
    source_file: str         # e.g. "SOP_Bank_Rate_Change_Process.docx"
    section_heading: str     # nearest heading above this chunk, e.g. "5. RETENTION ACTIONS"
    text: str                # the chunk text
    token_count: int         # approximate tokens (word count * 1.3 is fine)
    char_start: int          # character offset in original document (for dedup/debug)
```

**Docx chunking strategy:**
- Walk `doc.element.body` block by block (paragraphs + tables), same as current `_extract()`
- Track a `current_section` variable that updates whenever you hit a `Heading` style (`w:pStyle` with `val` starting with `Heading` or matching numbered patterns like "1.", "2.1.")
- Accumulate text into a buffer. When buffer exceeds `MAX_TOKENS = 280`, close the chunk and start a new one, carrying the last sentence of the closed chunk into the new one (overlap)
- Tables: render as `"Field | Value\n..."` lines and treat as one chunk per table (tables are rarely split mid-answer)
- Empty paragraphs: skip

**PDF chunking strategy:**
- Use `pdfplumber`: iterate pages, extract text per page
- Attempt heading detection via font-size heuristic (lines where font size > median → heading candidate)
- If `pytesseract` is available and a page has < 50 chars of extracted text, flag it as scanned and OCR it
- Chunk per page initially; split further if page > `MAX_TOKENS`
- Metadata: `section_heading = "Page {n}"` as fallback when no heading detected

**Token count approximation:**
Use `len(text.split()) * 1.3` — avoids the `tiktoken` dependency for chunking. Accurate enough at 280 token budget.

**Function signature:**
```python
def chunk_docx(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]: ...
def chunk_pdf(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]: ...
def chunk_file(filepath: str, starting_chunk_id: int = 0) -> list[Chunk]: ...  # dispatcher
```

---

### 1b. `agents/retrieval/embedder.py`

**Model:** `BAAI/bge-small-en-v1.5`
- 384 dimensions, ~33MB on disk, free, runs fully locally on CPU
- Consistently outperforms `all-MiniLM-L6-v2` on retrieval benchmarks (MTEB)
- Requires query prefix: `"Represent this sentence for searching relevant passages: {query}"`
- No prefix needed for document chunks

**Key design points:**
- Singleton pattern with `@functools.lru_cache` — model loads once, stays in memory
- Normalize embeddings to unit length so FAISS inner product = cosine similarity
- Batch encode all chunks at index-build time (fast)
- Single-encode queries at search time

```python
def get_model() -> SentenceTransformer: ...          # cached singleton
def encode_chunks(texts: list[str]) -> np.ndarray:  # shape (N, 384), normalized
def encode_query(query: str) -> np.ndarray:          # shape (384,), normalized, with prefix
```

---

### 1c. `agents/retrieval/faiss_index.py`

**Index type:** `faiss.IndexFlatIP` (exact inner product = cosine sim on normalized vectors)
- No training needed, no quantization loss
- For 5 SOPs × ~80 chunks each = ~400 chunks total → exact search takes < 1ms, no need for IVF

**Persistence:** serialize to `data/sop.faiss` and `data/sop_chunks.json` (list of Chunk dicts)

```python
def build(chunks: list[Chunk]) -> tuple[faiss.Index, list[Chunk]]: ...
def search(index, chunks, query_vec: np.ndarray, top_k: int = 20) -> list[tuple[Chunk, float]]:
    # returns [(chunk, cosine_similarity), ...] sorted by score descending
def save(index, chunks, index_path, chunks_path): ...
def load(index_path, chunks_path) -> tuple[faiss.Index, list[Chunk]]: ...
```

---

### 1d. `agents/retrieval/bm25_index.py`

**Library:** `rank_bm25.BM25Okapi`

**Tokenization:** lowercase + split on whitespace + punctuation. No stopword removal (banking terms like "who", "what" are meaningful in SOP queries).

**Persistence:** `pickle` to `data/sop_bm25.pkl`

```python
def build(chunks: list[Chunk]) -> BM25Okapi: ...
def search(bm25, chunks, query: str, top_k: int = 20) -> list[tuple[Chunk, float]]:
    # returns [(chunk, normalized_bm25_score), ...] sorted descending
def save(bm25, path): ...
def load(path) -> BM25Okapi: ...
```

Note: BM25 scores are not normalized by default. After `get_scores()`, normalize by dividing by `max(scores)` so scores are in [0, 1].

---

### 1e. `agents/retrieval/hybrid_search.py`

**Algorithm:** Reciprocal Rank Fusion (RRF) with k=60 (standard constant from original paper).

```
rrf_score(chunk) = Σ 1 / (k + rank_in_retriever_i)
```

**Process:**
1. Get top-20 results from FAISS (with cosine scores)
2. Get top-20 results from BM25 (with normalized scores)
3. Union the result sets (could be up to 40 unique chunks)
4. For each unique chunk: assign rank from each retriever (chunks not in a retriever get rank = 21)
5. Compute RRF score
6. Sort by RRF score, return top `top_k` (default 5)
7. Also return the max cosine similarity (used for guardrail check and confidence scoring)

```python
@dataclass
class SearchResult:
    chunk: Chunk
    cosine_sim: float    # from FAISS (0 if only in BM25)
    bm25_score: float    # normalized (0 if only in FAISS)
    rrf_score: float
    faiss_rank: int      # rank in FAISS results (21 if absent)
    bm25_rank: int       # rank in BM25 results (21 if absent)

def hybrid_search(
    faiss_results: list[tuple[Chunk, float]],
    bm25_results: list[tuple[Chunk, float]],
    top_k: int = 5
) -> list[SearchResult]: ...
```

---

### 1f. `agents/retrieval/indexer.py`

**Responsibility:** Orchestrate full pipeline — scan `data/` folder, chunk all files, build both indexes, save to disk.

```python
SUPPORTED_EXTENSIONS = {".docx", ".pdf"}

def build_index(data_dir: str = "data") -> tuple[faiss.Index, BM25Okapi, list[Chunk]]:
    """Chunks all supported files in data_dir and builds fresh FAISS + BM25 indexes."""

def load_or_build(data_dir: str = "data") -> tuple[faiss.Index, BM25Okapi, list[Chunk]]:
    """Loads persisted indexes if they exist and are newer than all source files.
    Otherwise rebuilds. Returns (faiss_index, bm25_index, chunks)."""

def get_file_mtimes(data_dir: str) -> dict[str, float]:
    """Returns {filepath: mtime} for all supported files."""
```

**Staleness check:** compare the minimum mtime of `sop.faiss`, `sop_chunks.json`, `sop_bm25.pkl` against the maximum mtime of all source files. If any source is newer than any index, rebuild.

---

### 1g. `agents/sop_retriever.py` — The Public API

This replaces `multi_sop_agent.ask()` as the retrieval interface. Everything else (`router.py`, specialist agents) remains the same — they still call `multi_sop_agent.ask()`, which now delegates here.

```python
# Module-level state (initialized once at import time)
_faiss_index = None
_bm25_index = None
_all_chunks: list[Chunk] = []

SIMILARITY_THRESHOLD = 0.25   # below this = "not in SOP" (code-level guardrail, fix #4)
TOP_K_RETRIEVAL = 5

def initialize(data_dir: str = "data"):
    """Load or build indexes. Called once at app startup."""

def retrieve(query: str) -> list[SearchResult]:
    """Run hybrid search. Returns [] if max cosine_sim < SIMILARITY_THRESHOLD."""

def ask(
    question: str,
    history: list,
    client,
    category_filter: str = "All Categories"
) -> tuple[str, list[SearchResult]]:
    """
    Full pipeline:
    1. retrieve() — if empty, return guardrail message (no LLM call)
    2. Build LLM context from top chunks
    3. Call Groq with try/except
    4. On LLM failure, return best chunk verbatim (graceful degradation, fix #6)
    Returns (answer_text, search_results_used)
    """
```

**LLM context construction:**

```python
CONTEXT_TEMPLATE = """
Use ONLY the following excerpts from the bank's SOP documents to answer the question.
Each excerpt shows its source document and section.
If the answer is not in these excerpts, say so — do not guess.

{formatted_chunks}

Question: {question}
"""

def _format_chunks_for_context(results: list[SearchResult]) -> str:
    # For each result:
    # [1] SOP_Bank_Rate_Change_Process.docx | Section: 5. RETENTION ACTIONS
    # "Any rate reduction below Tier 1 floor requires CLO approval..."
    #
    # [2] SOP_Bank_Rate_Change_Process.docx | Section: 3. APPROVAL AUTHORITY
    # "ALCO must approve all rate changes..."
```

**Guardrail response (fix #4):**
```
"This question could not be answered from the bank's SOP documents.
 The available SOP content does not appear to cover this topic.
 Please consult your supervisor or the relevant policy owner directly."
```

**Graceful degradation response (fix #6):**
```
"The AI assistant is temporarily unavailable. Here is the most relevant
 section from the SOP documents that may help:

 [Source: {source_file} → {section_heading}]
 {best_chunk_text}"
```

---

## Change #2: Citations in the UI

**In `chatbot/app.py` (Tab 2 only):**

Each message stored in `st.session_state.messages` gains a `"search_results"` field (list of `SearchResult` dicts, not the dataclass itself for JSON serialization).

Replace current single-line citation:
```python
# CURRENT:
st.markdown(f"📄 Source: {sop_used}")
```

With multi-chunk citation block:
```python
# NEW:
if search_results and not msg.get("is_clarification"):
    with st.expander(f"📄 {len(search_results)} SOP excerpt(s) used", expanded=False):
        for i, r in enumerate(search_results, 1):
            sim_pct = int(r["cosine_sim"] * 100)
            st.markdown(
                f"**[{i}] {r['source_file']}** → _{r['section_heading']}_  "
                f"<small style='color:#888'>({sim_pct}% match)</small>",
                unsafe_allow_html=True
            )
            st.caption(r["chunk_text"][:300] + ("…" if len(r["chunk_text"]) > 300 else ""))
```

This gives judges: "The answer came from Section 5 of the Rate Change SOP (87% match)" — not just a filename.

---

## Change #3: Grounding-Based Confidence

**In `agents/confidence_agent.py`:**

Add a retrieval-based signal and blend it with the existing LLM self-score.

```python
def score_from_retrieval(search_results: list[SearchResult]) -> dict:
    """
    Derive confidence purely from retrieval quality.
    No LLM call needed.
    """
    if not search_results:
        return {"score": 1, "reasoning": "No relevant SOP content found for this question."}

    top_sim = search_results[0].cosine_sim       # 0.0–1.0
    n_supporting = sum(1 for r in search_results if r.cosine_sim >= 0.4)

    # Map cosine similarity to 1-10
    retrieval_score = round(top_sim * 10, 1)

    # Boost slightly if multiple chunks support the answer
    if n_supporting >= 3:
        retrieval_score = min(retrieval_score + 0.5, 10.0)

    label = "High" if retrieval_score >= 8 else "Medium" if retrieval_score >= 5 else "Low"
    reasoning = (
        f"Top SOP match: {int(top_sim*100)}% similarity, "
        f"{n_supporting} supporting excerpt(s) found."
    )
    return {"score": retrieval_score, "reasoning": reasoning}


def score(question: str, answer: str, client, search_results: list = None) -> dict:
    """
    Blended confidence: 60% retrieval signal + 40% LLM self-assessment.
    Falls back to retrieval-only if LLM call fails.
    """
    retrieval_conf = score_from_retrieval(search_results or [])

    try:
        llm_conf = _llm_score(question, answer, client)   # existing logic, renamed
        blended = round(0.6 * retrieval_conf["score"] + 0.4 * llm_conf["score"], 1)
        return {
            "score": blended,
            "reasoning": retrieval_conf["reasoning"]
        }
    except Exception:
        return retrieval_conf    # fallback to retrieval-only (no hardcoded 7)
```

**Callers** pass `search_results` through. `multi_sop_agent.ask()` already returns them; just thread through to `confidence_agent.score()`.

---

## Change #4: Code-Level Guardrail

Already handled inside `sop_retriever.retrieve()`:

```python
def retrieve(query: str) -> list[SearchResult]:
    results = hybrid_search(...)
    if not results or results[0].cosine_sim < SIMILARITY_THRESHOLD:
        return []   # empty list = guardrail triggered

def ask(...):
    results = retrieve(question)
    if not results:
        return _GUARDRAIL_MESSAGE, []   # no LLM call whatsoever
    ...
```

The prompt still says "answer only from SOP" but the guardrail fires first in Python — the LLM is never called if retrieval finds nothing relevant. The threshold `0.25` can be tuned; start there and lower to `0.20` if too many false-positives (questions that should have answers but are rejected).

---

## Change #5: Multi-File Watching + PDF Support

**`agents/sop_watcher.py` rewrite:**

```python
DATA_DIR = "data"
SUPPORTED_EXTENSIONS = {".docx", ".pdf"}

# Replace the hardcoded SOP_DOCX path with a full-folder scan

def get_all_file_mtimes() -> dict[str, float]:
    """Returns {filepath: mtime} for all supported files in DATA_DIR."""

def check_and_reload_all(last_mtimes: dict[str, float]) -> tuple[dict[str, float], bool]:
    """
    Compares current mtimes vs stored mtimes.
    Returns (current_mtimes, changed: bool).
    If changed=True, caller should trigger indexer.build_index().
    """
```

**In `chatbot/app.py` startup:**
```python
# Replace current sop_watcher calls with:
if "index_mtimes" not in st.session_state:
    sop_retriever.initialize()
    st.session_state.index_mtimes = sop_watcher.get_all_file_mtimes()
else:
    current_mtimes, changed = sop_watcher.check_and_reload_all(st.session_state.index_mtimes)
    if changed:
        sop_retriever.rebuild()          # triggers indexer.build_index()
        st.session_state.index_mtimes = current_mtimes
        st.toast("📄 SOPs updated and re-indexed!", icon="🔄")
```

**PDF support in `chunker.py`:**
- `pdfplumber` handles most native PDFs (annual reports, policy PDFs, etc.)
- Scanned PDF detection: if `page.extract_text()` returns < 50 chars, flag as scanned
- OCR path: `pdf2image.convert_from_path()` → `pytesseract.image_to_string()`
- Make OCR optional: if `pytesseract` import fails, log a warning and skip scanned pages

---

## Change #6: Graceful Degradation

Already covered in `sop_retriever.ask()`:

```python
try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[...],
        max_tokens=1024,
        temperature=0.1,
    )
    answer = response.choices[0].message.content
except Exception as e:
    # Return best matching chunk verbatim — always useful, always SOP-grounded
    best = results[0]
    answer = (
        f"⚠️ The AI assistant is temporarily unavailable (error: {type(e).__name__}).\n\n"
        f"Here is the most relevant excerpt from the SOP documents:\n\n"
        f"**{best.chunk.source_file}** → _{best.chunk.section_heading}_\n\n"
        f"{best.chunk.text}"
    )
```

This also applies to specialist agents (`guidance_agent.ask()`, etc.) — wrap their Groq calls the same way. Or: have `multi_sop_agent.ask()` catch their exceptions and apply the same fallback pattern.

---

## New Dependencies

Add to `requirements.txt`:

```
# Existing
python-docx
groq
streamlit
pandas

# NEW — retrieval
sentence-transformers>=2.7.0
faiss-cpu>=1.8.0
rank-bm25>=0.2.2

# NEW — PDF support
pdfplumber>=0.11.0

# NEW — optional OCR (scanned PDFs only)
# pytesseract>=0.3.10
# pdf2image>=1.17.0
```

**Install command for EXL VM (Python 3.14):**
```powershell
& C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe -m pip install `
  sentence-transformers faiss-cpu rank-bm25 pdfplumber
```

**First-run note:** `sentence-transformers` downloads the model (~33MB) on first use. On the EXL VM, run `python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"` once before the demo to cache it.

---

## What Stays Completely Unchanged

- `agents/router.py` — no changes
- `agents/guidance_agent.py` — no changes
- `agents/escalation_agent.py` — no changes
- `agents/compliance_agent.py` — no changes
- `agents/email_agent.py` — no changes
- `agents/portfolio_risk_agent.py` — no changes
- `agents/retention_offer_agent.py` — no changes
- `chatbot/app.py` Tab 1 (Rate Change Intelligence) — no changes
- All scripts in `scripts/` — no changes
- `data/*.docx` SOP documents — no changes

---

## Implementation Order (strict — each step depends on the previous)

| Step | File | What it enables |
|---|---|---|
| 1 | `agents/retrieval/chunker.py` | Foundation — everything needs chunks |
| 2 | `agents/retrieval/embedder.py` | Needed by FAISS |
| 3 | `agents/retrieval/faiss_index.py` | Vector search |
| 4 | `agents/retrieval/bm25_index.py` | Keyword search |
| 5 | `agents/retrieval/hybrid_search.py` | RRF fusion (needs 3+4) |
| 6 | `agents/retrieval/indexer.py` | End-to-end ingestion (needs 1–5) |
| 7 | `agents/sop_retriever.py` | Public API + guardrail + fallback |
| 8 | `agents/multi_sop_agent.py` | Wire retriever into existing flow |
| 9 | `agents/confidence_agent.py` | Update signature to accept search_results |
| 10 | `agents/sop_watcher.py` | Multi-file watching |
| 11 | `chatbot/app.py` (Tab 2 only) | Citation display, pass search_results through |
| 12 | `requirements.txt` | Add new deps |
| 13 | Install + test | Run app, verify end-to-end |

---

## Key Design Decisions and Rationale

**Why `BAAI/bge-small-en-v1.5` over `all-MiniLM-L6-v2`?**
BGE-small consistently scores ~3-5 points higher on MTEB retrieval benchmarks at the same model size (33MB). Both are free and local. The query prefix requirement is a small cost for meaningfully better recall.

**Why `IndexFlatIP` (exact search) instead of IVF?**
With ~400 chunks total (5 SOPs × ~80 chunks each), exact search takes < 1ms. IVF introduces quantization error and training complexity for zero benefit at this scale. If the SOP library grows to 50+ documents, switch to `IndexIVFFlat` then.

**Why RRF with k=60?**
The original RRF paper (Cormack et al., 2009) established k=60 as robust across diverse retrieval settings. It's not tuned to this dataset but it will perform well. The key property is that it's robust to score scaling differences between FAISS (cosine, 0–1) and BM25 (arbitrary positive integers) — both are converted to ranks first.

**Why threshold 0.25 for the guardrail?**
Cosine similarity of 0.25 with `bge-small-en-v1.5` corresponds roughly to "topically related but not a match." Below 0.25, the model embedding space says the query shares essentially no semantic content with any chunk. This is a conservative starting point — if you get too many false "not in SOP" rejections on questions you know the SOP covers, lower to 0.20.

**Why 280 tokens per chunk?**
With 5 chunks in context and ~280 tokens each, you use ~1,400 tokens for retrieval context. LLaMA 3.3 70B has an 8K context window — this leaves ample room for the system prompt (~400 tokens), conversation history, and the LLM's response. 280 also aligns with "one meaningful section" in most SOP documents.

**Why keep `multi_sop_agent.ask()` as the interface?**
`router.py` and `app.py` both call `multi_sop_agent.ask()`. Keeping that function signature lets us swap the internals without touching `router.py`, all specialist agents, or the main app's Tab 2 logic. `sop_retriever.py` is an internal dependency, not a public interface.

---

## What Judges Will See After This Upgrade

**Before:** "Source: SOP_Bank_Rate_Change_Process.docx"

**After:**
```
📄 3 SOP excerpt(s) used
  [1] SOP_Bank_Rate_Change_Process.docx → 5. RETENTION ACTIONS  (87% match)
      "Any rate reduction below Tier 1 floor requires CLO approval..."
  [2] SOP_Bank_Rate_Change_Process.docx → 3. APPROVAL AUTHORITY  (74% match)
      "ALCO must approve all rate changes before implementation..."
  [3] SOP_Loan_Origination_Underwriting.docx → 3. CREDIT TIERS  (41% match)
      "Tier 1 Super Prime: FICO 750-850, max DTI 40%..."

Confidence: High (8.2/10) — Top SOP match: 87% similarity, 3 supporting excerpts found.
```

That is the difference between "we built a chatbot with a document" and "we built a grounded, auditable AI system."
