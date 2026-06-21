import sys
import streamlit as st
import pandas as pd
import json
import plotly.express as px
from pathlib import Path

PROJECT_ROOT = Path(
    "/Users/abdulrhman/Library/CloudStorage/OneDrive-UniversityofPrinceMugrin/"
    "Personal/Development/Agentic_bootcamp_SDA/devided_project"
)
SELECTED_TARGETS_PATH = PROJECT_ROOT / "selected_companies.json"
CAMPAIGN_OUTPUT_PATH = PROJECT_ROOT / "campaign_emails.csv"
CAMPAIGN_AGENT_DIR = PROJECT_ROOT / "Campaign_Agent"

if str(CAMPAIGN_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(CAMPAIGN_AGENT_DIR))

from campaign_agent import CampaignAgent  # noqa: E402

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
    with open('/Users/abdulrhman/Library/CloudStorage/OneDrive-UniversityofPrinceMugrin/Personal/Development/Agentic_bootcamp_SDA/devided_project/Agent-Filter/companies.json', encoding='utf-8') as f:
        return pd.DataFrame(json.load(f))

df = load_data()

# ── Header ─────────────────────────────────────────────────────────
st.markdown('<div class="header-title">🇸🇦 Saudi Companies Directory</div>', unsafe_allow_html=True)
st.markdown('<div class="header-sub">Browse & filter companies across all sectors — click any company for full details</div>', unsafe_allow_html=True)

# ── Sidebar Filters ─────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Filter Companies")

    st.markdown('<div class="filter-header">📂 Sector — pick one or more</div>', unsafe_allow_html=True)
    all_sectors = sorted(df['sector'].dropna().unique())
    selected_sectors = st.multiselect("", all_sectors, default=[], key="sectors", label_visibility="collapsed", placeholder="All sectors (default)")

    st.markdown('<div class="filter-header">📍 City — pick one or more</div>', unsafe_allow_html=True)
    all_cities = sorted([c for c in df['city_clean'].dropna().unique() if c not in ('Unknown', '')])
    selected_cities = st.multiselect("", all_cities, key="cities", label_visibility="collapsed", placeholder="All cities (default)")

    st.markdown('<div class="filter-header">👥 Company Size — pick one or more</div>', unsafe_allow_html=True)
    emp_order = ['51-200', '200-1,000', '1,000-5,000', '5,000-10,000', '10,000+']
    selected_emp = st.multiselect("", emp_order, default=[], key="emp", label_visibility="collapsed", placeholder="All sizes (default)")

    st.markdown('<div class="filter-header">🚀 Company Type</div>', unsafe_allow_html=True)
    company_type = st.radio("", ['All', 'Startups Only', 'Established Only'], key="type", label_visibility="collapsed")

    st.markdown('<div class="filter-header">🔎 Search</div>', unsafe_allow_html=True)
    search = st.text_input("", placeholder="Company name or description...", key="search", label_visibility="collapsed")

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


# ── Target Action Bar ────────────────────────────────────────────────
target_count = len(st.session_state.selected_targets)
ac1, ac2, ac3, ac4 = st.columns([2, 1, 1, 2])
with ac1:
    st.markdown(f"### 🎯 Targets selected: **{target_count}**")
with ac2:
    if st.button("➕ Add all filtered", use_container_width=True, key="add_all_filtered"):
        for n in filtered['name']:
            st.session_state.selected_targets.add(n)
        st.rerun()
with ac3:
    if st.button("🗑️ Clear all", use_container_width=True, key="clear_all_targets"):
        st.session_state.selected_targets = set()
        st.rerun()
with ac4:
    if st.button(
        f"✅ Confirm & Generate Emails ({target_count})",
        type="primary",
        use_container_width=True,
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
tab1, tab2, tab3 = st.tabs(["📋 Companies List", "📊 Analytics", "✉️ Generated Emails"])

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
                        if st.button(btn_label, key=f"btn_{abs_idx}", use_container_width=True):
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
            st.plotly_chart(fig1, use_container_width=True)

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
                st.plotly_chart(fig2, use_container_width=True)

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
        st.plotly_chart(fig3, use_container_width=True)

with tab3:
    emails = st.session_state.generated_emails
    if not emails:
        st.info(
            "No emails generated yet. Pick targets above and click "
            "**✅ Confirm & Generate Emails** to run the Campaign Agent."
        )
    else:
        st.markdown(f"### ✉️ {len(emails)} personalized email(s) ready")
        st.caption(f"Full CSV saved to: `{CAMPAIGN_OUTPUT_PATH}`")
        for e in emails:
            with st.expander(f"📧 {e.get('company_name', '(unnamed)')} — {e.get('email_subject', '')}"):
                meta_l, meta_r = st.columns(2)
                with meta_l:
                    st.markdown(f"**Sector:** {e.get('sector', 'N/A')}")
                    st.markdown(f"**City:** {e.get('city', 'N/A')}")
                with meta_r:
                    st.markdown(f"**Suggested service:** {e.get('suggested_service', 'N/A')}")
                    st.markdown(f"**Goal:** {e.get('campaign_goal', 'N/A')}")
                st.markdown(f"**Subject:** {e.get('email_subject', '')}")
                st.text_area(
                    "Body",
                    value=e.get("email_body", ""),
                    height=240,
                    key=f"body_{e.get('company_name', '')}",
                )

st.markdown("---")
st.caption("Saudi Companies Directory • Built with Streamlit & Plotly")