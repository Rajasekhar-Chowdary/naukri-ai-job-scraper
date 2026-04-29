import streamlit as st
import os
import sys
import json
import math
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from src.scraper.scraper_cli import NaukriScraper, SALARY_BUCKETS, INDUSTRIES, WORK_MODES, TIME_PERIODS, clear_session_status
from src.dashboard.design import inject_css, page_header, section_header, top_nav

st.set_page_config(
    page_title="Scraper — Naukri AI Opportunity Finder",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
top_nav("pages/1_🕸️_Scraper.py")
page_header("Job Scraper", "Configure your search and scrape fresh listings directly from Naukri.com", eyebrow="🕸️ Visual Scraper")

# ══════════════════════════════════════════════════════════════════
#  CONFIG — load / save scraper defaults
# ══════════════════════════════════════════════════════════════════
config_path = os.path.join('config', 'profile_config.json')
config_data = {}

try:
    if os.path.exists(config_path):
        with open(config_path) as f:
            config_data = json.load(f)
except Exception:
    pass

scraper_defaults = config_data.get("scraper_defaults", {})


def _save_scraper_defaults(defaults: dict):
    config_data["scraper_defaults"] = defaults
    try:
        os.makedirs('config', exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        st.error(f"Failed to save defaults: {e}")


# ══════════════════════════════════════════════════════════════════
#  SCRAPER FORM
# ══════════════════════════════════════════════════════════════════
section_header("Search Configuration", "All fields except Designation are optional. Leave blank to skip that filter.")

col1, col2 = st.columns(2)

with col1:
    designation = st.text_input(
        "Designation *",
        value=scraper_defaults.get("designation", ""),
        placeholder="e.g. Data Analyst, Software Engineer"
    )
    location = st.text_input(
        "Location",
        value=scraper_defaults.get("location", ""),
        placeholder="e.g. Bangalore, Hyderabad, India, Remote"
    )
    experience = st.select_slider(
        "Experience (min years)",
        options=list(range(0, 21)),
        value=scraper_defaults.get("experience", 0),
        help="Filter jobs requiring at least this many years of experience."
    )
    salary = st.selectbox(
        "Salary (CTC)",
        options=list(SALARY_BUCKETS.keys()),
        index=list(SALARY_BUCKETS.keys()).index(scraper_defaults.get("salary", "Any")) if scraper_defaults.get("salary") in SALARY_BUCKETS else 0,
        help="Filter by expected salary range."
    )

with col2:
    industry = st.selectbox(
        "Industry",
        options=list(INDUSTRIES.keys()),
        index=list(INDUSTRIES.keys()).index(scraper_defaults.get("industry", "Any")) if scraper_defaults.get("industry") in INDUSTRIES else 0,
    )
    time_period = st.selectbox(
        "Time Period",
        options=list(TIME_PERIODS.keys()),
        index=list(TIME_PERIODS.keys()).index(scraper_defaults.get("time_period", "Last 3 days")) if scraper_defaults.get("time_period") in TIME_PERIODS else 2,
        help="Only show jobs posted within this timeframe."
    )
    max_jobs = st.radio(
        "How many jobs?",
        options=[50, 100, 200, 500],
        index=[50, 100, 200, 500].index(scraper_defaults.get("max_jobs", 100)) if scraper_defaults.get("max_jobs") in [50, 100, 200, 500] else 1,
        horizontal=True,
        help="Approximate number of jobs to collect. Each page yields ~20 jobs."
    )
    work_mode = st.multiselect(
        "Work Mode",
        options=list(WORK_MODES.keys()),
        default=scraper_defaults.get("work_mode", []),
        help="Select one or more work arrangements."
    )

headless = st.toggle("Headless Browser", value=scraper_defaults.get("headless", True),
                     help="Turn off to watch the browser automate. Slower but useful for debugging.")

# ══════════════════════════════════════════════════════════════════
#  SCRAPE TRIGGER
# ══════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)

start_col, clear_col, _ = st.columns([1.2, 1.2, 2.6])
with start_col:
    start_clicked = st.button("🚀 Start Scraping", type="primary", width="stretch")
with clear_col:
    if st.button("🗑️ Clear Scrape History", width="stretch", help="Deletes past scrape files so the deduplication system starts completely fresh."):
        cleared = 0
        if os.path.exists("data"):
            for f in os.listdir("data"):
                if f.startswith("naukri_") and f.endswith(".csv"):
                    try:
                        os.remove(os.path.join("data", f))
                        cleared += 1
                    except Exception:
                        pass
        st.success(f"History cleared! Deleted {cleared} old scrape files.")


# ── Pipeline stage renderer ─────────────────────────────────────
def render_pipeline(stage_name: str, stage_index: int, total_stages: int, message: str, jobs_found: int = 0):
    """Render a visual pipeline with checkmarks, current indicator, and pending."""
    stages = NaukriScraper.STAGES
    html = '<div class="pipeline-wrap">'
    for i, s in enumerate(stages):
        if i < stage_index:
            status = 'done'
            icon = '✓'
        elif i == stage_index:
            status = 'active'
            icon = '●'
        else:
            status = 'pending'
            icon = '○'
        html += f'<div class="pipeline-step {status}"><div class="pipeline-icon">{icon}</div><div class="pipeline-label">{s}</div></div>'
        if i < len(stages) - 1:
            html += f'<div class="pipeline-line {status}"></div>'
    html += '</div>'
    html += f'<div class="pipeline-msg">{message}</div>'
    if jobs_found > 0:
        html += f'<div class="pipeline-jobs">📋 {jobs_found} jobs collected</div>'
    return html


if start_clicked:
    if not designation or not designation.strip():
        st.error("Please enter a Designation.")
        st.stop()

    _save_scraper_defaults({
        "designation": designation, "location": location, "experience": experience,
        "salary": salary, "industry": industry, "time_period": time_period,
        "max_jobs": max_jobs, "work_mode": work_mode, "headless": headless,
    })

    days = TIME_PERIODS.get(time_period, 0)
    pages = math.ceil(max_jobs / 20)

    # Clear any old session
    clear_session_status()

    # Summary metrics
    st.markdown("""
    <div style="margin:16px 0 24px 0;">
      <p style="font-size:0.85rem; color:var(--t3); margin-bottom:8px;">Configuration Summary</p>
    </div>
    """, unsafe_allow_html=True)
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Designation", designation)
    with s2:
        st.metric("Location", location or "Any")
    with s3:
        st.metric("Target Jobs", max_jobs)
    with s4:
        st.metric("Pages", pages)

    # Progress containers
    pipeline_container = st.empty()
    progress_bar = st.progress(0, text="Initializing...")
    log_container = st.empty()

    def progress_callback(page_num, total_pages, jobs_found, stage_name, detail):
        stage_idx = NaukriScraper.STAGES.index(stage_name) if stage_name in NaukriScraper.STAGES else 0
        pct = int((page_num / total_pages) * 100) if total_pages > 0 else 0
        if stage_name == "AI Scoring":
            pct = 80
        elif stage_name == "Saving":
            pct = 95
        progress_bar.progress(min(pct, 100), text=f"{stage_name} — page {page_num}/{total_pages}")
        safe_detail = (detail or "")[:60]
        pipeline_container.markdown(
            render_pipeline(stage_name, stage_idx, len(NaukriScraper.STAGES),
                           f"Page {page_num}/{total_pages}: {safe_detail}..." if safe_detail else stage_name,
                           jobs_found),
            unsafe_allow_html=True
        )
        log_lines = [f"<div class='log-line'><span class='log-time'>{time.strftime('%H:%M:%S')}</span> {stage_name}: Page {page_num}/{total_pages} | {jobs_found} jobs</div>"]
        if detail:
            log_lines.append(f"<div class='log-line log-detail'>→ {detail[:100]}</div>")
        log_container.markdown(f"<div class='log-tail'>{''.join(log_lines)}</div>", unsafe_allow_html=True)

    # Pipeline CSS is already injected by inject_css() via GLASS_CSS — no duplication needed.

    with st.spinner("Scraping in progress..."):
        try:
            scraper = NaukriScraper(headless=headless)
            df, output_file = scraper.scrape(
                role=designation, location=location or "india", pages=pages, days=days,
                experience_min=experience if experience > 0 else None,
                salary_bucket=salary if salary != "Any" else None,
                industry_id=industry if industry != "Any" else None,
                work_mode=work_mode if work_mode else None,
                max_jobs=max_jobs, progress_callback=progress_callback,
            )
        except Exception as e:
            st.error(f"Scraping failed: {e}")
            st.stop()

    # Final state
    progress_bar.empty()
    pipeline_container.empty()
    log_container.empty()

    if df is not None and output_file:
        total = len(df)
        top = len(df[df['AI_Score'] >= 85]) if 'AI_Score' in df.columns else 0
        good = len(df[df['AI_Score'] >= 50]) if 'AI_Score' in df.columns else 0

        # Completion pipeline (all green)
        st.markdown(f"""
        <div class="pipeline-wrap">
          <div class="pipeline-step done"><div class="pipeline-icon">✓</div><div class="pipeline-label">Initializing</div></div>
          <div class="pipeline-line done"></div>
          <div class="pipeline-step done"><div class="pipeline-icon">✓</div><div class="pipeline-label">Fetching</div></div>
          <div class="pipeline-line done"></div>
          <div class="pipeline-step done"><div class="pipeline-icon">✓</div><div class="pipeline-label">Parsing</div></div>
          <div class="pipeline-line done"></div>
          <div class="pipeline-step done"><div class="pipeline-icon">✓</div><div class="pipeline-label">AI Scoring</div></div>
          <div class="pipeline-line done"></div>
          <div class="pipeline-step done"><div class="pipeline-icon">✓</div><div class="pipeline-label">Saving</div></div>
        </div>
        <div class="pipeline-msg" style="color:#34d399;font-weight:600;">✨ Scraping Complete — {total} jobs saved</div>
        """, unsafe_allow_html=True)

        st.balloons()

        st.success(f"Scraping complete! {total} jobs saved. {top} top matches, {good} good matches.")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Jobs Scraped", total)
        with m2:
            st.metric("Top Matches 85+", top)
        with m3:
            st.metric("Good Matches 50+", good)
        with m4:
            fname = os.path.basename(output_file)
            st.metric("Saved To", fname[:18] + "..." if len(fname) > 18 else fname)

        # Navigation removed — use the top navigation bar to switch pages
    else:
        st.warning("No jobs were found with the given filters. Try broadening your search.")

# ══════════════════════════════════════════════════════════════════
#  SCRAPER TIPS
# ══════════════════════════════════════════════════════════════════
st.divider()
section_header("Tips for Better Results", "")

st.markdown("""
<ul style="color:var(--t2); font-size:0.88rem; line-height:1.7;">
  <li><strong>Be specific with designations.</strong> "Data Analyst" yields better results than "Data".</li>
  <li><strong>Leave location empty</strong> to search all of India.</li>
  <li><strong>Time Period = "Last 24 hours"</strong> is great for daily monitoring of fresh jobs.</li>
  <li><strong>Experience filter</strong> matches the <em>minimum</em> years required by the job.</li>
  <li><strong>Salary & Industry filters</strong> may reduce results significantly — use them only if you have a strong preference.</li>
  <li><strong>Headless = ON</strong> runs faster. Turn it off only if you want to watch the browser work.</li>
</ul>
""", unsafe_allow_html=True)
