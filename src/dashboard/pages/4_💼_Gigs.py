"""
Freelance Gigs Dashboard — Browse, score, and apply to freelance gigs.
"""

import streamlit as st
import pandas as pd
import os
import sys
import json
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.ai.ai_opportunity_finder import JobAIModel
from src.database import init_db, get_gigs, save_gig_feedback, get_gig_stats, update_gig_scores, get_gig_feedback_counts
from src.dashboard.design import inject_css, page_header, section_header, top_nav, score_badge, filter_chip, _flat

st.set_page_config(
    page_title="Gigs — Freelance Opportunities", page_icon="💼", layout="wide", initial_sidebar_state="collapsed"
)

inject_css()
top_nav("pages/4_💼_Gigs.py")
page_header(
    "Freelance Gigs",
    "Browse AI-ranked freelance opportunities from Freelancer.com, Guru, and more",
    eyebrow="💼 Gig Marketplace",
)

init_db()


@st.cache_resource
def get_ai_model():
    return JobAIModel()


ai_model = get_ai_model()

# ── Session state ────────────────────────────────────────────────
if "gig_page_size" not in st.session_state:
    st.session_state.gig_page_size = 20
if "gig_page_offset" not in st.session_state:
    st.session_state.gig_page_offset = 0
if "_last_gig_filter" not in st.session_state:
    st.session_state._last_gig_filter = ""

# ── Data Loading ─────────────────────────────────────────────────
with st.spinner("Loading gigs from database..."):
    raw_gigs = get_gigs(limit=2000)

if not raw_gigs:
    st.info("No gig data found. Go to the **🕸️ Scraper** page and select Freelancer or Guru to fetch gigs.")
    st.stop()

df = pd.DataFrame(raw_gigs)

# Score any unscored gigs
unscored_mask = df["ai_score"].isna() | (df["ai_score"] == 0)
if unscored_mask.any():
    with st.spinner(f"AI is scoring {unscored_mask.sum()} new gigs..."):
        unscored_df = df[unscored_mask].copy()
        scored = ai_model.predict_gig_scores(unscored_df)
        for _, row in scored.iterrows():
            update_gig_scores(row["url"], row.to_dict())
    raw_gigs = get_gigs(limit=2000)
    df = pd.DataFrame(raw_gigs)

for col in ["Score_Skill", "Score_Budget", "Score_Desc"]:
    if col not in df.columns:
        df[col] = 0

df = df.sort_values("ai_score", ascending=False).reset_index(drop=True)

# ── Stats Strip ──────────────────────────────────────────────────
_total = len(df)
_top = len(df[df["ai_score"] >= 85])
_good = len(df[df["ai_score"] >= 50])
_avg = int(df["ai_score"].mean()) if _total > 0 else 0

st.markdown(
    _flat(
        f"""
<div class="stat-strip fade-in">
  <div class="stat-strip-card"><div class="stat-strip-icon purple">💼</div><div><div class="stat-strip-val">{_total}</div><div class="stat-strip-lbl">Total Gigs</div></div></div>
  <div class="stat-strip-card"><div class="stat-strip-icon green">🏆</div><div><div class="stat-strip-val">{_top}</div><div class="stat-strip-lbl">Top 85+</div></div></div>
  <div class="stat-strip-card"><div class="stat-strip-icon amber">✅</div><div><div class="stat-strip-val">{_good}</div><div class="stat-strip-lbl">Good 50+</div></div></div>
  <div class="stat-strip-card"><div class="stat-strip-icon blue">📊</div><div><div class="stat-strip-val">{_avg}%</div><div class="stat-strip-lbl">Avg Score</div></div></div>
</div>
"""
    ),
    unsafe_allow_html=True,
)

# ── Filters ──────────────────────────────────────────────────────
section_header("Filters", "Refine your gig search")

all_clients = sorted(df["client"].dropna().unique()) if "client" in df.columns else []
all_sources = sorted(df["source"].dropna().unique()) if "source" in df.columns else []

f1, f2, f3, f4 = st.columns(4)
with f1:
    search_query = st.text_input(
        "🔍 Search", placeholder="Title, skill...", label_visibility="collapsed", key="gig_search"
    )
with f2:
    min_score = st.slider("Min Score", 0, 100, 0, key="gig_min_score")
with f3:
    sel_source = st.multiselect("Source", options=all_sources, key="gig_source")
with f4:
    hide_applied = st.toggle("Hide Applied", value=False, key="gig_hide_applied")
    hide_rejected = st.toggle("Hide Rejected", value=False, key="gig_hide_rejected")

# Apply filters
fdf = df.copy()
fdf = fdf[fdf["ai_score"] >= min_score]
if search_query:
    q = search_query.lower()
    mask = fdf["title"].astype(str).str.lower().str.contains(q, na=False) | fdf["skills"].astype(
        str
    ).str.lower().str.contains(q, na=False)
    fdf = fdf[mask]
if sel_source:
    fdf = fdf[fdf["source"].isin(sel_source)]
if hide_applied and "is_applied" in fdf.columns:
    fdf = fdf[fdf["is_applied"] != 1]
if hide_rejected and "is_rejected" in fdf.columns:
    fdf = fdf[fdf["is_rejected"] != 1]

fdf = fdf.sort_values("ai_score", ascending=False).reset_index(drop=True)

# ── Gig Feed ─────────────────────────────────────────────────────
section_header("Gig Feed", "AI-ranked freelance opportunities")

total_filtered = len(fdf)
if total_filtered == 0:
    st.info("No gigs match your filters.")
else:
    offset = st.session_state.gig_page_offset
    page_size = st.session_state.gig_page_size
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

        budget = ""
        if pd.notna(row.get("budget_min")) and pd.notna(row.get("budget_max")):
            curr = row.get("currency", "")
            btype = row.get("budget_type", "")
            budget = f" | {btype} {int(row['budget_min'])}-{int(row['budget_max'])} {curr}"

        proposals = row.get("proposals_count")
        prop_str = f" | {proposals} proposals" if pd.notna(proposals) else ""

        label = f"{dot} {score}% | {row['title'][:60]}{budget}{prop_str}"
        exp_key = f"gig_exp_{idx}"

        with st.expander(label, expanded=False):
            c1, c2 = st.columns([1, 4])
            with c1:
                st.markdown(score_badge(score, size="lg"), unsafe_allow_html=True)
                st.caption("AI Score")
            with c2:
                semantic = int(row.get("Score_Desc", score)) if pd.notna(row.get("Score_Desc")) else score
                st.markdown(f"Description match: {semantic}%", unsafe_allow_html=True)

            pills = []
            for icon, key, bad in [
                ("📍", "location", "Not mentioned"),
                ("💰", "budget_type", ""),
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
                    st.button("✓ Applied", key=f"gig_good_{idx}", disabled=True, width="stretch")
                else:
                    if st.button("👍 Good Fit", key=f"gig_good_{idx}", width="stretch"):
                        save_gig_feedback(url, "applied")
                        st.rerun()
            with c2:
                if is_rejected:
                    st.button("✕ Rejected", key=f"gig_bad_{idx}", disabled=True, width="stretch")
                else:
                    if st.button("👎 Bad Fit", key=f"gig_bad_{idx}", width="stretch"):
                        save_gig_feedback(url, "rejected")
                        st.rerun()
            with c3:
                st.markdown(
                    f'<a href="{url}" target="_blank" class="naukri-link">View on {row.get("source", "Freelancer").title()} →</a>',
                    unsafe_allow_html=True,
                )

    # Pagination
    if total_filtered > page_size:
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        with col_prev:
            if offset > 0:
                if st.button("← Previous", width="stretch"):
                    st.session_state.gig_page_offset = max(0, offset - page_size)
                    st.rerun()
        with col_info:
            st.markdown(
                f"<div style='text-align:center;color:var(--t3);font-size:0.85rem;padding-top:8px;'>Gigs {offset + 1}-{min(offset + page_size, total_filtered)} of {total_filtered}</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            if offset + page_size < total_filtered:
                if st.button("Next →", width="stretch"):
                    st.session_state.gig_page_offset = offset + page_size
                    st.rerun()

# ── AI Model Status ──────────────────────────────────────────────
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)
section_header("AI Model Status", "")

model_info = ai_model.get_model_info()
feedback_counts = get_gig_feedback_counts()
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Model Trained", "Yes" if model_info.get("loaded") else "No")
with col2:
    st.metric("Gig Feedback (Applied)", feedback_counts.get("applied", 0))
with col3:
    st.metric("Gig Feedback (Rejected)", feedback_counts.get("rejected", 0))

if st.button("🔄 Retrain AI Model on Gigs", type="primary"):
    with st.spinner("Training on gig feedback..."):
        ok, msg = ai_model.train()
        (st.success if ok else st.error)(msg)
        if ok:
            st.cache_data.clear()
            st.rerun()
