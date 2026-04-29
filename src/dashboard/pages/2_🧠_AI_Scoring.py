"""
AI Scoring — Production-Level Job Discovery Dashboard
======================================================
Two-column layout: Job feed (left) + Intelligence panel (right)
Features: score explainability, feedback state tracking, batch actions,
advanced filters, skill coverage, model status, upskill radar.
"""

import streamlit as st
import pandas as pd
import os
import sys
import json
import time
from glob import glob
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from src.ai.ai_opportunity_finder import JobAIModel
from src.dashboard.design import (
    inject_css, page_header, section_header, top_nav, score_badge,
    score_breakdown_bar, skill_coverage_ring, model_status_card,
    filter_chip, _flat
)

st.set_page_config(page_title="AI Scoring — Dream Hunt", page_icon="🧠", layout="wide",
                    initial_sidebar_state="collapsed")

inject_css()
top_nav("pages/2_🧠_AI_Scoring.py")
page_header("AI Job Scoring", "Browse AI-ranked listings, teach the model, and manage your profile",
            eyebrow="🧠 Smart Matching")

# ══════════════════════════════════════════════════════════════════
#  AI MODEL & SESSION STATE
# ══════════════════════════════════════════════════════════════════
@st.cache_resource
def get_ai_model():
    return JobAIModel()

ai_model = get_ai_model()
if not hasattr(ai_model, "profile_skills"):
    st.cache_resource.clear()
    ai_model = get_ai_model()

# Session state for pagination and filters
if "ai_page_size" not in st.session_state:
    st.session_state.ai_page_size = 20
if "ai_page_offset" not in st.session_state:
    st.session_state.ai_page_offset = 0
if "ai_filters" not in st.session_state:
    st.session_state.ai_filters = {}
if "rated_jobs" not in st.session_state:
    st.session_state.rated_jobs = {}  # url -> "applied" | "rejected"
if "_last_filter_state" not in st.session_state:
    st.session_state._last_filter_state = ""

config_path = os.path.join('config', 'profile_config.json')
config_data: dict = {}
current_skills: list = []

try:
    if os.path.exists(config_path):
        with open(config_path) as _f:
            config_data = json.load(_f)
            current_skills = config_data.get("profile_keywords", [])
except Exception as _e:
    st.error(f"Config load error: {_e}")


def _save_config():
    try:
        os.makedirs('config', exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        st.error(f"Config save error: {e}")


def _load_rated_jobs():
    """Load already-rated jobs into session state."""
    rated = {}
    for path, label in [("data/applied_jobs.csv", "applied"), ("data/rejected_jobs.csv", "rejected")]:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                for url in df.get('Job URL', []):
                    if pd.notna(url):
                        rated[str(url)] = label
            except Exception:
                pass
    return rated


# Initialize rated jobs once
if not st.session_state.rated_jobs:
    st.session_state.rated_jobs = _load_rated_jobs()


def save_feedback(row: pd.Series, filename: str, label: str):
    """Save feedback with deduplication and session tracking."""
    url = str(row.get('Job URL', ''))
    if url in st.session_state.rated_jobs:
        st.toast("Already rated this job!")
        return

    path = os.path.join('data', filename)
    os.makedirs('data', exist_ok=True)

    out = {
        "Title": row.get('Title', ''),
        "Company": row.get('Company', ''),
        "Location": row.get('Location', ''),
        "Experience": row.get('Experience', ''),
        "Description": row.get('Description', ''),
        "Skills": row.get('Skills', ''),
        "Job URL": url,
        "AI_Score": row.get('AI_Score', 0),
        "Feedback_Date": datetime.now().isoformat(),
        "Label": label,
    }
    
    df_new = pd.DataFrame([out])
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            df_old = pd.read_csv(path)
            pd.concat([df_old, df_new], ignore_index=True).to_csv(path, index=False)
        except Exception:
            import shutil
            shutil.copy(path, path + ".bak")
            df_new.to_csv(path, index=False)
    else:
        df_new.to_csv(path, index=False)

    st.session_state.rated_jobs[url] = label
    st.toast(f"Saved to {filename}")


# ══════════════════════════════════════════════════════════════════
#  DATA LOADING
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60)
def get_latest_data(folder: str = "data"):
    if not os.path.exists(folder):
        return None, None
    files = glob(os.path.join(folder, "*.csv"))
    files = [f for f in files if "applied_jobs" not in f and "rejected_jobs" not in f and "top_matches" not in f]
    if not files:
        return None, None
    latest = max(files, key=os.path.getmtime)
    return latest, pd.read_csv(latest)


latest_csv, df = get_latest_data()

if latest_csv is None or df is None:
    st.warning("No job data found. Go to the **🕸️ Scraper** page to fetch jobs first.")
    if st.button("Go to Scraper", width="stretch"):
        st.switch_page("pages/1_🕸️_Scraper.py")
    st.stop()

# Deduplicate
before = len(df)
df = df.drop_duplicates(subset=['Title', 'Company'], keep='first').reset_index(drop=True)

# Score if missing
if 'AI_Score' not in df.columns:
    with st.spinner("AI is scoring jobs..."):
        df = ai_model.predict_with_breakdown(df)
else:
    # Ensure breakdown columns exist
    if 'Score_Semantic' not in df.columns:
        df['Score_Semantic'] = df['AI_Score']
    if 'Score_ExpPenalty' not in df.columns:
        df['Score_ExpPenalty'] = 0

df = df.sort_values('AI_Score', ascending=False).reset_index(drop=True)

# ── Quick Stats Strip ────────────────────────────────────────
_total = len(df)
_top = len(df[df['AI_Score'] >= 85])
_good = len(df[df['AI_Score'] >= 50])
_avg = int(df['AI_Score'].mean()) if _total > 0 else 0
_dedup_note = f" · {before - len(df)} dupes removed" if before > len(df) else ""

st.markdown(_flat(f'''
<div class="stat-strip fade-in">
  <div class="stat-strip-card">
    <div class="stat-strip-icon purple">📋</div>
    <div><div class="stat-strip-val">{_total}</div><div class="stat-strip-lbl">Total Jobs</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon green">🏆</div>
    <div><div class="stat-strip-val">{_top}</div><div class="stat-strip-lbl">Top 85+</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon amber">✅</div>
    <div><div class="stat-strip-val">{_good}</div><div class="stat-strip-lbl">Good 50+</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon blue">📊</div>
    <div><div class="stat-strip-val">{_avg}%</div><div class="stat-strip-lbl">Avg Score</div></div>
  </div>
</div>
'''), unsafe_allow_html=True)
st.caption(f"Source: `{os.path.basename(latest_csv)}`{_dedup_note}")

# ══════════════════════════════════════════════════════════════════
#  MAIN LAYOUT
# ══════════════════════════════════════════════════════════════════

# ── TOP SECTION: Filters ─────────────────────────────────────
section_header("Filters", "Refine your job search results")

# Extract unique values for multi-select
all_companies = sorted(df['Company'].dropna().unique()) if 'Company' in df.columns else []
all_locations = sorted(df['Location'].dropna().unique()) if 'Location' in df.columns else []
all_exp_ranges = []
if 'Experience' in df.columns:
    for e in df['Experience'].dropna():
        nums = [int(x) for x in str(e).split() if x.isdigit()]
        if nums:
            label = f"{min(nums)}-{max(nums)} Yrs" if len(nums) > 1 else f"{nums[0]}+ Yrs"
            if label not in all_exp_ranges:
                all_exp_ranges.append(label)

f1, f2, f3 = st.columns(3)
with f1:
    search_query = st.text_input("🔍 Search", placeholder="Title, company, skill...",
                                 label_visibility="collapsed", key="search_q")
with f2:
    min_score = st.slider("Min Score", 0, 100, 0, key="min_score")
with f3:
    sort_by = st.selectbox("Sort by", ["AI Score ↓", "AI Score ↑", "Posted ↓", "Company A-Z"],
                           key="sort_by")

f4, f5, f6 = st.columns(3)
with f4:
    sel_companies = st.multiselect("Company", options=all_companies, key="filter_company")
with f5:
    sel_locations = st.multiselect("Location", options=all_locations, key="filter_loc")
with f6:
    sel_work_mode = st.multiselect("Work Mode", ["Remote", "Hybrid", "On-site"], key="filter_mode")

# Apply filters
fdf = df.copy()
fdf = fdf[fdf['AI_Score'] >= min_score]

if search_query:
    q = search_query.lower()
    mask = (
        fdf['Title'].astype(str).str.lower().str.contains(q, na=False) |
        fdf['Company'].astype(str).str.lower().str.contains(q, na=False) |
        fdf['Skills'].astype(str).str.lower().str.contains(q, na=False)
    )
    fdf = fdf[mask]

if sel_companies:
    fdf = fdf[fdf['Company'].isin(sel_companies)]
if sel_locations:
    fdf = fdf[fdf['Location'].isin(sel_locations)]
if sel_work_mode:
    mode_pattern = '|'.join(sel_work_mode)
    mode_mask = (
        fdf['Location'].astype(str).str.contains(mode_pattern, case=False, na=False) |
        fdf['Skills'].astype(str).str.contains(mode_pattern, case=False, na=False) |
        fdf['Description'].astype(str).str.contains(mode_pattern, case=False, na=False)
    )
    fdf = fdf[mode_mask]

# Sorting
if sort_by == "AI Score ↓":
    fdf = fdf.sort_values('AI_Score', ascending=False)
elif sort_by == "AI Score ↑":
    fdf = fdf.sort_values('AI_Score', ascending=True)
elif sort_by == "Company A-Z":
    fdf = fdf.sort_values('Company', ascending=True)
# Posted sort would need parsing posted dates



# ── Profile Context ──────────────────────────────────────────
section_header("Profile Context", "Target roles and experience requirements")
p_exp, p_resume = st.columns([1, 1.2], gap="large")

with p_exp:
    cur_exp = config_data.get("min_experience_years", 0)
    new_exp = st.slider("Experience (years)", 0, 30, cur_exp,
                        help="AI penalises jobs requiring significantly more or less experience.")
    if new_exp != cur_exp:
        config_data["min_experience_years"] = new_exp
        _save_config()
        st.success(f"Updated to {new_exp} years")
        st.rerun()

with p_resume:
    uploaded_pdf = st.file_uploader("📄 Upload Resume / LinkedIn PDF", type=['pdf'], key="resume_uploader", help="Upload your Resume or LinkedIn profile PDF.")
    if uploaded_pdf is not None:
        os.makedirs('data', exist_ok=True)
        with open(os.path.join('data', uploaded_pdf.name), "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        st.success(f"Saved `{uploaded_pdf.name}`")

    existing_pdfs = [f for f in os.listdir('data') if f.endswith('.pdf')] if os.path.exists('data') else []
    if existing_pdfs:
        st.markdown("""
        <style>
        div[class*="st-key-del_pdf_"] button {
            padding: 0 !important; min-height: 20px !important;
            border: none !important; background: transparent !important; color: var(--t3) !important;
        }
        div[class*="st-key-del_pdf_"] button:hover { color: #ef4444 !important; background: transparent !important; }
        </style>
        """, unsafe_allow_html=True)
        for pdf in existing_pdfs:
            c1, c2 = st.columns([0.85, 0.15])
            c1.markdown(f"<div style='font-size:0.8rem;padding-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'>📄 {pdf}</div>", unsafe_allow_html=True)
            if c2.button("✕", key=f"del_pdf_{pdf}", help="Delete", use_container_width=True):
                try:
                    os.remove(os.path.join('data', pdf))
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")


st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

left_col, right_col = st.columns([2.2, 1])

# ── RIGHT COLUMN: Intelligence Panel ────────────────────────────
with right_col:
    # Profile Intelligence
    st.markdown('<div class="intel-card"><div class="intel-card-title">📊 Profile Intelligence</div>', unsafe_allow_html=True)
    coverage = ai_model.get_skill_coverage(df)
    st.markdown(skill_coverage_ring(coverage["coverage"], coverage["matched"], coverage["total_unique"]),
                unsafe_allow_html=True)
    if coverage["missing"]:
        st.markdown("<div style='margin-top:10px;font-size:0.78rem;color:var(--t3);'>Top missing skills:</div>", unsafe_allow_html=True)
        max_count = coverage["missing"][0][1] if coverage["missing"] else 1
        for skill, count in coverage["missing"][:5]:
            pct = int(count / max_count * 100)
            st.markdown(_flat(f'<div class="missing-skill-row"><span class="missing-skill-name">{skill}</span><div class="missing-skill-bar"><div class="missing-skill-fill" style="width:{pct}%"></div></div><span class="missing-skill-count">{count}</span></div>'), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Model Status
    st.markdown('<div class="intel-card"><div class="intel-card-title">🤖 AI Model Status</div>', unsafe_allow_html=True)
    model_info = ai_model.get_model_info()
    st.markdown(model_status_card(
        is_trained=model_info.get("loaded", False),
        samples=model_info.get("samples", 0),
        accuracy=model_info.get("accuracy_note", ""),
        trained_at=model_info.get("trained_at", "")[:10] if model_info.get("trained_at") else ""
    ), unsafe_allow_html=True)
    if st.button("🔄 Retrain AI Model", width="stretch", type="primary"):
        with st.spinner("Training on your feedback..."):
            ok, msg = ai_model.train()
            (st.success if ok else st.error)(msg)
            if ok:
                st.cache_data.clear()
                st.cache_resource.clear()
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Upskill Radar
    st.markdown('<div class="intel-card"><div class="intel-card-title">🚀 Upskill Radar</div>', unsafe_allow_html=True)
    upskills = ai_model.get_upskill_recommendations(df, top_n=5)
    if upskills:
        max_count = upskills[0][1]
        for skill, count in upskills:
            pct = int(count / max_count * 100)
            st.markdown(_flat(f'<div style="margin:6px 0;"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;"><span style="font-size:0.85rem;font-weight:600;color:var(--t1);">{skill}</span><span style="font-size:0.72rem;color:var(--t3);">{count} listings</span></div><div style="background:var(--track);border-radius:50px;height:5px;overflow:hidden;"><div style="width:{pct}%;height:100%;background:linear-gradient(90deg,rgba(139,92,246,0.85),rgba(99,102,241,0.50));border-radius:50px;"></div></div></div>'), unsafe_allow_html=True)
    else:
        st.success("You cover all top market skills! 🎉")
    st.markdown('</div>', unsafe_allow_html=True)

    # Top Matches queue
    queue_path = "data/top_matches.csv"
    if os.path.exists(queue_path):
        try:
            qdf = pd.read_csv(queue_path)
            st.markdown(f'<div class="intel-card"><div class="intel-card-title">📬 Top Matches</div>', unsafe_allow_html=True)
            st.markdown(f"**{len(qdf)}** jobs queued")
            if st.button("View Queue", width="stretch"):
                st.dataframe(qdf[['Title', 'Company', 'AI_Score']].head(10), width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)
        except Exception:
            pass




# ── LEFT COLUMN: Filters & Job Feed ─────────────────────────────
with left_col:

    # Reset pagination to page 1 whenever any filter changes
    _filter_state = (
        f"{min_score}|{search_query}|{','.join(sorted(sel_companies))}"
        f"|{','.join(sorted(sel_locations))}|{','.join(sorted(sel_work_mode))}"
    )
    if st.session_state._last_filter_state != _filter_state:
        st.session_state._last_filter_state = _filter_state
        st.session_state.ai_page_offset = 0

    total_filtered = len(fdf)

    # Active filter chips
    active_filters = []
    if min_score > 0:
        active_filters.append(filter_chip(f"Score ≥ {min_score}", active=True))
    if sel_companies:
        active_filters.append(filter_chip(f"Companies ({len(sel_companies)})", active=True))
    if sel_locations:
        active_filters.append(filter_chip(f"Locations ({len(sel_locations)})", active=True))
    if sel_work_mode:
        active_filters.append(filter_chip(f"Mode ({len(sel_work_mode)})", active=True))
    if search_query:
        active_filters.append(filter_chip(f"Search: {search_query[:20]}", active=True))

    if active_filters:
        st.markdown('<div style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 16px 0;">' +
                    ''.join(active_filters) + '</div>', unsafe_allow_html=True)

    st.markdown(f"<p style='font-size:0.85rem;color:var(--t3);margin:0 0 14px 0;'>"
                f"Showing <strong style='color:var(--t1);'>{total_filtered}</strong> jobs</p>",
                unsafe_allow_html=True)

    # Job Feed
    section_header("Job Feed", "AI-ranked opportunities")

    if total_filtered == 0:
        st.info("No jobs match your filters. Try broadening your search.")
    else:
        offset = st.session_state.ai_page_offset
        page_size = st.session_state.ai_page_size
        page_df = fdf.iloc[offset:offset + page_size]  # Keep original unique index

        for idx, row in page_df.iterrows():
            score = int(row['AI_Score'])
            url = str(row.get('Job URL', '#'))
            is_rated = url in st.session_state.rated_jobs
            rating = st.session_state.rated_jobs.get(url, "")

            # Expander label
            if is_rated and rating == "rejected":
                dot = "❌"
            elif is_rated and rating == "applied":
                dot = "✅"
            else:
                if score >= 80:
                    dot = "🟢"
                elif score >= 50:
                    dot = "🟡"
                else:
                    dot = "🔴"
            
            label = f"{dot} {score}% | {row['Title']} at {row['Company']}"
            exp_key = f"job_exp_{idx}"

            with st.expander(label, expanded=False):
                # Score badge + breakdown
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(score_badge(score, size="lg"), unsafe_allow_html=True)
                    st.caption("AI Score")
                with c2:
                    semantic = int(row.get('Score_Semantic', score))
                    penalty = int(row.get('Score_ExpPenalty', 0))
                    st.markdown(score_breakdown_bar(semantic, penalty, score), unsafe_allow_html=True)

                # Meta pills
                pills = []
                for icon, key, bad in [("📍", "Location", "Not mentioned"),
                                        ("💼", "Experience", "Not mentioned"),
                                        ("📅", "Posted", "N/A")]:
                    v = str(row.get(key, '')).strip()
                    if v and v not in (bad, 'nan', ''):
                        pills.append(f'<span class="meta-pill">{icon} {v}</span>')
                if pills:
                    st.markdown(f'<div class="job-meta">{ "".join(pills) }</div>', unsafe_allow_html=True)

                # Skills
                raw_skills = str(row.get('Skills', '')).strip()
                if raw_skills and raw_skills not in ('N/A', 'nan'):
                    slist = [s.strip() for s in raw_skills.split(',') if s.strip()][:12]
                    skills_html = ''.join(f'<span class="skill-pill">{s}</span>' for s in slist)
                    st.markdown(f'<div class="skills-row">{skills_html}</div>', unsafe_allow_html=True)

                # Description
                desc = str(row.get('Description', 'No description available.')).strip()
                st.markdown(f"<p style='color:var(--td);font-size:13.5px;line-height:1.68;margin:0 0 14px 0;'>{desc}</p>",
                            unsafe_allow_html=True)

                # Actions
                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    btn_key = f"goodfit_{idx}"
                    if is_rated and rating == "applied":
                        st.button("✓ Applied", key=btn_key, disabled=True, width="stretch")
                    else:
                        if st.button("👍 Good Fit", key=btn_key, width="stretch"):
                            save_feedback(row, "applied_jobs.csv", "applied")
                            st.rerun()
                with c2:
                    btn_key = f"badfit_{idx}"
                    if is_rated and rating == "rejected":
                        st.button("✕ Rejected", key=btn_key, disabled=True, width="stretch")
                    else:
                        if st.button("👎 Bad Fit", key=btn_key, width="stretch"):
                            save_feedback(row, "rejected_jobs.csv", "rejected")
                            st.rerun()
                with c3:
                    st.markdown(f'<a href="{url}" target="_blank" class="naukri-link">View on Naukri →</a>',
                                unsafe_allow_html=True)

        # Pagination
        if total_filtered > page_size:
            col_prev, col_info, col_next = st.columns([1, 2, 1])
            with col_prev:
                if offset > 0:
                    if st.button("← Previous", width="stretch"):
                        st.session_state.ai_page_offset = max(0, offset - page_size)
                        st.rerun()
            with col_info:
                st.markdown(f"<div style='text-align:center;color:var(--t3);font-size:0.85rem;padding-top:8px;'>"
                            f"Jobs {offset + 1}-{min(offset + page_size, total_filtered)} of {total_filtered}</div>",
                            unsafe_allow_html=True)
            with col_next:
                if offset + page_size < total_filtered:
                    if st.button("Next →", width="stretch"):
                        st.session_state.ai_page_offset = offset + page_size
                        st.rerun()

            # Page size selector
            ps = st.selectbox("Jobs per page", [10, 20, 50, 100],
                              index=[10, 20, 50, 100].index(page_size), key="page_size_sel")
            if ps != page_size:
                st.session_state.ai_page_size = ps
                st.session_state.ai_page_offset = 0
                st.rerun()

# ══════════════════════════════════════════════════════════════════
#  SKILLS MANAGEMENT (Bottom Section)
# ══════════════════════════════════════════════════════════════════
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)
section_header("Skills Management", "Add or remove skills to improve AI matching")

sk_left, sk_right = st.columns([1, 2], gap="large")

with sk_left:
    new_skill = st.text_input("Add skill", placeholder="e.g. Python, Tableau, AWS", key="skill_input", label_visibility="collapsed")
    if st.button("➕ Add Skill", width="stretch") and new_skill:
        to_add = [s.strip() for s in new_skill.split(',') if s.strip()]
        added = [s for s in to_add if s not in current_skills]
        if added:
            current_skills.extend(added)
            config_data["profile_keywords"] = current_skills
            _save_config()
            st.success(f"Added {len(added)} skill(s)!")
            time.sleep(0.3)
            st.rerun()
        else:
            st.warning("All skill(s) already exist.")

with sk_right:
    if current_skills:
        st.markdown(
            f"<div style='font-size:0.75rem;color:var(--t3);margin-bottom:6px;'>Active skills ({len(current_skills)}) — hover to delete:</div>",
            unsafe_allow_html=True
        )

        # Render interactive skill tags (HTML) + hidden Streamlit buttons for deletion
        tags_html = ''.join(
            f'<span class="skill-mgmt-tag" data-skill-idx="{i}" onclick="'
            f"document.querySelector('[data-testid=\\\"stAppViewBlockContainer\\\"] "
            f".st-key-del_sk_{i} button').click();"
            f'">{s}</span>'
            for i, s in enumerate(current_skills)
        )
        st.markdown(f'<div class="skill-mgmt-cloud">{tags_html}</div>', unsafe_allow_html=True)

        # Hidden delete buttons (CSS-hidden, triggered by JS onclick above)
        st.markdown("""
        <style>
        div[class*="st-key-del_sk_"] { position:absolute !important; width:1px !important; height:1px !important; overflow:hidden !important; clip:rect(0,0,0,0) !important; }
        </style>
        """, unsafe_allow_html=True)
        for i, skill in enumerate(current_skills):
            if st.button(f"del_{skill}", key=f"del_sk_{i}"):
                current_skills.remove(skill)
                config_data["profile_keywords"] = current_skills
                _save_config()
                st.rerun()
    else:
        st.markdown(
            "<div style='color:var(--t3);font-size:0.85rem;padding:20px 0;'>"
            "No skills configured yet. Add skills to improve AI matching!</div>",
            unsafe_allow_html=True
        )



