# AI Handoff Prompt — Agentic Rate Change Intelligence System
## Paste this into any AI assistant to continue development, tweak, or document this project.

---

## What This Project Is

A two-tab Streamlit web application built for EXL Hackathon 2026. It solves a real banking problem: when the Federal Reserve changes interest rates, banks lose millions of dollars because they can't quickly identify which customers are about to refinance with a competitor. This app identifies those customers in 3 minutes (vs 2 days manually) and generates personalized retention offers grounded in the bank's own policy documents.

**GitHub:** https://github.com/RohitKankhedia/SOP-Chat-boat-ver-1.0
**Built by:** Rohit Kankhedia
**Current version:** v3.0 — Guardrails Edition

---

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit (Python) |
| LLM | openai/gpt-oss-120b via Groq API |
| Embeddings | scikit-learn TF-IDF + TruncatedSVD (256-dim, no PyTorch) |
| Vector search | Pure numpy dot-product cosine similarity |
| Keyword search | BM25Okapi (rank-bm25) |
| Hybrid fusion | Reciprocal Rank Fusion (RRF k=60) |
| Document parsing | python-docx, pdfplumber |
| Data | pandas, synthetic CSV (500 customers) |
| Safety | Custom Python guardrails (regex, no LLM) |

**Important:** The embedding backend uses scikit-learn TF-IDF + SVD — NOT sentence-transformers or fastembed. This was done because the EXL sandbox blocks large model downloads and PyTorch DLLs are incompatible with Python 3.14. Do not suggest switching back to sentence-transformers.

---

## Project Folder Structure

```
SOP Chat bot/                        ← project root (all paths relative to here)
├── chatbot/
│   └── app.py                       ← main Streamlit app (2 tabs)
├── agents/
│   ├── __init__.py
│   ├── guardrails.py                ← v3.0: code-level safety layer
│   ├── sop_retriever.py             ← public RAG API (hybrid search + guardrails)
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── chunker.py               ← section-aware document chunking
│   │   ├── embedder.py              ← TF-IDF + SVD embeddings
│   │   ├── faiss_index.py           ← numpy cosine similarity search
│   │   ├── bm25_index.py            ← BM25 keyword search
│   │   ├── hybrid_search.py         ← RRF fusion
│   │   └── indexer.py               ← orchestrates build/load of all indexes
│   ├── portfolio_risk_agent.py      ← 5-factor churn scoring engine
│   ├── retention_offer_agent.py     ← personalized offer generator
│   ├── router.py                    ← classifies questions to agent type
│   ├── guidance_agent.py            ← process/steps questions
│   ├── escalation_agent.py          ← contacts/ownership questions
│   ├── compliance_agent.py          ← regulatory questions
│   ├── email_agent.py               ← email drafting
│   ├── confidence_agent.py          ← grounding-based confidence scoring
│   ├── multi_sop_agent.py           ← delegates to sop_retriever
│   └── sop_watcher.py               ← file change detection
├── scripts/
│   ├── generate_portfolio.py        ← creates data/loan_portfolio.csv
│   └── create_sops.py               ← creates data/*.docx SOP files
├── data/                            ← auto-created at runtime
│   ├── loan_portfolio.csv           ← 500 synthetic customers
│   ├── competitor_rates.csv         ← 3 competitor banks
│   ├── SOP_Bank_Rate_Change_Process.docx
│   ├── SOP_Loan_Origination_Underwriting.docx
│   ├── SOP_Wire_ACH_Payment_Processing.docx
│   ├── SOP_KYC_AML_Compliance.docx
│   └── SOP_Core_Banking_EOD_Processing.docx
├── run.bat                          ← one-click launcher
├── requirements.txt
├── README.md
└── PITCH_SCRIPT.txt
```

---

## Key Architecture Decisions (don't change these without understanding why)

**1. Working directory always set in app.py**
At the top of `chatbot/app.py`, `os.chdir(_PROJECT_ROOT)` forces the working directory to the project root. All relative paths (`data/`, `agents/`) depend on this. Do not remove it.

**2. Torch blocker in app.py**
A `_TorchBlocker` meta path hook intercepts any `import torch` before the DLL loads. This is required because torch 2.x is installed but incompatible with Python 3.14 on this machine. Do not remove it.

**3. Embeddings are TF-IDF + SVD, not neural**
`agents/retrieval/embedder.py` uses scikit-learn. It fits the vectorizer during index build (`encode_chunks()`) and saves it to `data/sop_vectorizer.pkl`. At query time (`encode_query()`), it loads the saved vectorizer. If you rebuild the index, the vectorizer is automatically refitted.

**4. FAISS replaced with numpy**
`agents/retrieval/faiss_index.py` uses `numpy` matrix multiplication for cosine similarity. The "index" is just a numpy array saved to `data/sop_vectors.npy`. No faiss-cpu is installed.

**5. Guardrails are code, not prompts**
`agents/guardrails.py` runs `check_input()` before every LLM call and `check_output()` after. These use regex patterns — no LLM involvement. The guardrails in `sop_retriever.py` (API layer) and `app.py` (UI layer) provide defense in depth.

**6. Churn scoring is rule-based**
`portfolio_risk_agent.py` uses a weighted formula — not ML. Weights: rate_gap=35%, balance=25%, months_remaining=20%, FICO=15%, payment_history=5%.

---

## How Each Tab Works

### Tab 1 — Rate Change Intelligence
1. User enters basis points (e.g. 25 = +0.25%) and effective date
2. `portfolio_risk_agent.score_portfolio(bps)` reads `data/loan_portfolio.csv` and `data/competitor_rates.csv`, scores all 500 customers
3. Dashboard shows KPI cards, two charts, ranked call list with CSV download
4. Selecting a customer calls `retention_offer_agent.generate()` which reads the rate change SOP and generates a personalized offer via Groq

### Tab 2 — SOP Assistant
1. User types a question
2. `guardrails.check_input()` runs — rejects injection attempts and PII
3. `router.route()` classifies: guidance / escalation / compliance / email / general
4. For email: retrieves SOP chunks, drafts email via `email_agent.ask()`
5. For all others: `multi_sop_agent.ask()` → `sop_retriever.ask()`:
   - `embedder.encode_query()` → TF-IDF transform
   - `faiss_index.search()` → top-20 by cosine similarity
   - `bm25_index.search()` → top-20 by keyword match
   - `hybrid_search()` → RRF → top-5 chunks
   - Guardrail: if top cosine_sim < 0.25 → return "not in SOP", no LLM call
   - LLM generates answer from top-5 chunk context
   - `guardrails.check_output()` → PII redaction, length cap, hard-block check
6. `confidence_agent.score()` → 60% retrieval similarity + 40% LLM self-score
7. Answer displayed with expandable citations and confidence badge

---

## How to Extend This Project

### Add a new SOP document
Drop any `.docx` or `.pdf` into the `data/` folder. The watcher in `sop_watcher.py` detects the change and `sop_retriever.rebuild()` is called automatically on the next app load.

### Add a new agent type
1. Create `agents/new_agent.py` with an `ask(question, history, context, client)` function
2. Add the new type to `agents/router.py` classification logic
3. Add a branch in `chatbot/app.py` Tab 2 message processing block
4. Add to `AGENT_INFO` dict in `app.py`

### Change the churn scoring weights
Edit the `WEIGHTS` dict in `agents/portfolio_risk_agent.py`. Must sum to 100.

### Change the similarity threshold
Edit `SIMILARITY_THRESHOLD = 0.25` in `agents/sop_retriever.py`. Lower = more answers but less accurate. Higher = stricter guardrail.

### Add a new guardrail pattern
Add a regex string to `_INJECTION_PATTERNS` list in `agents/guardrails.py`.

### Switch to a different LLM model
Change `MODEL = "openai/gpt-oss-120b"` in each agent file. The Groq client interface is standard — any Groq-supported model works.

---

## Common Tasks to Ask an AI Assistant

**To tweak the UI:**
"Here is my Streamlit app.py. I want to [change X]. The working directory is always the project root. Tab 1 is the dashboard, Tab 2 is the SOP chatbot. Don't touch Tab 1 when modifying Tab 2."

**To add a feature:**
"I have an agentic banking app. The architecture is [paste structure above]. I want to add [feature]. Which file should I modify and what should I change?"

**To create documentation:**
"Here is the complete architecture of my app [paste above]. Create a [one-pager / technical spec / API reference / user guide] for this system."

**To debug an error:**
"I'm running a Streamlit app with the following architecture [paste above]. I'm getting this error: [paste error]. The working directory is always set to project root in app.py."

**To write tests:**
"Here is my project structure [paste above]. Write pytest unit tests for [agents/guardrails.py / portfolio_risk_agent.py / embedder.py]. The app runs from project root."
