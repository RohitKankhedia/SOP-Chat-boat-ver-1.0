"""
app.py  (v4 — Rate Change Intelligence + SOP Assistant)
--------------------------------------------------------
Tab 1: Rate Change Intelligence Dashboard (new)
Tab 2: SOP Intelligence Chatbot (existing)

Usage:
    streamlit run chatbot/app.py
"""

import os
import sys

# ── Block PyTorch before anything else loads ──────────────────────────────────
# torch 2.x DLL is incompatible with Python 3.14 on Windows (c10.dll crash).
# sentence-transformers (still installed) tries to import torch on load.
# This blocker intercepts that import at the Python level so the DLL
# is never touched. Our app uses scikit-learn for embeddings instead.
class _TorchBlocker:
    _BLOCKED = {"torch", "torchvision", "torchaudio", "torch._C"}
    def find_module(self, name, path=None):
        if name in self._BLOCKED or name.startswith("torch."):
            return self
    def load_module(self, name):
        import types
        mod = types.ModuleType(name)
        mod.__loader__ = self
        mod.__package__ = name
        mod.__spec__ = None
        sys.modules[name] = mod
        return mod

if not any(isinstance(h, _TorchBlocker) for h in sys.meta_path):
    sys.meta_path.insert(0, _TorchBlocker())
# ─────────────────────────────────────────────────────────────────────────────

# ── Fix working directory to project root ─────────────────────────────────────
# __file__ = chatbot/app.py  →  parent = chatbot/  →  parent = project root
# This ensures data/, agents/, scripts/ are always found regardless of how
# Streamlit was launched (double-click, bat file, terminal, different cwd).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_ROOT)
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
from groq import Groq

from agents import router, guidance_agent, escalation_agent, compliance_agent
from agents import confidence_agent, email_agent, multi_sop_agent
from agents import portfolio_risk_agent, retention_offer_agent
from agents.sop_watcher import (
    load_sop_text, check_and_reload,
    get_all_file_mtimes, check_and_reload_all,
)
import agents.sop_retriever as sop_retriever
import agents.guardrails as guardrails

MODEL = "openai/gpt-oss-120b"

AGENT_INFO = {
    "guidance":   {"label": "📋 Task Guidance Agent",          "color": "#1f77b4"},
    "escalation": {"label": "📞 Escalation & Ownership Agent", "color": "#d62728"},
    "compliance": {"label": "⚖️ Compliance Agent",             "color": "#2ca02c"},
    "email":      {"label": "✉️ Email Drafting Agent",          "color": "#9467bd"},
    "general":    {"label": "🤖 SOP General Agent",            "color": "#7f7f7f"},
}

# ── Page setup ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="EXL Banking AI — Rate Change Intelligence",
    page_icon="🏦",
    layout="wide"
)

# ── EXL Branding Header ────────────────────────────────────────────────
st.markdown("""
<div style='background: linear-gradient(90deg, #003087 0%, #0057B8 100%);
     padding: 12px 24px; border-radius: 8px; margin-bottom: 16px;
     display: flex; align-items: center; justify-content: space-between;'>
  <div>
    <span style='color: white; font-size: 1.4em; font-weight: 800;
          letter-spacing: 2px;'>EXL</span>
    <span style='color: #90CAF9; font-size: 0.9em; margin-left: 12px;'>
          Analytics · AI · Operations</span>
  </div>
  <div style='color: #90CAF9; font-size: 0.85em;'>
    🏦 Banking Client Solution &nbsp;|&nbsp; EXL Hackathon 2026
  </div>
</div>
""", unsafe_allow_html=True)

# ── Groq client ────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY not set. Run: $env:GROQ_API_KEY='your-key'")
        st.stop()
    return Groq(api_key=api_key)

client = get_client()

# ── SOP loading ────────────────────────────────────────────────────────
@st.cache_resource
def get_all_sops():
    return multi_sop_agent.load_all_sops()

all_sops = get_all_sops()

# ── RAG index initialization (runs once per session, rebuilds on SOP changes) ──
if "retriever_initialized" not in st.session_state:
    with st.spinner("📚 Indexing SOP documents — first run may take ~30s..."):
        sop_retriever.initialize()
    st.session_state.retriever_initialized = True
    st.session_state.index_mtimes = get_all_file_mtimes()
else:
    current_mtimes, changed = check_and_reload_all(
        st.session_state.get("index_mtimes", {})
    )
    if changed:
        with st.spinner("🔄 Re-indexing updated SOP documents..."):
            sop_retriever.rebuild()
        st.session_state.index_mtimes = current_mtimes
        st.cache_resource.clear()
        st.toast("📄 SOPs updated and re-indexed!", icon="🔄")

# ── Legacy SOP text for Tab 1 retention offer agent (full-file extraction) ────
if "sop_text" not in st.session_state or "sop_last_modified" not in st.session_state:
    sop_text, last_mod = load_sop_text()
    st.session_state.sop_text          = sop_text
    st.session_state.sop_last_modified = last_mod
else:
    new_mod, new_text = check_and_reload(st.session_state.sop_last_modified)
    if new_text:
        st.session_state.sop_text          = new_text
        st.session_state.sop_last_modified = new_mod

sop_text = st.session_state.sop_text

if "messages" not in st.session_state:
    st.session_state.messages = []

# ══════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════
tab1, tab2 = st.tabs([
    "📊 Rate Change Intelligence",
    "🤖 SOP Assistant"
])


# ══════════════════════════════════════════════════════════════════════
# TAB 1 — RATE CHANGE INTELLIGENCE DASHBOARD
# ══════════════════════════════════════════════════════════════════════
with tab1:
    st.title("📊 Rate Change Intelligence & Customer Retention")
    st.caption("Powered by EXL Agentic AI · Identifies at-risk customers before they leave")
    st.divider()

    # ── Input Panel ───────────────────────────────────────────────────
    col_in1, col_in2, col_in3 = st.columns([1, 1, 1])
    with col_in1:
        rate_change_bps = st.number_input(
            "Fed Rate Change (basis points)",
            min_value=-100, max_value=100, value=25, step=25,
            help="25 bps = +0.25%. Enter negative for a rate cut."
        )
    with col_in2:
        effective_date = st.date_input("Effective Date")
    with col_in3:
        st.write("")
        st.write("")
        run_analysis = st.button("🚀 Run Churn Analysis", use_container_width=True, type="primary")

    st.divider()

    # ── Run Analysis ──────────────────────────────────────────────────
    if run_analysis or "portfolio_scored" in st.session_state:

        if run_analysis:
            with st.spinner("Scanning 500 customer loan records..."):
                scored = portfolio_risk_agent.score_portfolio(rate_change_bps)
                summary = portfolio_risk_agent.get_summary(scored)
                st.session_state.portfolio_scored = scored
                st.session_state.portfolio_summary = summary
                st.session_state.rate_change_bps = rate_change_bps

        scored  = st.session_state.portfolio_scored
        summary = st.session_state.portfolio_summary
        bps     = st.session_state.rate_change_bps

        # ── KPI Cards ─────────────────────────────────────────────────
        st.subheader(f"Portfolio Impact — Fed Rate {'↑' if bps > 0 else '↓'} {abs(bps)}bps ({abs(bps/100):.2f}%)")

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Customers",   f"{summary['total_customers']:,}")
        k2.metric("🔴 High Risk",       f"{summary['high_risk']:,}",
                  f"{summary['high_risk']/summary['total_customers']*100:.0f}% of portfolio")
        k3.metric("🟡 Medium Risk",     f"{summary['medium_risk']:,}")
        k4.metric("💰 At-Risk Balance", f"${summary['at_risk_balance']/1e6:.1f}M")
        k5.metric("⚠️ Est. Loss if No Action", f"${summary['estimated_loss']/1e6:.1f}M",
                  f"Recoverable: ${summary['recoverable']/1e6:.1f}M",
                  delta_color="inverse")

        st.divider()

        # ── Charts Row ────────────────────────────────────────────────
        ch1, ch2 = st.columns(2)

        with ch1:
            st.subheader("Risk Distribution by Product")
            risk_product = scored.groupby(["Product", "RiskCategory"]).size().reset_index(name="Count")
            pivot = risk_product.pivot(index="Product", columns="RiskCategory", values="Count").fillna(0)
            st.bar_chart(pivot)

        with ch2:
            st.subheader("Churn Risk Score Distribution")
            bins = pd.cut(scored["ChurnRiskScore"], bins=[0,30,50,70,100],
                         labels=["Low (0-30)", "Medium (30-50)", "Medium-High (50-70)", "High (70-100)"])
            dist = bins.value_counts().sort_index()
            st.bar_chart(dist)

        st.divider()

        # ── At-Risk Customer Table ────────────────────────────────────
        st.subheader("🔴 Top At-Risk Customers — Priority Call List")

        col_f1, col_f2 = st.columns([1, 1])
        with col_f1:
            product_filter = st.selectbox(
                "Filter by Product",
                ["All Products", "Indirect Auto", "Direct Auto", "Business Banking"]
            )
        with col_f2:
            risk_filter = st.selectbox(
                "Filter by Risk",
                ["High Risk Only", "High + Medium Risk", "All Customers"]
            )

        # Apply filters
        display = scored.copy()
        if product_filter != "All Products":
            display = display[display["Product"] == product_filter]
        if risk_filter == "High Risk Only":
            display = display[display["RiskCategory"] == "🔴 High Risk"]
        elif risk_filter == "High + Medium Risk":
            display = display[display["RiskCategory"].isin(["🔴 High Risk", "🟡 Medium Risk"])]

        display_cols = ["CustomerID", "CustomerName", "Product", "CreditTier",
                       "LoanBalance", "CurrentRate", "NewRate", "BestCompRate",
                       "RateGap", "ChurnRiskScore", "RiskCategory", "RelationshipMgr"]

        display_show = display[display_cols].head(50).copy()
        display_show["LoanBalance"] = display_show["LoanBalance"].apply(lambda x: f"${x:,.0f}")
        display_show["CurrentRate"] = display_show["CurrentRate"].apply(lambda x: f"{x}%")
        display_show["NewRate"]     = display_show["NewRate"].apply(lambda x: f"{x}%")
        display_show["BestCompRate"]= display_show["BestCompRate"].apply(lambda x: f"{x}%")
        display_show["RateGap"]     = display_show["RateGap"].apply(lambda x: f"{x}%")

        st.dataframe(display_show, use_container_width=True, height=350)

        # Download call list
        csv_data = display[display_cols].to_csv(index=False)
        st.download_button(
            "📥 Download Call List (CSV)",
            data=csv_data,
            file_name=f"retention_call_list_{effective_date}.csv",
            mime="text/csv"
        )

        st.divider()

        # ── Customer Detail + Retention Offer ─────────────────────────
        st.subheader("🎯 Generate Personalized Retention Offer")

        high_risk_customers = scored[scored["RiskCategory"] == "🔴 High Risk"]["CustomerName"].tolist()
        if not high_risk_customers:
            high_risk_customers = scored["CustomerName"].head(20).tolist()

        selected_customer = st.selectbox(
            "Select a customer to generate retention offer:",
            high_risk_customers[:30]
        )

        if st.button("🤖 Generate Retention Offer", type="primary"):
            customer_row = scored[scored["CustomerName"] == selected_customer].iloc[0]
            customer_dict = customer_row.to_dict()

            col_detail, col_offer = st.columns([1, 1])

            with col_detail:
                st.markdown("**Customer Profile**")
                st.markdown(f"""
| Field | Value |
|---|---|
| **Name** | {customer_dict['CustomerName']} |
| **Product** | {customer_dict['Product']} |
| **Credit Tier** | {customer_dict['CreditTier']} |
| **FICO** | {customer_dict['FICO']} |
| **Loan Balance** | ${float(customer_dict['LoanBalance']):,.0f} |
| **Current Rate** | {customer_dict['CurrentRate']}% |
| **New Rate** | {customer_dict['NewRate']}% |
| **Best Competitor** | {customer_dict['BestCompRate']}% |
| **Rate Gap** | {customer_dict['RateGap']}% |
| **Months Remaining** | {customer_dict['MonthsRemaining']} |
| **Churn Risk** | {customer_dict['ChurnRiskScore']}/100 |
| **Relationship Mgr** | {customer_dict['RelationshipMgr']} |
""")

            with col_offer:
                with st.spinner("AI generating personalized retention offer..."):
                    offer = retention_offer_agent.generate(
                        customer_dict,
                        customer_dict["ChurnRiskScore"],
                        sop_text,
                        client
                    )
                st.markdown("**AI-Generated Retention Offer**")
                st.markdown(
                    f"<div style='background:#f8f9fa; padding:15px; border-radius:8px; "
                    f"border-left:4px solid #1f77b4;'>{offer.replace(chr(10), '<br>')}</div>",
                    unsafe_allow_html=True
                )

    else:
        # Placeholder before analysis runs
        st.info("👆 Enter a rate change above and click **Run Churn Analysis** to scan the portfolio.")

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Portfolio Size", "500 customers", "Ready to scan")
        col_b.metric("Total Loan Balance", "$132M", "Across 3 products")
        col_c.metric("Potential Loss per Cycle", "Up to $15M", "Without intervention", delta_color="inverse")


# ══════════════════════════════════════════════════════════════════════
# TAB 2 — SOP ASSISTANT CHATBOT
# ══════════════════════════════════════════════════════════════════════
with tab2:

    # Sidebar-style controls inside the tab
    st.title("🤖 SOP Intelligence Assistant")
    st.caption("Answers sourced only from SOP documents · Multi-Agent AI")
    st.divider()

    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1:
        user_email = st.text_input("📧 Your email (for email drafts)", placeholder="you@bank.com")
    with ctrl2:
        category = st.selectbox("📂 Product Category",
            ["All Categories", "Indirect Auto", "Direct Auto", "Business Banking"])
    with ctrl3:
        st.write("")
        if st.button("🗑️ Clear chat"):
            st.session_state.messages = []
            st.rerun()

    st.divider()

    # Sample questions
    with st.expander("💡 Sample questions — click to ask"):
        samples = {
            "📋 Process":     ["What is the first step in the rate change process?",
                               "How do I notify dealers for Indirect Auto?",
                               "What happens after ALCO approves a rate change?"],
            "📞 Escalation":  ["Who approves rate changes?",
                               "What do I do if the core system is not updated on time?",
                               "Who do I contact if a business client disputes a rate change?"],
            "⚖️ Compliance":  ["What compliance regulations apply to Direct Auto?",
                               "What is the MLA rate cap?",
                               "How long must rate change documents be retained?"],
            "✉️ Email":        ["Write an email to notify a dealer about the rate update",
                               "Draft an escalation email to IT about a core system issue"],
        }
        cols = st.columns(4)
        for idx, (group, questions) in enumerate(samples.items()):
            with cols[idx]:
                st.markdown(f"**{group}**")
                for q in questions:
                    if st.button(q, key=f"smp_{q}", use_container_width=True):
                        st.session_state.pending_question = q

    st.divider()

    # ── Chat input ─────────────────────────────────────────────────────
    if "pending_question" in st.session_state:
        prompt = st.session_state.pop("pending_question")
    else:
        prompt = st.chat_input("Ask anything about the Bank SOPs...")

    # ── Process question ───────────────────────────────────────────────
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        # INPUT GUARDRAIL — runs before routing, retrieval, or any LLM call
        input_check = guardrails.check_input(prompt)
        if not input_check.safe:
            st.session_state.messages.append({
                "role": "assistant", "content": input_check.user_message,
                "agent": "general", "is_clarification": False,
                "search_results": [], "confidence": None,
            })
            st.rerun()

        agent_name = router.route(prompt, client)

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[:-1]
        ]

        needs_clarify, clarify_q = False, ""
        if agent_name == "general":
            needs_clarify, clarify_q = multi_sop_agent.needs_clarification(prompt, client)

        if needs_clarify:
            st.session_state.messages.append({
                "role": "assistant", "content": f"🤔 {clarify_q}",
                "agent": "general", "is_clarification": True,
                "search_results": [], "confidence": None,
            })
        else:
            try:
                search_results = []

                if agent_name == "email":
                    email_addr    = user_email or "staff@bank.com"
                    # Retrieve relevant chunks for email context
                    email_results = sop_retriever.retrieve(prompt)
                    email_context = (
                        "\n\n".join(r.chunk.text for r in email_results)
                        if email_results else sop_text
                    )
                    raw_answer     = email_agent.ask(prompt, history, email_context, client, email_addr)
                    # OUTPUT GUARDRAIL — PII redaction + length cap for email drafts
                    email_conf     = email_results[0].cosine_sim if email_results else 1.0
                    out_check      = guardrails.check_output(raw_answer, retrieval_confidence=email_conf)
                    answer         = out_check.text
                    search_results = email_results
                    conf           = None
                else:
                    answer, search_results = multi_sop_agent.ask(
                        prompt, history, all_sops, client, category
                    )
                    conf = confidence_agent.score(prompt, answer, client, search_results)

                # Serialize SearchResult objects to plain dicts for session_state storage
                sr_dicts = [
                    {
                        "source_file":     r.chunk.source_file,
                        "section_heading": r.chunk.section_heading,
                        "chunk_text":      r.chunk.text[:500],
                        "cosine_sim":      r.cosine_sim,
                        "rrf_score":       r.rrf_score,
                    }
                    for r in (search_results or [])
                ]

                st.session_state.messages.append({
                    "role": "assistant", "content": answer,
                    "agent": agent_name, "is_clarification": False,
                    "search_results": sr_dicts, "confidence": conf,
                })
            except Exception as e:
                st.session_state.messages.append({
                    "role": "assistant", "content": f"❌ Error: {e}",
                    "agent": "general", "is_clarification": False,
                    "search_results": [], "confidence": None,
                })

    # ── Render chat history ────────────────────────────────────────────
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                agent_name = msg.get("agent", "general")
                info = AGENT_INFO.get(agent_name, AGENT_INFO["general"])

                if not msg.get("is_clarification"):
                    st.markdown(
                        f"<small style='color:{info['color']}'>{info['label']}</small>",
                        unsafe_allow_html=True
                    )
                st.markdown(msg["content"])

                search_results = msg.get("search_results", [])
                if search_results and not msg.get("is_clarification"):
                    with st.expander(
                        f"📄 {len(search_results)} SOP excerpt(s) used",
                        expanded=False,
                    ):
                        for i, r in enumerate(search_results, 1):
                            sim_pct = int(r["cosine_sim"] * 100)
                            st.markdown(
                                f"**[{i}] {r['source_file']}** → "
                                f"_{r['section_heading']}_ "
                                f"<small style='color:#888'>({sim_pct}% match)</small>",
                                unsafe_allow_html=True,
                            )
                            preview = r["chunk_text"]
                            st.caption(
                                preview[:300] + ("…" if len(preview) > 300 else "")
                            )

                conf = msg.get("confidence")
                if conf and not msg.get("is_clarification"):
                    score = conf["score"]
                    color = "#2ca02c" if score >= 8 else "#ff7f0e" if score >= 5 else "#d62728"
                    label = "High" if score >= 8 else "Medium" if score >= 5 else "Low"
                    st.markdown(
                        f"<div style='margin-top:6px;padding:5px 10px;background:#f0f2f6;"
                        f"border-radius:6px;font-size:0.8em;'>"
                        f"<b>Confidence:</b> <span style='color:{color};font-weight:bold;'>"
                        f"{label} ({score}/10)</span> — {conf['reasoning']}</div>",
                        unsafe_allow_html=True
                    )
