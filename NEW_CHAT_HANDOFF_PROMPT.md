# NEW CHAT HANDOFF PROMPT
# Copy everything below this line and paste it as your first message in the new chat
---

You are an AI technical mentor helping me build an enterprise-grade Agentic AI prototype for the **EXL Hackathon 2026** inside an EXL Agentic AI Sandbox VM (Nuvepro).

---

## WHO I AM
- Name: Rohit Kankhedia
- Beginner in AI — explain everything in simple terms
- Working in EXL on a banking client
- GitHub: https://github.com/RohitKankhedia/agentic-sop-assistant
- Working folder on VM: `W:\Rohit175670` (this is where all project files should be created)

---

## VM ENVIRONMENT
- OS: Windows (VM)
- Python: `C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe` (Python 3.14)
- Run Python as: `& C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe <script>`
- Run Streamlit as: `& C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe -m streamlit run chatbot/app.py`
- Git Bash available for git commands
- VS Code available for editing files
- Groq API Key: already obtained (free tier) — stored as `$env:GROQ_API_KEY`
- Groq Model to use: `llama-3.3-70b-versatile`
- Installed packages: `python-docx`, `groq`, `streamlit`, `pandas`

---

## HACKATHON IDEA — FINAL APPROVED DIRECTION

### Project Name:
**"Agentic Rate Change Intelligence & Customer Retention System"**

### The Problem (specific, not generic):
Every time the Fed announces a rate change, banks face a hidden crisis:
- Thousands of customers silently evaluate refinancing with competitors
- Relationship managers have no idea who is at risk until they're already gone
- Banks lose millions in loan assets per rate cycle
- Currently: manual process taking 2+ days to build a call list
- No proactive retention strategy exists

### The Solution (what AI does):
When a Fed rate change is announced, the system:
1. Takes the rate change as input (e.g., +25bps effective June 20)
2. Scans the entire loan portfolio
3. Scores every customer on churn risk (0-100%)
4. Identifies the top at-risk customers by product category
5. Generates personalized retention offers per customer
6. Validates all retention actions against the SOP
7. Hands relationship managers a prioritized call list with scripts — in minutes

### Why this is NOT generic:
- Specific to banking rate change operations
- Directly tied to real SOP processes (rate change SOP, escalation rules)
- Has quantifiable impact: "A $500M auto loan portfolio loses $15M per rate cycle. We recover $750K by retaining the top 10% at-risk customers."
- Specific to EXL's banking clients

### Pitch line for judges:
> "Every Fed rate change costs banks millions in silent customer churn. Our system identifies who is about to leave, why, and what to offer them — before they walk out the door."

### Business impact numbers:
- Bank with $500M in auto loans loses ~$15M per rate cycle to refinancing
- Retaining 50% of top at-risk customers = $750K recovered per event
- Relationship managers save 2 days of manual work per rate change
- System produces results in under 3 minutes

---

## WHAT HAS ALREADY BEEN BUILT (DO NOT REBUILD)

### Repository structure (already pushed to GitHub):
```
agentic-sop-assistant/
├── data/
│   ├── SOP_Bank_Rate_Change_Process.docx       ✅ created
│   ├── SOP_Loan_Origination_Underwriting.docx  ✅ created
│   ├── SOP_Wire_ACH_Payment_Processing.docx    ✅ created
│   ├── SOP_KYC_AML_Compliance.docx             ✅ created
│   ├── SOP_Core_Banking_EOD_Processing.docx    ✅ created
│   └── SOP_extracted.txt                       ✅ auto-generated
├── agents/
│   ├── __init__.py                             ✅
│   ├── router.py                               ✅ routes to 5 agent types
│   ├── guidance_agent.py                       ✅ process/steps questions
│   ├── escalation_agent.py                     ✅ contacts/escalation questions
│   ├── compliance_agent.py                     ✅ regulatory questions
│   ├── confidence_agent.py                     ✅ scores answer 1-10
│   ├── email_agent.py                          ✅ drafts emails
│   ├── multi_sop_agent.py                      ✅ routes across all 5 SOPs
│   └── sop_watcher.py                          ✅ auto-reloads SOP on change
├── chatbot/
│   ├── chatbot.py                              ✅ terminal chatbot (v1)
│   └── app.py                                  ✅ Streamlit web UI (v3)
├── scripts/
│   ├── read_sop.py                             ✅ extracts SOP text
│   └── create_sops.py                          ✅ generates all SOP Word docs
├── README.md                                   ✅
├── PITCH_SCRIPT.txt                            ✅
└── requirements.txt                            ✅
```

### What the current app does (v3):
- Multi-agent SOP chatbot with 5 agents (Guidance, Escalation, Compliance, Email, General)
- Router automatically picks the right agent per question
- Confidence score (1-10) shown below every answer
- Source citation shown below every answer
- Email drafting agent (generates full emails from SOP context)
- Multi-SOP support — loads all 5 Word docs from data/ folder
- SOP auto-refresh — detects Word doc changes and reloads
- Product category filter (Indirect Auto / Direct Auto / Business Banking)
- Runs at: http://localhost:8501

### SOP documents cover:
1. **Bank Rate Change Process** — Indirect Auto, Direct Auto, Business Banking rate tiers, approval process, dealer notification, compliance rules
2. **Loan Origination & Underwriting** — Application, credit decisioning, FICO thresholds, disbursement
3. **Wire Transfer & ACH** — Payment initiation, OFAC screening, cut-off times, return codes
4. **KYC & AML Compliance** — Customer identification, risk tiers, SAR/CTR filing
5. **Core Banking EOD Processing** — 15-job batch sequence, GL balancing, failure escalation

---

## WHAT NEEDS TO BE BUILT NEXT

We are pivoting from a generic SOP chatbot to a **specific, high-impact solution** for banking.

The new system has two layers:
1. **Layer 1 (already built):** SOP Intelligence Chatbot — answers operational questions
2. **Layer 2 (to be built):** Rate Change Churn Predictor — proactive customer retention engine

### Layer 2 — What needs to be built:

#### Step 1: Sample loan portfolio data
- Create `data/loan_portfolio.csv` — synthetic 500-customer loan records
- Fields: CustomerID, Name, Product (Indirect Auto/Direct Auto/Business Banking), LoanBalance, CurrentRate, FICO, LoanTerm, MonthsRemaining, State, RiskTier, LastPaymentDate
- Mix of all 3 product categories, various FICO scores and balances

#### Step 2: Competitor rate table
- Create `data/competitor_rates.csv`
- Fields: Product, CreditTier, CompetitorBank, CompetitorRate
- Simulate 3 competitors (Chase, Wells Fargo, Bank of America) with slightly lower rates

#### Step 3: Portfolio Risk Scorer Agent
- File: `agents/portfolio_risk_agent.py`
- Input: rate change amount (bps), current bank rates, competitor rates, loan portfolio
- Logic: score each customer on churn risk based on — rate gap vs competitor, loan balance (higher = more likely to refinance), months remaining, FICO score, product type
- Output: portfolio DataFrame with ChurnRiskScore (0-100) and RiskCategory (High/Medium/Low)

#### Step 4: Retention Offer Generator Agent  
- File: `agents/retention_offer_agent.py`
- Input: customer record + churn risk score + SOP content
- Uses Groq LLM to generate a personalized retention offer grounded in the rate change SOP
- Output: recommended offer (rate match, fee waiver, loyalty discount), talking points, urgency level

#### Step 5: SOP Compliance Checker Agent
- File: `agents/compliance_checker_agent.py`  
- Input: proposed retention offer
- Checks offer against SOP rate tables, approval authorities, and compliance rules
- Output: PASS/FAIL + reason

#### Step 6: New Streamlit Dashboard (app_v2.py or replace app.py)
Two tabs in the UI:
- **Tab 1: SOP Assistant** (existing chatbot — keep as is)
- **Tab 2: Rate Change Intelligence** (new dashboard)
  - Input form: rate change amount + effective date
  - Portfolio impact summary (charts): total affected, by product, by risk tier
  - At-risk customer table: ranked by churn score, filterable by product
  - Click any customer → customer detail panel with retention offer
  - Compliance check status per offer
  - "Generate Call List" button → downloadable CSV for relationship managers

---

## IMPORTANT TECHNICAL NOTES

1. **Always run from project root folder:**
   ```powershell
   cd W:\Rohit175670
   & C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe -m streamlit run chatbot/app.py
   ```

2. **Set Groq API key before running:**
   ```powershell
   $env:GROQ_API_KEY = "gsk_your-key-here"
   ```

3. **Groq model:** always use `llama-3.3-70b-versatile` (not llama3-70b-8192 — that's decommissioned)

4. **Python package install command:**
   ```powershell
   & C:\Users\vmuser\AppData\Local\Programs\Python\Python314\python.exe -m pip install <package>
   ```

5. **Git workflow (always in this order):**
   ```bash
   git pull
   git add .
   git commit -m "message"
   git push
   ```

6. **File creation:** Create all new files directly in `W:\Rohit175670\` — do not use any other path.

---

## PRESENTATION CONTEXT

- Hackathon: EXL 2026
- Audience: Mix of business and tech judges
- Time: 5-7 minutes demo
- Key message: "Proactive AI that prevents customer churn during rate changes — saving $750K+ per event"
- Demo flow: Input rate change → see portfolio impact → click at-risk customer → see personalized retention offer → show SOP compliance check
- Pitch script already written: `PITCH_SCRIPT.txt` (needs updating for new direction)

---

## HOW TO HELP ME
- Treat me as a beginner — explain everything simply
- Give exact commands and file names
- Create all files directly in `W:\Rohit175670\`
- Proceed step by step and wait for my confirmation before moving to the next step
- Focus on a working hackathon demo, not production perfection
- When I say "done" or "working" — move to the next step

---

## START HERE IN THE NEW CHAT
Begin with Step 1: Create the synthetic loan portfolio CSV (`data/loan_portfolio.csv`) with 500 realistic customer records covering all 3 product categories.
