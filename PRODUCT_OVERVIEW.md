# Product Overview — Agentic Rate Change Intelligence System
### v3.0 Guardrails Edition | EXL Hackathon 2026

---

## What Is This Product?

A two-tab AI-powered web application for banking operations teams. When the Federal Reserve changes interest rates, it identifies which customers are most likely to refinance with a competitor and generates personalized retention offers — all grounded in the bank's own policy documents. What previously took relationship managers 2 days of manual spreadsheet work now takes 3 minutes.

**Business impact:** A mid-size bank with $500M in auto loans loses ~$15M per rate cycle to silent churn. This system recovers $750K per rate event by retaining the highest-risk customers before they leave.

---

## Tab 1 — Rate Change Intelligence Dashboard

### Input
- Fed rate change in basis points (e.g. 25 = +0.25%)
- Effective date

### Churn Risk Scoring
- Scores all 500 loan customers from 0 to 100
- Five-factor weighted model:

| Factor | Weight | Why |
|---|---|---|
| Rate gap vs competitor | 35% | Biggest incentive to leave |
| Loan balance | 25% | Higher balance = bigger monthly savings |
| Months remaining | 20% | More time left = more total savings |
| FICO score | 15% | Better credit = more refinancing options |
| Payment history | 5% | Missed payments reduce refi ability |

- Categories: 🔴 High Risk / 🟡 Medium Risk / 🟢 Low Risk

### KPI Dashboard (5 cards)
- Total customers in portfolio
- Number of high-risk customers + % of portfolio
- Number of medium-risk customers
- Total at-risk loan balance ($)
- Estimated loss if no action + recoverable amount

### Charts
- Risk distribution by product type (bar chart)
- Churn score distribution histogram

### Priority Call List
- Filterable by product (Indirect Auto / Direct Auto / Business Banking)
- Filterable by risk level
- Ranked table: customer name, credit tier, FICO, balance, rate gap, churn score, relationship manager
- Download as CSV — ready to import into any CRM

### AI Retention Offer Generator
- Select any high-risk customer
- AI reads their full profile (balance, rate, FICO, competitor gap)
- Generates personalized talking points grounded in bank SOP policy
- Tells the relationship manager: what to offer, whether manager approval is needed, which policy section it's based on

---

## Tab 2 — SOP Intelligence Assistant

### What It Does
Answers questions from the bank's own Standard Operating Procedure documents. Not Google. Not general AI knowledge. Only the bank's own policies — with citations showing exactly which document and section was used.

### 5 Specialist Agents (auto-routed)

| Agent | Handles |
|---|---|
| 📋 Task Guidance | Step-by-step process questions ("How do I notify dealers?") |
| 📞 Escalation & Ownership | Who to contact, approval chains ("Who approves rate changes?") |
| ⚖️ Compliance | Regulatory questions (Reg Z, MLA, ECOA, retention periods) |
| ✉️ Email Drafting | Writes professional emails (dealer notifications, IT escalations) |
| 🤖 SOP General | Everything else — full RAG retrieval from all 5 SOPs |

### RAG Retrieval Pipeline
1. SOP documents chunked into 280-token sections with section headings tracked
2. TF-IDF + SVD embeddings (256-dim, no PyTorch required)
3. FAISS-equivalent numpy cosine similarity search → top-20 candidates
4. BM25 keyword search → top-20 candidates
5. Reciprocal Rank Fusion (RRF) combines both → top-5 best chunks
6. Top-5 chunks sent to LLM as context (not the whole document)

### Citation Display
Every answer shows an expandable panel with:
- Source file name
- Section heading
- % similarity match
- Text preview of the matched excerpt

### Confidence Scoring
- **High** (8–10/10): Strong retrieval match + LLM confirms
- **Medium** (5–7/10): Partial match
- **Low** (1–4/10): Weak retrieval, treat with caution

Scoring formula: 60% retrieval cosine similarity + 40% LLM self-assessment

### SOP Documents Loaded (5 files)
1. SOP_Bank_Rate_Change_Process.docx
2. SOP_Loan_Origination_Underwriting.docx
3. SOP_Wire_ACH_Payment_Processing.docx
4. SOP_KYC_AML_Compliance.docx
5. SOP_Core_Banking_EOD_Processing.docx

---

## v3.0 Guardrails Layer (Safety)

All checks are pure Python code — independent of the LLM. Cannot be bypassed by prompt engineering.

### Input Side (before LLM sees anything)
| Check | What it catches |
|---|---|
| Prompt injection | "ignore previous instructions", "act as", "you are now", "DAN", jailbreak strings, `[INST]` delimiters |
| PII detection | Questions containing SSN, card numbers, account numbers |
| Length gate | Questions over 2,000 characters |

### Output Side (before user sees anything)
| Check | What it does |
|---|---|
| Retrieval hard-block | If cosine similarity < 25%, LLM answer is discarded and "not in SOP" is forced |
| PII redaction | SSN, card, routing, account, phone, email scrubbed from all responses |
| HTML sanitization | `<script>` tags and `javascript:` URLs stripped |
| Length cap | Responses truncated at 4,000 characters |

---

## Version History

| Version | Name | Key Addition |
|---|---|---|
| v1.0 | Proof of Concept | Multi-agent chatbot + rate change dashboard |
| v2.0 | Grounded Intelligence Edition | Real RAG retrieval, chunk citations, confidence scoring |
| v3.0 | Guardrails Edition | Code-level input/output safety, PII redaction, injection detection |
