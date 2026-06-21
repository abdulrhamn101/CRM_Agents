import sys
import streamlit as st
import pandas as pd
import json
import plotly.express as px
from pathlib import Path
from scorer import score_in_batches

PROJECT_ROOT = Path(
    "/Users/abdulrhman/Library/CloudStorage/OneDrive-UniversityofPrinceMugrin/"
    "Personal/Development/Agentic_bootcamp_SDA/devided_project"
)
SELECTED_TARGETS_PATH = PROJECT_ROOT / "selected_companies.json"
CAMPAIGN_OUTPUT_PATH = PROJECT_ROOT / "campaign_emails.csv"
CAMPAIGN_AGENT_DIR = PROJECT_ROOT / "Campaign_Agent"
EMAIL_AGENT_DIR = PROJECT_ROOT / "Email-Agent"

for _d in (CAMPAIGN_AGENT_DIR, EMAIL_AGENT_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

from campaign_agent import CampaignAgent  # noqa: E402
from email_agent import (  # noqa: E402
    send_approved_email,
    run_inbox_triage,
    is_signed_in,
    get_authenticated_email,
    sign_in_gmail,
    sign_out_gmail,
)
from email_finder import find_email  # noqa: E402

st.set_page_config(
    page_title="Saudi Companies Directory",
    page_icon="🇸🇦",
    layout="wide"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

* { font-family: 'Inter', sans-serif; }

.stApp { background: #0f1117; }

.header-title {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #00c853, #00e676);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 4px;
}
.header-sub {
    color: #666;
    font-size: 0.95rem;
    margin-bottom: 2rem;
}

.metric-card {
    background: #1a1d27;
    border: 1px solid #2a2d3a;
    border-radius: 14px;
    padding: 20px;
    text-align: center;
    transition: border-color 0.2s;
}
.metric-card:hover { border-color: #00c853; }
.metric-num { font-size: 2.2rem; font-weight: 800; color: #00c853; }
.metric-lbl { font-size: 0.8rem; color: #888; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }

.detail-box {
    background: #1a1d27;
    border: 1px solid #00c853;
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 20px;
}
.detail-title { font-size: 1.4rem; font-weight: 800; color: #fff; margin-bottom: 6px; }
.detail-desc { color: #aaa; line-height: 1.7; margin: 12px 0; }
.detail-row { display: flex; gap: 30px; flex-wrap: wrap; margin-top: 16px; }
.detail-key { font-size: 0.75rem; color: #666; text-transform: uppercase; letter-spacing: 0.05em; }
.detail-val { font-size: 0.95rem; color: #eee; font-weight: 600; margin-top: 2px; }

.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    margin-right: 6px;
}
.badge-sector { background: #1e3a5f; color: #60a5fa; }
.badge-startup { background: #1a3a2a; color: #4ade80; }
.badge-emp { background: #2a1f3a; color: #c084fc; }

.filter-header {
    color: #00c853;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
    margin-top: 16px;
}

div[data-testid="stSidebar"] {
    background: #12151e;
    border-right: 1px solid #1e2130;
}

.no-results {
    text-align: center;
    padding: 60px 20px;
    color: #555;
    font-size: 1rem;
}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    with open('companies.json', encoding='utf-8') as f:
        return pd.DataFrame(json.load(f))

df = load_data()

# ── Header ─────────────────────────────────────────────────────────
st.markdown('<div class="header-title">🇸🇦 Saudi Companies Directory</div>', unsafe_allow_html=True)
st.markdown('<div class="header-sub">Browse & filter companies across all sectors — click any company for full details</div>', unsafe_allow_html=True)

# ── Sidebar Filters ─────────────────────────────────────────────────
with st.sidebar:
    # ── Gmail sign-in ───────────────────────────────────────────────
    st.markdown("## 📬 Gmail Account")

    if "gmail_email" not in st.session_state:
        st.session_state.gmail_email = get_authenticated_email()

    current_email = st.session_state.gmail_email

    if current_email:
        st.success(f"✓ Connected\n\n`{current_email}`")
        if st.button("🚪 Sign out", key="gmail_signout", width="stretch"):
            sign_out_gmail()
            st.session_state.gmail_email = None
            st.rerun()
    else:
        st.warning("Not connected — sending and inbox features are disabled.")
        if st.button("🔐 Sign in to Gmail", key="gmail_signin",
                     type="primary", width="stretch"):
            try:
                with st.spinner("Opening browser for Gmail consent…"):
                    result = sign_in_gmail()
                st.session_state.gmail_email = result.get("email")
                st.success(f"Connected as {result.get('email')}")
                st.rerun()
            except FileNotFoundError as exc:
                st.error(str(exc))
                st.caption("Put your OAuth `credentials.json` (Google Cloud → "
                           "OAuth client ID → Desktop app) in `Email-Agent/`.")
            except Exception as exc:
                st.error(f"Sign-in failed: {exc}")

    st.markdown("---")

    st.markdown("## 🔍 Filter Companies")

    st.markdown('<div class="filter-header">📂 Sector — pick one or more</div>', unsafe_allow_html=True)
    all_sectors = sorted(df['sector'].dropna().unique())
    selected_sectors = st.multiselect("Sector", all_sectors, default=[], key="sectors", label_visibility="collapsed", placeholder="All sectors (default)")

    st.markdown('<div class="filter-header">📍 City — pick one or more</div>', unsafe_allow_html=True)
    all_cities = sorted([c for c in df['city_clean'].dropna().unique() if c not in ('Unknown', '')])
    selected_cities = st.multiselect("City", all_cities, key="cities", label_visibility="collapsed", placeholder="All cities (default)")

    st.markdown('<div class="filter-header">👥 Company Size — pick one or more</div>', unsafe_allow_html=True)
    emp_order = ['51-200', '200-1,000', '1,000-5,000', '5,000-10,000', '10,000+']
    selected_emp = st.multiselect("Company size", emp_order, default=[], key="emp", label_visibility="collapsed", placeholder="All sizes (default)")

    st.markdown('<div class="filter-header">🚀 Company Type</div>', unsafe_allow_html=True)
    company_type = st.radio("Company type", ['All', 'Startups Only', 'Established Only'], key="type", label_visibility="collapsed")

    st.markdown('<div class="filter-header">🔎 Search</div>', unsafe_allow_html=True)
    search = st.text_input("Search", placeholder="Company ", key="search", label_visibility="collapsed")

# ── Apply Filters ────────────────────────────────────────────────────
filtered = df.copy()

if selected_sectors:  # empty = show all
    filtered = filtered[filtered['sector'].isin(selected_sectors)]

if selected_cities:  # empty = show all
    filtered = filtered[filtered['city_clean'].isin(selected_cities)]

if selected_emp:  # empty = show all
    filtered = filtered[filtered['emp_bucket'].isin(selected_emp)]

if company_type == 'Startups Only':
    filtered = filtered[filtered['is_startup'] == True]
elif company_type == 'Established Only':
    filtered = filtered[filtered['is_startup'] == False]

if search:
    mask = (
        filtered['name'].str.contains(search, case=False, na=False) |
        filtered['description'].str.contains(search, case=False, na=False) |
        filtered['sub_sector'].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

filtered = filtered.sort_values('name').reset_index(drop=True)

# ── Metrics ──────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
for col, num, label in [
    (c1, len(filtered), "Companies Found"),
    (c2, filtered['sector'].nunique(), "Sectors"),
    (c3, int(filtered['is_startup'].sum()), "🚀 Startups"),
    (c4, filtered[filtered['city_clean'] != 'Unknown']['city_clean'].nunique(), "Cities"),
]:
    with col:
        st.markdown(f'<div class="metric-card"><div class="metric-num">{num}</div><div class="metric-lbl">{label}</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── State ────────────────────────────────────────────────────────────
if 'selected' not in st.session_state:
    st.session_state.selected = None
if 'score_results' not in st.session_state:
    st.session_state.score_results = None
if 'score_criteria' not in st.session_state:
    st.session_state.score_criteria = ""
if 'scored_count' not in st.session_state:
    st.session_state.scored_count = 0
if 'selected_targets' not in st.session_state:
    st.session_state.selected_targets = set()
if 'confirm_msg' not in st.session_state:
    st.session_state.confirm_msg = None
if 'generated_emails' not in st.session_state:
    st.session_state.generated_emails = None


def save_targets():
    targets_df = df[df['name'].isin(st.session_state.selected_targets)].copy()
    records = []
    for _, r in targets_df.iterrows():
        rec = r.to_dict()
        rec['company_name'] = rec.get('name', '')
        if rec.get('city_clean') and not rec.get('city'):
            rec['city'] = rec['city_clean']
        records.append(rec)
    SELECTED_TARGETS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    return len(records)


def _parse_triage_events(events):
    """Walk the (kind, data) event stream from run_inbox_triage and
    assemble a structured per-email summary list."""
    emails = []
    by_id = {}
    current = None  # most recent email being processed (matched via body)

    for kind, data in events:
        if kind == "tool_result" and data.get("name") == "fetch_unread_emails":
            for e in data.get("result", {}).get("emails", []):
                summary = {
                    "id": e.get("id"),
                    "thread_id": e.get("thread_id"),
                    "from": e.get("from"),
                    "subject": e.get("subject"),
                    "date": e.get("date"),
                    "snippet": e.get("snippet"),
                    "body": e.get("body"),
                    "signals": None,
                    "priority": None,
                    "classification": None,
                    "confidence": None,
                    "routed_to": None,
                    "action": None,
                    "draft": None,
                    "marked_read": False,
                }
                emails.append(summary)
                if e.get("id"):
                    by_id[e["id"]] = summary

        elif kind == "tool_call":
            name = data.get("name", "")
            inp = data.get("input", {})
            if name in ("extract_signals", "classify_email"):
                body = inp.get("body", "") or ""
                for em in emails:
                    if em.get("body") and body and em["body"][:200] == body[:200]:
                        current = em
                        break
            elif name == "create_draft" and current is not None:
                current["draft"] = {
                    "to": inp.get("to"),
                    "subject": inp.get("subject"),
                    "body": inp.get("body"),
                }
            elif name == "mark_as_read":
                eid = inp.get("email_id")
                if eid and eid in by_id:
                    by_id[eid]["marked_read"] = True

        elif kind == "tool_result":
            name = data.get("name", "")
            res = data.get("result")
            if not isinstance(res, dict):
                continue
            if name == "extract_signals" and current is not None:
                current["signals"] = res.get("signals", [])
                current["priority"] = res.get("priority")
            elif name == "classify_email" and current is not None:
                current["classification"] = res.get("classification")
                current["confidence"] = res.get("confidence")
            elif name == "route_to_agent" and current is not None:
                current["routed_to"] = res.get("routed_to")
                current["action"] = res.get("action")
            elif name == "create_draft" and current is not None:
                if current.get("draft") is None:
                    current["draft"] = {}
                current["draft"]["draft_id"] = res.get("draft_id")

    return emails


def _render_email_card(e):
    """Render one triaged email as a self-contained card."""
    cls = e.get("classification") or ""
    pri = e.get("priority") or ""
    cls_emoji = "📄" if cls == "proposal" else ("🔍" if cls == "opportunity_qualification" else "📧")
    pri_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(pri, "⚪")

    with st.container(border=True):
        # Header
        subject = e.get("subject") or "(no subject)"
        st.markdown(f"#### {cls_emoji} {subject}")

        # Meta row — From / Date / read status
        meta_l, meta_r = st.columns([3, 1])
        with meta_l:
            sender = e.get("from") or "unknown"
            st.markdown(f"**From:**  {sender}")
            if e.get("date"):
                st.caption(f"📅 {e['date']}")
        with meta_r:
            if e.get("marked_read"):
                st.caption("✓ marked read")

        st.markdown("")

        # Classification / Priority / Routing — three boxes
        col_cls, col_pri, col_route = st.columns(3)
        with col_cls:
            with st.container(border=True):
                st.caption("CLASSIFICATION")
                if cls:
                    label = cls.replace("_", " ").title()
                    st.markdown(f"**{cls_emoji} {label}**")
                    if e.get("confidence"):
                        st.caption(f"confidence: {e['confidence']}")
                else:
                    st.markdown("—")
        with col_pri:
            with st.container(border=True):
                st.caption("PRIORITY")
                if pri:
                    st.markdown(f"**{pri_emoji} {pri.title()}**")
                else:
                    st.markdown("—")
        with col_route:
            with st.container(border=True):
                st.caption("ROUTED TO")
                if e.get("routed_to"):
                    st.markdown(f"**{e['routed_to']}**")
                    if e.get("action"):
                        st.caption(e["action"])
                else:
                    st.markdown("—")

        # Signals chips
        signals = e.get("signals") or []
        if signals:
            st.markdown("**🎯 Detected signals**")
            st.markdown("  ".join(f"`{s}`" for s in signals))

        # Email content (collapsible)
        body = e.get("body") or e.get("snippet") or "(no content)"
        with st.expander("📄 Original email content"):
            st.text(body)

        # Reply draft (collapsible)
        if e.get("draft"):
            d = e["draft"]
            with st.expander("✉️ Reply draft — saved to Gmail → Drafts"):
                st.markdown(f"**To:**  {d.get('to', '')}")
                st.markdown(f"**Subject:**  {d.get('subject', '')}")
                st.text(d.get("body", ""))
                if d.get("draft_id"):
                    st.caption(f"Gmail draft ID: `{d['draft_id']}`")


# ── Target Action Bar ────────────────────────────────────────────────
target_count = len(st.session_state.selected_targets)
ac1, ac2, ac3, ac4 = st.columns([2, 1, 1, 2])
with ac1:
    st.markdown(f"### 🎯 Targets selected: **{target_count}**")
with ac2:
    if st.button("➕ Add all filtered", width="stretch", key="add_all_filtered"):
        for n in filtered['name']:
            st.session_state.selected_targets.add(n)
        st.rerun()
with ac3:
    if st.button("🗑️ Clear all", width="stretch", key="clear_all_targets"):
        st.session_state.selected_targets = set()
        st.rerun()
with ac4:
    if st.button(
        f"✅ Confirm & Generate Emails ({target_count})",
        type="primary",
        width="stretch",
        disabled=(target_count == 0),
        key="confirm_targets",
    ):
        n_saved = save_targets()
        progress_bar = st.progress(0.0, text="Starting Campaign Agent…")

        def _on_progress(idx, total, name):
            progress_bar.progress(
                idx / max(total, 1),
                text=f"Generating email {idx}/{total} — {name}",
            )

        try:
            agent = CampaignAgent()
            result = agent.run(
                input_file=str(SELECTED_TARGETS_PATH),
                limit=None,
                source="selected",
                output_file=str(CAMPAIGN_OUTPUT_PATH),
                progress_callback=_on_progress,
            )
            st.session_state.generated_emails = result["emails"]
            st.session_state.confirm_msg = (
                f"Saved {n_saved} target{'s' if n_saved != 1 else ''} and generated "
                f"{result['total_companies']} personalized email{'s' if result['total_companies'] != 1 else ''} → "
                f"{CAMPAIGN_OUTPUT_PATH.name}"
            )
        except Exception as e:
            st.session_state.confirm_msg = f"Saved {n_saved} targets, but Campaign Agent failed: {e}"
        finally:
            progress_bar.empty()

if st.session_state.confirm_msg:
    st.success(st.session_state.confirm_msg)
    st.session_state.confirm_msg = None

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Companies List",
    "📊 Analytics",
    "🎯 Lead Scoring",
    "✉️ Emails & Send",
    "📥 Inbox Triage",
])

with tab1:
    if filtered.empty:
        st.markdown('<div class="no-results">😕 No companies match your current filters.</div>', unsafe_allow_html=True)
    else:
        # Detail panel
        if st.session_state.selected is not None:
            idx = st.session_state.selected
            if idx < len(filtered):
                row = filtered.iloc[idx]
                website = str(row.get('website', '') or '').strip()
                website_clean = website.replace('www.', '').strip()

                with st.container(border=True):
                    title_col, close_col = st.columns([5, 1])
                    with title_col:
                        st.markdown(f"### 🏢 {row.get('name', '')}")
                    with close_col:
                        if st.button("✕ Close", key="close"):
                            st.session_state.selected = None
                            st.rerun()
                    badges = f"`{row.get('sector', '')}`"
                    if row.get('is_startup'):
                        badges += "  `🚀 Startup`"
                    badges += f"  `👥 {row.get('employees', 'N/A')}`"
                    st.markdown(badges)
                    st.markdown(f"> {row.get('description', 'No description available.')}")
                    d1, d2, d3, d4 = st.columns(4)
                    with d1:
                        st.markdown("**📍 City**")
                        st.write(row.get('city_clean', 'N/A'))
                    with d2:
                        st.markdown("**🏷️ Sub-sector**")
                        st.write(row.get('sub_sector', 'N/A'))
                    with d3:
                        st.markdown("**👥 Employees**")
                        st.write(row.get('employees', 'N/A'))
                    with d4:
                        st.markdown("**🔗 Website**")
                        if website_clean and website_clean not in ('N/A', 'nan', ''):
                            st.markdown(f"[{website_clean}](https://{website_clean})")
                        else:
                            st.write("N/A")

                st.markdown("---")

        # Grid
        cols_per_row = 2
        rows = [filtered.iloc[i:i+cols_per_row] for i in range(0, len(filtered), cols_per_row)]

        for row_df in rows:
            cols = st.columns(cols_per_row)
            for col_idx, (_, company) in enumerate(row_df.iterrows()):
                abs_idx = filtered.index.get_loc(company.name)
                company_name = company['name']
                with cols[col_idx]:
                    startup_tag = "🚀 " if company.get('is_startup') else ""
                    sub = str(company.get('sub_sector', '') or '')[:45]

                    chk_col, btn_col = st.columns([1, 5])
                    with chk_col:
                        is_target = st.checkbox(
                            "🎯",
                            value=(company_name in st.session_state.selected_targets),
                            key=f"chk_{abs_idx}",
                            help="Mark as campaign target",
                        )
                        if is_target:
                            st.session_state.selected_targets.add(company_name)
                        else:
                            st.session_state.selected_targets.discard(company_name)
                    with btn_col:
                        btn_label = f"{startup_tag}**{company_name}**\n📍 {company.get('city_clean','?')}  ·  👥 {company.get('emp_bucket','?')}\n🏷️ {sub}"
                        if st.button(btn_label, key=f"btn_{abs_idx}", width="stretch"):
                            st.session_state.selected = abs_idx
                            st.rerun()

with tab2:
    if filtered.empty:
        st.warning("No data to display.")
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            sector_counts = filtered['sector'].value_counts().reset_index()
            sector_counts.columns = ['Sector', 'Count']
            fig1 = px.bar(sector_counts, x='Count', y='Sector', orientation='h',
                         title='Companies by Sector', color='Count',
                         color_continuous_scale=['#1a3a2a', '#00c853'],
                         template='plotly_dark')
            fig1.update_layout(showlegend=False, height=380, plot_bgcolor='#1a1d27', paper_bgcolor='#1a1d27')
            st.plotly_chart(fig1, width="stretch")

        with col_b:
            city_df = filtered[filtered['city_clean'].notna() & (filtered['city_clean'] != 'Unknown')]
            if not city_df.empty:
                city_counts = city_df['city_clean'].value_counts().reset_index()
                city_counts.columns = ['City', 'Count']
                fig2 = px.pie(city_counts, values='Count', names='City',
                             title='Distribution by City', hole=0.45,
                             template='plotly_dark',
                             color_discrete_sequence=px.colors.qualitative.Safe)
                fig2.update_layout(height=380, paper_bgcolor='#1a1d27')
                st.plotly_chart(fig2, width="stretch")

        emp_counts = filtered[
            filtered['emp_bucket'].notna() & (filtered['emp_bucket'] != 'Unknown')
        ]['emp_bucket'].value_counts().reset_index()
        emp_counts.columns = ['Size', 'Count']
        emp_order_f = [e for e in emp_order if e in emp_counts['Size'].values]
        emp_counts['Size'] = pd.Categorical(emp_counts['Size'], categories=emp_order_f, ordered=True)
        emp_counts = emp_counts.sort_values('Size')
        fig3 = px.bar(emp_counts, x='Size', y='Count', title='Companies by Employee Count',
                     color='Count', color_continuous_scale=['#1e3a5f', '#60a5fa'],
                     template='plotly_dark')
        fig3.update_layout(showlegend=False, plot_bgcolor='#1a1d27', paper_bgcolor='#1a1d27')
        st.plotly_chart(fig3, width="stretch")


with tab3:
    st.markdown("### 🎯 Lead Scoring")
    st.markdown(f"Scoring will run on the **{len(filtered)} companies** from your current filters.")

    if filtered.empty:
        st.warning("No companies to score. Adjust your filters first.")
    else:
        st.markdown("---")

        # Criteria selection
        use_defaults = st.checkbox(
            "✅ Use BeamData default criteria (IT, Fintech, Telecom, Healthcare — 200+ employees — Riyadh priority)",
            value=True
        )

        custom_criteria = ""
        if not use_defaults:
            custom_criteria = st.text_area(
                "✍️ Write your own criteria:",
                placeholder="e.g. I want companies in healthcare with 500+ employees that are likely to invest in AI automation...",
                height=120
            )

        st.markdown("---")

        # Agent mode toggle
        use_agent = st.toggle(
            "🤖 Agent Mode — searches the web for each company (slower but more accurate)",
            value=False
        )
        if use_agent:
            st.info(f"⚠️ Agent mode will do {len(filtered)} web searches — recommended max 10 companies.")

        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            score_btn = st.button(
                f"🎯 Score {len(filtered)} Companies",
                width="stretch",
                type="primary"
            )
        with col_info:
            if use_agent:
                st.caption("🤖 Agent will search the web for each company then score it.")
            else:
                st.caption("⚡ Fast mode: scores based on existing data.")

        if score_btn:
            if not use_defaults and not custom_criteria.strip():
                st.error("Please write your criteria or use BeamData defaults.")
            else:
                companies_list = filtered.to_dict(orient='records')

                if use_agent:
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    def update_progress(current, total, company_name):
                        progress_bar.progress(current / total)
                        status_text.text(f"🔍 Researching {current}/{total}: {company_name}")

                    try:
                        results = score_in_batches(
                            companies_list,
                            criteria=custom_criteria,
                            use_beamdata_defaults=use_defaults,
                            use_agent=True,
                            progress_callback=update_progress
                        )
                        progress_bar.progress(1.0)
                        status_text.text("✅ Done!")
                        st.session_state.score_results = results
                        st.session_state.scored_count = len(results)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    with st.spinner(f"⚡ Scoring {len(companies_list)} companies..."):
                        try:
                            results = score_in_batches(
                                companies_list,
                                criteria=custom_criteria,
                                use_beamdata_defaults=use_defaults,
                                batch_size=15,
                                use_agent=False
                            )
                            st.session_state.score_results = results
                            st.session_state.scored_count = len(results)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # Show results
        if st.session_state.score_results:
            results = st.session_state.score_results

            # Summary metrics
            high = sum(1 for r in results if r.get('grade') == 'High')
            medium = sum(1 for r in results if r.get('grade') == 'Medium')
            low = sum(1 for r in results if r.get('grade') == 'Low')

            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(f'<div class="metric-card"><div class="metric-num">{len(results)}</div><div class="metric-lbl">Scored</div></div>', unsafe_allow_html=True)
            with m2:
                st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#4ade80">{high}</div><div class="metric-lbl">🟢 High</div></div>', unsafe_allow_html=True)
            with m3:
                st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#facc15">{medium}</div><div class="metric-lbl">🟡 Medium</div></div>', unsafe_allow_html=True)
            with m4:
                st.markdown(f'<div class="metric-card"><div class="metric-num" style="color:#f87171">{low}</div><div class="metric-lbl">🔴 Low</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Grade filter
            grade_filter = st.radio("Show:", ["All", "🟢 High", "🟡 Medium", "🔴 Low"], horizontal=True)

            filtered_results = results
            if grade_filter == "🟢 High":
                filtered_results = [r for r in results if r.get('grade') == 'High']
            elif grade_filter == "🟡 Medium":
                filtered_results = [r for r in results if r.get('grade') == 'Medium']
            elif grade_filter == "🔴 Low":
                filtered_results = [r for r in results if r.get('grade') == 'Low']

            st.markdown("---")

            # Results table
            for i, r in enumerate(filtered_results):
                grade = r.get('grade', '')
                score = r.get('score', 0)
                emoji = "🟢" if grade == "High" else "🟡" if grade == "Medium" else "🔴"

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"**{i+1}. {r.get('name', 'N/A')}**")
                        st.caption(f"📍 {r.get('city_clean', 'N/A')}  ·  🏷️ {r.get('sector', 'N/A')}  ·  👥 {r.get('employees', 'N/A')}")
                    with c2:
                        st.markdown(f"### {emoji} {score}")
                    with c3:
                        st.markdown(f"`{grade}`")
                    st.markdown(f"💬 *{r.get('reason', '')}*")
                    if r.get('research'):
                        with st.expander("🔍 Web Research"):
                            st.caption(r.get('research', ''))

            st.markdown("---")

            # Export CSV
            import csv, io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=['name', 'city_clean', 'sector', 'employees', 'score', 'grade', 'reason', 'website'])
            writer.writeheader()
            for r in results:
                writer.writerow({
                    'name': r.get('name', ''),
                    'city_clean': r.get('city_clean', ''),
                    'sector': r.get('sector', ''),
                    'employees': r.get('employees', ''),
                    'score': r.get('score', ''),
                    'grade': r.get('grade', ''),
                    'reason': r.get('reason', ''),
                    'website': r.get('website', ''),
                })
            csv_data = output.getvalue()

            st.download_button(
                label="⬇️ Export Results as CSV",
                data=csv_data,
                file_name="lead_scoring_results.csv",
                mime="text/csv",
                width="stretch"
            )

            if st.button("🔄 Clear Results & Re-score", width="stretch"):
                st.session_state.score_results = None
                st.rerun()

with tab4:
    emails = st.session_state.generated_emails
    if not emails:
        st.info(
            "No emails generated yet. Pick targets above and click "
            "**✅ Confirm & Generate Emails** to run the Campaign Agent."
        )
    else:
        st.markdown(f"### ✉️ {len(emails)} personalized email(s)")
        st.caption(f"Full CSV: `{CAMPAIGN_OUTPUT_PATH}`")

        ctl_l, ctl_r = st.columns([3, 1])
        with ctl_l:
            test_recipient = st.text_input(
                "🧪 Test recipient — overrides every 'To:' address (leave blank to send to real prospects)",
                value=st.session_state.get("test_recipient", ""),
                placeholder="you@gmail.com",
                key="test_recipient_input",
            )
            st.session_state.test_recipient = test_recipient
        with ctl_r:
            st.markdown("####")
            if st.button("🔎 Enrich missing emails", width="stretch", key="enrich_btn"):
                progress = st.progress(0.0, text="Searching company sites…")
                updated = 0
                missing = [e for e in emails if not (e.get("email") or "").strip()
                           or (e.get("email") or "").strip().lower() in ("n/a", "na", "none")]
                for i, e in enumerate(missing, 1):
                    result = find_email(
                        e.get("company_name", ""),
                        website=e.get("website") or None,
                        city=e.get("city"),
                    )
                    if result.get("email"):
                        e["email"] = result["email"]
                        e["_email_source"] = result.get("source")
                        e["_email_confidence"] = result.get("confidence")
                        updated += 1
                    progress.progress(i / max(len(missing), 1),
                                      text=f"{e.get('company_name','?')} → {result.get('email','—')}")
                progress.empty()
                st.success(f"Enriched {updated} of {len(missing)} missing address(es).")
                st.rerun()

        st.markdown("---")

        if "sent_emails" not in st.session_state:
            st.session_state.sent_emails = {}

        for idx, e in enumerate(emails):
            company = e.get("company_name", f"row-{idx}")
            real_to = (e.get("email") or "").strip()
            effective_to = test_recipient.strip() or real_to
            sent_record = st.session_state.sent_emails.get(company)

            badge = ""
            if sent_record:
                badge = " ✓ sent"
            elif not real_to and not test_recipient.strip():
                badge = " ⚠️ no recipient"

            with st.expander(f"📧 {company} — {e.get('email_subject', '')}{badge}"):
                meta_l, meta_r = st.columns(2)
                with meta_l:
                    st.markdown(f"**Sector:** {e.get('sector', 'N/A')}")
                    st.markdown(f"**City:** {e.get('city', 'N/A')}")
                with meta_r:
                    st.markdown(f"**Suggested service:** {e.get('suggested_service', 'N/A')}")
                    st.markdown(f"**Goal:** {e.get('campaign_goal', 'N/A')}")

                conf = e.get("_email_confidence")
                to_help = None
                if test_recipient.strip() and real_to:
                    to_help = f"Test override active. Real address on file: {real_to}"
                elif conf:
                    to_help = f"Auto-found ({e.get('_email_source')}, confidence: {conf})"

                new_to = st.text_input("To", value=effective_to, key=f"to_{idx}", help=to_help)
                new_subject = st.text_input("Subject", value=e.get("email_subject", ""), key=f"subj_{idx}")
                new_body = st.text_area("Body", value=e.get("email_body", ""), height=240, key=f"body_{idx}")

                btn_col, status_col = st.columns([1, 3])
                with btn_col:
                    signed_in = bool(st.session_state.get("gmail_email"))
                    can_send = bool(new_to.strip()) and signed_in
                    send_help = None if signed_in else "Sign in to Gmail in the sidebar first."
                    if st.button("✉️ Approve & Send", key=f"send_{idx}",
                                 type="primary", disabled=not can_send,
                                 width="stretch", help=send_help):
                        try:
                            result = send_approved_email(
                                to=new_to.strip(),
                                subject=new_subject,
                                body=new_body,
                            )
                            st.session_state.sent_emails[company] = result
                            st.success(f"Sent → {new_to.strip()} (id: {result['message_id'][:12]}…)")
                        except FileNotFoundError as exc:
                            st.error(str(exc))
                            st.info("Put your Google OAuth `credentials.json` in `Email-Agent/`. "
                                    "See Email-Agent/README.md.")
                        except Exception as exc:
                            st.error(f"Send failed: {exc}")
                with status_col:
                    if sent_record:
                        st.caption(f"✓ Sent at {sent_record.get('sent_at','?')} → {sent_record.get('to','?')}  "
                                   f"(Gmail id: {sent_record.get('message_id','?')[:16]}…)")


with tab5:
    st.markdown("### 📥 Inbox Triage")
    st.markdown(
        "Pulls **unread** messages from your connected Gmail, classifies each "
        "(proposal vs opportunity-qualification), extracts sales signals, and "
        "saves a reply **draft** (Gmail → Drafts) for your review. Never sends automatically."
    )

    if "triage_events" not in st.session_state:
        st.session_state.triage_events = []

    signed_in = bool(st.session_state.get("gmail_email"))
    if not signed_in:
        st.warning("🔐 Sign in to Gmail in the sidebar to enable inbox triage.")

    ic_l, ic_r = st.columns([1, 4])
    with ic_l:
        max_results = st.number_input(
            "Max emails", min_value=1, max_value=20, value=5, key="triage_max",
        )
    with ic_r:
        st.markdown("####")
        triage_btn = st.button(
            "🔄 Triage unread emails", type="primary",
            width="stretch", key="triage_btn",
            disabled=not signed_in,
            help=None if signed_in else "Sign in to Gmail first.",
        )

    if triage_btn:
        st.session_state.triage_events = []
        log_placeholder = st.empty()
        log_lines = []
        try:
            for kind, data in run_inbox_triage(max_results=int(max_results)):
                st.session_state.triage_events.append((kind, data))

                if kind == "log":
                    log_lines.append(data)
                elif kind == "tool_call":
                    log_lines.append(f"→ {data['name']}({', '.join(data['input'].keys())})")
                elif kind == "tool_result":
                    log_lines.append(f"  ← {data['name']} returned")

                with log_placeholder.container(border=True):
                    st.caption("Live agent log")
                    for line in log_lines[-15:]:
                        st.text(line)

            log_placeholder.empty()
            st.success("Triage complete.")
        except FileNotFoundError as exc:
            st.error(str(exc))
            st.info("Drop your Google OAuth `credentials.json` into `Email-Agent/`. "
                    "See `Email-Agent/README.md` for the OAuth setup.")
        except RuntimeError as exc:
            st.error(str(exc))
            st.info("Set OPENAI_API_KEY in the shell that launched Streamlit, then restart.")
        except Exception as exc:
            st.error(f"Triage failed: {exc}")

    # ── Per-email results ────────────────────────────────────────────
    if st.session_state.triage_events:
        parsed = _parse_triage_events(st.session_state.triage_events)
        if not parsed:
            st.info("📭 No unread emails were found.")
        else:
            st.markdown(f"### 📨 {len(parsed)} email(s) triaged")
            drafts_n = sum(1 for e in parsed if e.get("draft"))
            high_n = sum(1 for e in parsed if e.get("priority") == "high")
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Triaged", len(parsed))
            with m2:
                st.metric("High priority", high_n)
            with m3:
                st.metric("Drafts created", drafts_n)

            st.markdown("---")

            for e in parsed:
                _render_email_card(e)
                st.markdown("")

        with st.expander("🔧 Raw agent event log (debug)", expanded=False):
            for kind, data in st.session_state.triage_events:
                if kind == "log":
                    st.text(data)
                elif kind == "tool_call":
                    keys = ", ".join(data["input"].keys())
                    st.markdown(f"`→ {data['name']}({keys})`")
                elif kind == "tool_result":
                    res = data.get("result")
                    if isinstance(res, dict):
                        preview = {k: res[k] for k in list(res)[:3]}
                        st.caption(f"  ← {data['name']}: {preview}")
                    else:
                        st.caption(f"  ← {data['name']}: {res}")


st.markdown("---")
st.caption("Saudi Companies Directory • Built with Streamlit & Plotly")
