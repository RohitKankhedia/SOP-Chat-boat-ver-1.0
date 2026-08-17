# 🏦 Agentic Rate Change Intelligence & Customer Retention System
### v2.0 — Grounded Intelligence Edition

> **EXL Hackathon 2026** · Built on EXL Agentic AI Sandbox · By Rohit Kankhedia

An enterprise-grade agentic AI system that identifies banking customers at risk of churning after a Fed rate change — and hands relationship managers a personalized, SOP-compliant retention playbook in under 3 minutes.

---

## 🆕 What's New in v3.0 — Guardrails Edition

Version 1 proved the concept. Version 2 added real RAG retrieval. Version 3 adds a production-grade safety layer enforced entirely in Python — independent of the LLM.

**v3.0 additions:**

| # | What changed | Why it matters |
|---|---|---|
| **7** | **Input-side prompt injection detection** — regex patterns block "ignore previous instructions", persona injection, system prompt extraction, jailbreak keywords, prompt delimiter injection before anything reaches the LLM | v2 relied on the system prompt saying "answer only from SOP." A determined user could override that. v3 blocks it in Python before the LLM sees the message |
| **8** | **Output-side hard-block** — retrieval confidence is checked again AFTER the LLM answers; if it's below threshold, the LLM's response is discarded and the "not covered in SOP" message is forced | v2 prevented the LLM call if retrieval failed, but a race condition or code path change could bypass it. v3 checks on both sides |
| **9** | **PII redaction** — SSNs, card numbers, account numbers, routing numbers, phone numbers, emails are regex-scrubbed from all LLM output before it reaches the UI | Protects against SOP documents or user questions that contain real customer data leaking into displayed answers |
| **10** | **Response sanitization** — control characters, `<script>` tags, `javascript:` URLs stripped from all output; hard length cap at 4,000 characters | Prevents XSS in the Streamlit markdown renderer; stops runaway LLM responses |
| **11** | **Input PII detection** — if the user's question contains what looks like a SSN, card number, or account number, it's blocked with an explanation before reaching the LLM | Users sometimes think the chatbot can look up their account; this protects them from sending real financial data |

**v2.0 additions (still active):**

| # | What changed | Why it matters |
|---|---|---|
| **1** | **Real RAG retrieval** — SOP docs are chunked (280 tokens, section-aware), embedded with `BAAI/bge-small-en-v1.5`, and indexed via FAISS + BM25 | v1 dumped entire SOP files into the LLM (20K+ tokens of noise). v2 sends only the 5 most relevant excerpts |
| **2** | **Chunk-level citations** — every answer shows which section of which SOP it came from, with % similarity score | v1 only showed a filename. v2 shows "SOP_Rate_Change.docx → Section 5: Retention Actions (87% match)" |
| **3** | **Grounding-based confidence** — confidence score is 60% retrieval similarity + 40% LLM self-assessment | v1 asked the LLM to rate its own answer 1–10 (hallucination-prone). v2 uses an objective retrieval signal as the primary signal |
| **4** | **Code-level guardrail** — if retrieval finds no chunk above 25% similarity, the LLM is never called at all | v1 relied entirely on prompting. v2 enforces this in Python |
| **5** | **Multi-file SOP watching** — watcher now scans all files in `data/`, rebuilds index when any file changes | v1 hardcoded a single file path |
| **6** | **Graceful degradation** — if the Groq API is unavailable, the app returns the best-matching SOP excerpt verbatim instead of crashing | v1 showed a raw Python exception |

> **Hybrid search (FAISS + BM25 → Reciprocal Rank Fusion):**
> Vector similarity catches semantic matches ("who approves rate changes?" → finds "CLO signs off").
> BM25 catches exact term matches ("Reg Z", "MLA", "ECOA", step numbers).
> RRF fuses both rankings — best of both worlds, no score normalization needed.

---

## 🚨 The Problem

Every Fed rate change triggers a silent crisis at banks:

- Customers quietly evaluate refinancing with competitors
- Relationship managers spend **2 days manually** building call lists
- By the time they act, customers are already pre-approved elsewhere
- A mid-size bank with $500M in auto loans loses **~$15M per rate cycle** to churn
- No intelligent prioritization. No personalized retention strategy.

---

## ✅ The Solution

**Rate Change Intelligence** — AI that does in 3 minutes what takes 2 days:

1. Ops team enters the Fed rate change (e.g. +25bps, effective June 20)
2. AI scans the entire loan portfolio and scores every customer on churn risk (0–100)
3. Generates a prioritized call list ranked by who is most likely to leave
4. Creates a personalized AI retention offer per customer — grounded in the bank's own SOP
5. Validates every offer against SOP compliance rules via grounded retrieval

**Business Impact:**
- 🔴 Identify top at-risk customers before they leave
- 💰 Recover $750K per rate event by retaining 50% of high-risk customers
- ⏱️ Save 2 days of manual work per rate change
- 📋 Every action grounded in and auditable against bank SOPs

---

## 🏗️ System Architecture

```
Fed Rate Change Announced
         │
         ▼
┌─────────────────────────┐
│   Rate Change Input     │  ← Ops team enters bps + effective date
└────────────┬────────────┘
             │
    ┌────────▼──────────┐
    │  Portfolio Risk   │  ← Scores 500+ customers on churn risk
    │  Scorer Agent     │    5 factors: rate gap, balance, months,
    └────────┬──────────┘    FICO, payment history
             │
    ┌────────▼──────────┐
    │  Competitor Gap   │  ← Compares bank rates vs 3 competitors
    │  Analyzer         │    Identifies dangerous rate gaps
    └────────┬──────────┘
             │
    ┌────────▼──────────┐
    │  Retention Offer  │  ← Generates personalized offer per customer
    │  Generator Agent  │    Grounded in rate change SOP rules
    └────────┬──────────┘
             │
    ┌────────▼──────────────────────────────────┐
    │  SOP Intelligence Assistant (v2.0)         │
    │                                            │
    │  Query → Embed (BGE-small-en-v1.5)        │
    │       → FAISS top-20 (vector)             │
    │       → BM25 top-20 (keyword)             │
    │       → RRF → top-5 chunks                │
    │       → Guardrail (sim < 0.25 → no LLM)  │
    │       → Groq LLaMA 3.3 70B               │
    │       → Answer + section citations        │
    └───────────────────────────────────────────┘
             │
             ▼
  📊 Streamlit Dashboard
  Priority call list + personalized scripts + grounded citations
```

---

## 📊 Churn Risk Scoring Model

| Factor | Weight | Logic |
|---|---|---|
| Rate Gap vs Competitor | 35% | Higher gap = customer has more incentive to leave |
| Loan Balance | 25% | Larger balance = bigger monthly savings from refinancing |
| Months Remaining | 20% | More time left = more total savings possible |
| FICO Score | 15% | Better credit = more options at competitor banks |
| Payment History | 5% | Missed payments reduce ability to refinance elsewhere |

---

## 🧠 RAG Retrieval Pipeline (v2.0)

```
INGESTION (at startup + on file change)
  data/*.docx / data/*.pdf
      │
      ▼ chunker.py
  Chunks (max 280 tokens, section-aware, 30-word overlap)
  Each chunk carries: source_file, section_heading, char_start
      │
      ▼ embedder.py (BAAI/bge-small-en-v1.5, 384-dim, local)
  L2-normalized embeddings
      │
      ├──► faiss_index.py  → data/sop.faiss + data/sop_chunks.json
      └──► bm25_index.py   → data/sop_bm25.pkl

QUERY PATH (per user question)
  Question
      │
      ├──► FAISS top-20 (cosine similarity)
      └──► BM25 top-20  (keyword match)
              │
              ▼ hybrid_search.py (RRF k=60)
          Top-5 chunks
              │
              ▼ Guardrail (max cosine_sim < 0.25?)
          YES → "Not covered in SOP" (no LLM call)
          NO  → Groq LLaMA 3.3 70B
              │
              ▼ Graceful degradation
          API fails → return best chunk verbatim
              │
              ▼
  Answer + chunk-level citations + grounding confidence score
```

---

## 🖥️ Application Screens

| Tab | What you see |
|---|---|
| **Rate Change Intelligence** | Input rate change → KPI cards → risk charts → priority call list → AI retention offer per customer |
| **SOP Assistant (v2.0)** | Hybrid RAG chatbot — answers from top-5 relevant SOP excerpts, shows section-level citations and grounding confidence |

---

## 📂 Project Structure

```
agentic-sop-assistant/
├── data/
│   ├── loan_portfolio.csv                      ← 500 synthetic customer records
│   ├── competitor_rates.csv                    ← Competitor rate table (3 banks)
│   ├── sop.faiss                               ← FAISS vector index (built at startup)
│   ├── sop_chunks.json                         ← Chunk metadata
│   ├── sop_bm25.pkl                            ← BM25 keyword index
│   ├── SOP_Bank_Rate_Change_Process.docx
│   ├── SOP_Loan_Origination_Underwriting.docx
│   ├── SOP_Wire_ACH_Payment_Processing.docx
│   ├── SOP_KYC_AML_Compliance.docx
│   └── SOP_Core_Banking_EOD_Processing.docx
├── agents/
│   ├── retrieval/                              ← NEW in v2.0
│   │   ├── chunker.py                          ← Section-aware document chunking
│   │   ├── embedder.py                         ← BAAI/bge-small-en-v1.5 wrapper
│   │   ├── faiss_index.py                      ← Vector index build + search
│   │   ├── bm25_index.py                       ← Keyword index build + search
│   │   ├── hybrid_search.py                    ← RRF fusion
│   │   └── indexer.py                          ← Orchestrates full ingestion pipeline
│   ├── guardrails.py                           ← NEW in v3.0: input/output safety layer
│   ├── sop_retriever.py                        ← public RAG API + retrieval guardrail
│   ├── portfolio_risk_agent.py                 ← Churn scoring engine
│   ├── retention_offer_agent.py                ← Personalized offer generator
│   ├── router.py                               ← Question classifier
│   ├── guidance_agent.py                       ← Process & steps
│   ├── escalation_agent.py                     ← Contacts & escalation
│   ├── compliance_agent.py                     ← Regulatory compliance
│   ├── confidence_agent.py                     ← UPDATED: grounding-based scoring
│   ├── email_agent.py                          ← Email drafting
│   ├── multi_sop_agent.py                      ← UPDATED: delegates to sop_retriever
│   └── sop_watcher.py                          ← UPDATED: watches all files
├── chatbot/
│   └── app.py                                  ← UPDATED: v2.0 citation display
├── scripts/
│   ├── generate_portfolio.py
│   ├── read_sop.py
│   └── create_sops.py
├── README.md
├── PITCH_SCRIPT.txt
├── RAG_UPGRADE_PLAN.md
└── requirements.txt
```

---

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/RohitKankhedia/agentic-sop-assistant.git
cd agentic-sop-assistant
```

### 2. Install dependencies
```powershell
& C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe -m pip install `
  python-docx groq streamlit pandas `
  sentence-transformers faiss-cpu rank-bm25 pdfplumber
```

### 3. Generate portfolio data and SOP documents
```powershell
& python.exe scripts/create_sops.py
& python.exe scripts/generate_portfolio.py
```

### 4. Set your Groq API key
```powershell
$env:GROQ_API_KEY = "gsk_your-key-here"
```

### 5. Run the app
```powershell
& python.exe -m streamlit run chatbot/app.py
```

> **First run:** The app will build the RAG index on startup (~20–30 seconds for 5 SOPs). After that it loads from cache in under 1 second. You'll see the spinner: "📚 Indexing SOP documents..."

Open http://localhost:8501

---

## 💡 Demo Flow

1. Open **Tab 1 — Rate Change Intelligence**
2. Enter `25` in the rate change box (+0.25%)
3. Click **Run Churn Analysis**
4. See: customers at risk, total at-risk balance, estimated loss
5. Browse the **priority call list** — download as CSV
6. Select a high-risk customer → **Generate Retention Offer**
7. Switch to **Tab 2 — SOP Assistant**
8. Ask: *"Who approves rate changes?"*
9. See: answer + expandable citations showing which SOP section matched and at what % similarity

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| LLM Inference | LLaMA 3.3 70B via Groq (free tier) |
| Embedding Model | BAAI/bge-small-en-v1.5 (local, 384-dim, free) |
| Vector Index | FAISS IndexFlatIP (exact cosine similarity) |
| Keyword Index | BM25Okapi (rank-bm25) |
| Hybrid Fusion | Reciprocal Rank Fusion (RRF k=60) |
| Document Chunking | python-docx + pdfplumber (section-aware, token-bounded) |
| Churn Scoring | Python + Pandas (weighted rule-based model) |
| Web Dashboard | Streamlit |
| Agent Orchestration | Custom Python multi-agent router |
| Data | Synthetic loan portfolio (500 customers, ~$132M balance) |

---

## 📈 Business Impact Summary

| Metric | Value |
|---|---|
| Portfolio scanned | 500 customers / ~$132M balance |
| Time to generate call list | < 3 minutes (vs 2 days manually) |
| Estimated loss per rate cycle (no action) | ~$15M on $500M portfolio |
| Recoverable with AI intervention | $750K–$4.5M per year |
| SOP documents loaded | 5 (Rate Change, Loan Origination, Wire/ACH, KYC/AML, EOD) |
| SOP chunk retrieval | Top-5 relevant excerpts per query (not whole files) |
| Answer guardrail | No LLM call if cosine similarity < 25% — forced "not in SOP" |

---

## 🔄 Changelog

### v3.0 — Guardrails Edition (EXL Hackathon 2026, Final)
- Added `agents/guardrails.py`: all checks are regex/rule-based Python, no LLM involvement
- Input: prompt injection detection (25+ patterns: instruction override, persona injection, delimiter attacks, jailbreak keywords)
- Input: PII detection blocks user questions containing SSN, card numbers, account numbers
- Input: length gate (max 2,000 chars per question)
- Output: retrieval hard-block — LLM answer discarded if retrieval confidence < 25%, even if LLM was called
- Output: PII redaction — SSN, card, account, routing, phone, email scrubbed from all responses
- Output: HTML/script injection stripping + control-character sanitization
- Output: 4,000-character response length cap with truncation notice
- Guardrails enforced at two layers (sop_retriever.py + app.py) for defense in depth

### v2.0 — Grounded Intelligence Edition (EXL Hackathon 2026)
- Added hybrid RAG retrieval: chunking + FAISS + BM25 + RRF
- Added chunk-level citations with section headings and similarity %
- Confidence score now 60% retrieval-grounded + 40% LLM self-assessment
- Added code-level guardrail: LLM never called if no relevant chunk found
- SOP watcher now monitors all files in data/ (not one hardcoded path)
- Added graceful degradation: LLM failure returns best chunk verbatim
- Added PDF support via pdfplumber (+ optional OCR via pytesseract)

### v1.0 — Proof of Concept (EXL Hackathon 2026, Initial)
- Multi-agent SOP chatbot (guidance, escalation, compliance, email, general)
- Rate Change Intelligence dashboard with churn scoring
- Personalized retention offer generator
- 5-factor weighted churn model (rate gap, balance, months, FICO, payments)

---

## 🔮 Future Enhancements

- [ ] Live competitor rate feed via API
- [ ] Integration with core banking system (FiServ/Jack Henry) for real portfolio data
- [ ] CRM integration (Salesforce) to push call list directly to relationship managers
- [ ] Historical churn data to train a supervised ML model on top of the rule-based scorer
- [ ] Multi-bank deployment with bank-specific SOP and rate configuration
- [ ] Mobile app for relationship managers to access retention offers on the go

---

## 👤 Author

**Rohit Kankhedia**
EXL Hackathon 2026 · EXL Agentic AI Sandbox (Nuvepro)
GitHub: https://github.com/RohitKankhedia/agentic-sop-assistant
