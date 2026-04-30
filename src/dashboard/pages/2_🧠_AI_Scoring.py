"""
AI Scoring — Production-Level Job Discovery Dashboard
Reads from SQLite, scores unscored jobs, manages feedback.
"""

import streamlit as st
import pandas as pd
import os
import sys
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from src.ai.ai_opportunity_finder import JobAIModel
from src.database import (
    init_db,
    get_jobs,
    save_feedback,
    get_feedback_counts,
    update_job_scores,
)
from src.dashboard.design import (
    inject_css,
    page_header,
    section_header,
    top_nav,
    score_badge,
    score_breakdown_bar,
    skill_coverage_ring,
    model_status_card,
    filter_chip,
    _flat,
)

st.set_page_config(
    page_title="AI Scoring — Dream Hunt", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed"
)
inject_css()
top_nav("pages/2_🧠_AI_Scoring.py")
page_header(
    "AI Job Scoring", "Browse AI-ranked listings, teach the model, and manage your profile", eyebrow="🧠 Smart Matching"
)

init_db()


# ── AI Model ─────────────────────────────────────────────────────
@st.cache_resource
def get_ai_model():
    return JobAIModel()


ai_model = get_ai_model()
if not hasattr(ai_model, "profile_skills"):
    st.cache_resource.clear()
    ai_model = get_ai_model()

# ── Session state ────────────────────────────────────────────────
if "ai_page_size" not in st.session_state:
    st.session_state.ai_page_size = 20
if "ai_page_offset" not in st.session_state:
    st.session_state.ai_page_offset = 0
if "_last_filter_state" not in st.session_state:
    st.session_state._last_filter_state = ""

config_path = os.path.join("config", "profile_config.json")
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
        os.makedirs("config", exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        st.error(f"Config save error: {e}")


# ── Data Loading ─────────────────────────────────────────────────
with st.spinner("Loading jobs from database..."):
    raw_jobs = get_jobs(limit=2000)

if not raw_jobs:
    st.warning("No job data found. Go to the **🕸️ Scraper** page to fetch jobs first.")
    if st.button("Go to Scraper", width="stretch"):
        st.switch_page("pages/1_🕸️_Scraper.py")
    st.stop()

df = pd.DataFrame(raw_jobs)

# Score any unscored jobs
unscored_mask = df["ai_score"].isna() | (df["ai_score"] == 0)
if unscored_mask.any():
    with st.spinner(f"AI is scoring {unscored_mask.sum()} new jobs..."):
        unscored_df = df[unscored_mask].copy()
        scored = ai_model.predict_with_breakdown(unscored_df)
        for _, row in scored.iterrows():
            update_job_scores(row["url"], row.to_dict())
    # Reload after scoring
    raw_jobs = get_jobs(limit=2000)
    df = pd.DataFrame(raw_jobs)

# Ensure breakdown columns exist
for col in ["Score_Skill", "Score_Title", "Score_Desc", "Score_Exp"]:
    if col not in df.columns:
        df[col] = 0
df = df.sort_values("ai_score", ascending=False).reset_index(drop=True)

# ── Stats Strip ──────────────────────────────────────────────────
_total = len(df)
_top = len(df[df["ai_score"] >= 85])
_good = len(df[df["ai_score"] >= 50])
_avg = int(df["ai_score"].mean()) if _total > 0 else 0
_applied = int(df["is_applied"].sum()) if "is_applied" in df.columns else 0
_rejected = int(df["is_rejected"].sum()) if "is_rejected" in df.columns else 0

st.markdown(
    _flat(
        f"""
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
  <div class="stat-strip-card">
    <div class="stat-strip-icon pink">📝</div>
    <div><div class="stat-strip-val">{_applied}</div><div class="stat-strip-lbl">Applied</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon red">❌</div>
    <div><div class="stat-strip-val">{_rejected}</div><div class="stat-strip-lbl">Rejected</div></div>
  </div>
</div>
"""
    ),
    unsafe_allow_html=True,
)

# ── Main Layout ──────────────────────────────────────────────────
section_header("Filters", "Refine your job search results")

all_companies = sorted(df["company"].dropna().unique()) if "company" in df.columns else []
all_locations = sorted(df["location"].dropna().unique()) if "location" in df.columns else []

f1, f2, f3 = st.columns(3)
with f1:
    search_query = st.text_input(
        "🔍 Search", placeholder="Title, company, skill...", label_visibility="collapsed", key="search_q"
    )
with f2:
    min_score = st.slider("Min Score", 0, 100, 0, key="min_score")
with f3:
    sort_by = st.selectbox("Sort by", ["AI Score ↓", "AI Score ↑", "Company A-Z"], key="sort_by")

f4, f5, f6, f7 = st.columns([1, 1, 1, 1])
with f4:
    sel_companies = st.multiselect("Company", options=all_companies, key="filter_company")
with f5:
    sel_locations = st.multiselect("Location", options=all_locations, key="filter_loc")
with f6:
    sel_source = st.multiselect("Source", sorted(df["source"].dropna().unique()), key="filter_source")
with f7:
    hide_applied = st.toggle("Hide Applied", value=False, key="hide_applied")
    hide_rejected = st.toggle("Hide Rejected", value=False, key="hide_rejected")

# Apply filters
fdf = df.copy()
fdf = fdf[fdf["ai_score"] >= min_score]
if search_query:
    q = search_query.lower()
    mask = (
        fdf["title"].astype(str).str.lower().str.contains(q, na=False)
        | fdf["company"].astype(str).str.lower().str.contains(q, na=False)
        | fdf["skills"].astype(str).str.lower().str.contains(q, na=False)
    )
    fdf = fdf[mask]
if sel_companies:
    fdf = fdf[fdf["company"].isin(sel_companies)]
if sel_locations:
    fdf = fdf[fdf["location"].isin(sel_locations)]
if sel_source:
    fdf = fdf[fdf["source"].isin(sel_source)]
if hide_applied and "is_applied" in fdf.columns:
    fdf = fdf[fdf["is_applied"] != 1]
if hide_rejected and "is_rejected" in fdf.columns:
    fdf = fdf[fdf["is_rejected"] != 1]

if sort_by == "AI Score ↓":
    fdf = fdf.sort_values("ai_score", ascending=False)
elif sort_by == "AI Score ↑":
    fdf = fdf.sort_values("ai_score", ascending=True)
elif sort_by == "Company A-Z":
    fdf = fdf.sort_values("company", ascending=True)

# ── Profile Context ──────────────────────────────────────────────
section_header("Profile Context", "Target roles and experience requirements")
p_exp, p_resume = st.columns([1, 1.2], gap="large")
with p_exp:
    cur_exp = config_data.get("min_experience_years", 0)
    new_exp = st.slider("Experience (years)", 0, 30, cur_exp)
    if new_exp != cur_exp:
        config_data["min_experience_years"] = new_exp
        _save_config()
        st.success(f"Updated to {new_exp} years")
        st.rerun()

with p_resume:
    uploaded_pdf = st.file_uploader("📄 Upload Resume / LinkedIn PDF", type=["pdf"], key="resume_uploader")
    if uploaded_pdf is not None:
        os.makedirs("data", exist_ok=True)
        with open(os.path.join("data", uploaded_pdf.name), "wb") as f:
            f.write(uploaded_pdf.getbuffer())
        st.success(f"Saved `{uploaded_pdf.name}`")

st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

left_col, right_col = st.columns([2.2, 1])

# ── Right Column: Intelligence Panel ─────────────────────────────
with right_col:
    st.markdown(
        '<div class="intel-card"><div class="intel-card-title">📊 Profile Intelligence</div>', unsafe_allow_html=True
    )
    coverage = ai_model.get_skill_coverage(df)
    st.markdown(
        skill_coverage_ring(coverage["coverage"], coverage["matched"], coverage["total_unique"]), unsafe_allow_html=True
    )
    if coverage["missing"]:
        st.markdown(
            "<div style='margin-top:10px;font-size:0.78rem;color:var(--t3);'>Top missing skills:</div>",
            unsafe_allow_html=True,
        )
        max_count = coverage["missing"][0][1] if coverage["missing"] else 1
        for skill, count in coverage["missing"][:5]:
            pct = int(count / max_count * 100)
            st.markdown(
                _flat(
                    f'<div class="missing-skill-row"><span class="missing-skill-name">{skill}</span><div class="missing-skill-bar"><div class="missing-skill-fill" style="width:{pct}%"></div></div><span class="missing-skill-count">{count}</span></div>'
                ),
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="intel-card"><div class="intel-card-title">🤖 AI Model Status</div>', unsafe_allow_html=True
    )
    model_info = ai_model.get_model_info()
    st.markdown(
        model_status_card(
            is_trained=model_info.get("loaded", False),
            samples=model_info.get("samples", 0),
            accuracy=model_info.get("accuracy_note", ""),
            trained_at=model_info.get("trained_at", "")[:10] if model_info.get("trained_at") else "",
        ),
        unsafe_allow_html=True,
    )
    if st.button("🔄 Retrain AI Model", width="stretch", type="primary"):
        with st.spinner("Training on your feedback..."):
            ok, msg = ai_model.train()
            (st.success if ok else st.error)(msg)
            if ok:
                st.cache_data.clear()
                st.cache_resource.clear()
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="intel-card"><div class="intel-card-title">🚀 Upskill Radar</div>', unsafe_allow_html=True)
    upskills = ai_model.get_upskill_recommendations(df, top_n=5)
    if upskills:
        max_count = upskills[0][1]
        for skill, count in upskills:
            pct = int(count / max_count * 100)
            st.markdown(
                _flat(
                    f'<div style="margin:6px 0;"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:3px;"><span style="font-size:0.85rem;font-weight:600;color:var(--t1);">{skill}</span><span style="font-size:0.72rem;color:var(--t3);">{count} listings</span></div><div style="background:var(--track);border-radius:50px;height:5px;overflow:hidden;"><div style="width:{pct}%;height:100%;background:linear-gradient(90deg,rgba(139,92,246,0.85),rgba(99,102,241,0.50));border-radius:50px;"></div></div></div>'
                ),
                unsafe_allow_html=True,
            )
    else:
        st.success("You cover all top market skills! 🎉")
    st.markdown("</div>", unsafe_allow_html=True)

# ── Left Column: Job Feed ────────────────────────────────────────
with left_col:
    _filter_state = f"{min_score}|{search_query}|{','.join(sorted(sel_companies))}|{','.join(sorted(sel_locations))}|{','.join(sorted(sel_source))}"
    if st.session_state._last_filter_state != _filter_state:
        st.session_state._last_filter_state = _filter_state
        st.session_state.ai_page_offset = 0

    total_filtered = len(fdf)

    active_filters = []
    if min_score > 0:
        active_filters.append(filter_chip(f"Score ≥ {min_score}", active=True))
    if sel_companies:
        active_filters.append(filter_chip(f"Companies ({len(sel_companies)})", active=True))
    if sel_locations:
        active_filters.append(filter_chip(f"Locations ({len(sel_locations)})", active=True))
    if sel_source:
        active_filters.append(filter_chip(f"Sources ({len(sel_source)})", active=True))
    if search_query:
        active_filters.append(filter_chip(f"Search: {search_query[:20]}", active=True))

    if active_filters:
        st.markdown(
            '<div style="display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 16px 0;">'
            + "".join(active_filters)
            + "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        f"<p style='font-size:0.85rem;color:var(--t3);margin:0 0 14px 0;'>Showing <strong style='color:var(--t1);'>{total_filtered}</strong> jobs</p>",
        unsafe_allow_html=True,
    )

    section_header("Job Feed", "AI-ranked opportunities")

    if total_filtered == 0:
        st.info("No jobs match your filters. Try broadening your search.")
    else:
        offset = st.session_state.ai_page_offset
        page_size = st.session_state.ai_page_size
        page_df = fdf.iloc[offset : offset + page_size]

        for idx, row in page_df.iterrows():
            score = int(row["ai_score"]) if pd.notna(row["ai_score"]) else 0
            url = str(row.get("url", "#"))
            is_applied = bool(row.get("is_applied", 0))
            is_rejected = bool(row.get("is_rejected", 0))

            if is_rejected:
                dot = "❌"
            elif is_applied:
                dot = "✅"
            else:
                dot = "🟢" if score >= 80 else ("🟡" if score >= 50 else "🔴")

            label = f"{dot} {score}% | {row['title']} at {row['company']}"
            exp_key = f"job_exp_{idx}"

            with st.expander(label, expanded=False):
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(score_badge(score, size="lg"), unsafe_allow_html=True)
                    st.caption("AI Score")
                with c2:
                    semantic = int(row.get("Score_Desc", score)) if pd.notna(row.get("Score_Desc")) else score
                    penalty = int(100 - row.get("Score_Exp", 100)) if pd.notna(row.get("Score_Exp")) else 0
                    st.markdown(score_breakdown_bar(semantic, penalty, score), unsafe_allow_html=True)

                pills = []
                for icon, key, bad in [
                    ("📍", "location", "Not mentioned"),
                    ("💼", "experience", "Not mentioned"),
                    ("📅", "posted", "N/A"),
                    ("🔗", "source", ""),
                ]:
                    v = str(row.get(key, "")).strip()
                    if v and v not in (bad, "nan", "", "None"):
                        pills.append(f'<span class="meta-pill">{icon} {v.title() if key == "source" else v}</span>')
                if pills:
                    st.markdown(f'<div class="job-meta">{ "".join(pills) }</div>', unsafe_allow_html=True)

                raw_skills = str(row.get("skills", "")).strip()
                if raw_skills and raw_skills not in ("N/A", "nan", ""):
                    slist = [s.strip() for s in raw_skills.split(",") if s.strip()][:12]
                    skills_html = "".join(f'<span class="skill-pill">{s}</span>' for s in slist)
                    st.markdown(f'<div class="skills-row">{skills_html}</div>', unsafe_allow_html=True)

                desc = str(row.get("description", "No description available.")).strip()
                st.markdown(
                    f"<p style='color:var(--td);font-size:13.5px;line-height:1.68;margin:0 0 14px 0;'>{desc}</p>",
                    unsafe_allow_html=True,
                )

                c1, c2, c3 = st.columns([1, 1, 3])
                with c1:
                    if is_applied:
                        st.button("✓ Applied", key=f"goodfit_{idx}", disabled=True, width="stretch")
                    else:
                        if st.button("👍 Good Fit", key=f"goodfit_{idx}", width="stretch"):
                            save_feedback(url, "applied")
                            st.rerun()
                with c2:
                    if is_rejected:
                        st.button("✕ Rejected", key=f"badfit_{idx}", disabled=True, width="stretch")
                    else:
                        if st.button("👎 Bad Fit", key=f"badfit_{idx}", width="stretch"):
                            save_feedback(url, "rejected")
                            st.rerun()
                with c3:
                    st.markdown(
                        f'<a href="{url}" target="_blank" class="naukri-link">View on {row.get("source", "Naukri").title()} →</a>',
                        unsafe_allow_html=True,
                    )

        # Pagination
        if total_filtered > page_size:
            col_prev, col_info, col_next = st.columns([1, 2, 1])
            with col_prev:
                if offset > 0:
                    if st.button("← Previous", width="stretch"):
                        st.session_state.ai_page_offset = max(0, offset - page_size)
                        st.rerun()
            with col_info:
                st.markdown(
                    f"<div style='text-align:center;color:var(--t3);font-size:0.85rem;padding-top:8px;'>Jobs {offset + 1}-{min(offset + page_size, total_filtered)} of {total_filtered}</div>",
                    unsafe_allow_html=True,
                )
            with col_next:
                if offset + page_size < total_filtered:
                    if st.button("Next →", width="stretch"):
                        st.session_state.ai_page_offset = offset + page_size
                        st.rerun()
            ps = st.selectbox(
                "Jobs per page", [10, 20, 50, 100], index=[10, 20, 50, 100].index(page_size), key="page_size_sel"
            )
            if ps != page_size:
                st.session_state.ai_page_size = ps
                st.session_state.ai_page_offset = 0
                st.rerun()

# ── Skills Management ────────────────────────────────────────────
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)
section_header("Skills Management", "Add or remove skills to improve AI matching")

sk_left, sk_right = st.columns([1, 2], gap="large")
with sk_left:
    new_skill = st.text_input(
        "Add skill", placeholder="e.g. Python, Tableau, AWS", key="skill_input", label_visibility="collapsed"
    )
    if st.button("➕ Add Skill", width="stretch") and new_skill:
        to_add = [s.strip() for s in new_skill.split(",") if s.strip()]
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
            unsafe_allow_html=True,
        )
        tags_html = "".join(
            f'<span class="skill-mgmt-tag" data-skill-idx="{i}" onclick="document.querySelector(\'[data-testid=\\"stAppViewBlockContainer\\"] .st-key-del_sk_{i} button\').click();">{s}</span>'
            for i, s in enumerate(current_skills)
        )
        st.markdown(f'<div class="skill-mgmt-cloud">{tags_html}</div>', unsafe_allow_html=True)
        st.markdown(
            """
        <style>
        div[class*="st-key-del_sk_"] { position:absolute !important; width:1px !important; height:1px !important; overflow:hidden !important; clip:rect(0,0,0,0) !important; }
        </style>
        """,
            unsafe_allow_html=True,
        )
        for i, skill in enumerate(current_skills):
            if st.button(f"del_{skill}", key=f"del_sk_{i}"):
                current_skills.remove(skill)
                config_data["profile_keywords"] = current_skills
                _save_config()
                st.rerun()
    else:
        st.markdown(
            "<div style='color:var(--t3);font-size:0.85rem;padding:20px 0;'>No skills configured yet. Add skills to improve AI matching!</div>",
            unsafe_allow_html=True,
        )
