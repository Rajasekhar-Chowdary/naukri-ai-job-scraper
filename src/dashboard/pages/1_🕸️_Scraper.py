import streamlit as st
import os
import sys
import json
import math
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.scraper.naukri import NaukriScraper, SALARY_BUCKETS, INDUSTRIES, WORK_MODES, TIME_PERIODS, clear_session_status
from src.scraper.linkedin import LinkedInScraper
from src.scraper.indeed import IndeedScraper
from src.scraper.multi_runner import MultiScraperRunner
from src.database import init_db, get_latest_scrapes
from src.dashboard.design import inject_css, page_header, section_header, top_nav

st.set_page_config(
    page_title="Scraper — Naukri AI Opportunity Finder", page_icon="🕸️", layout="wide", initial_sidebar_state="collapsed"
)

inject_css()
top_nav("pages/1_🕸️_Scraper.py")
page_header(
    "Job Scraper",
    "Configure your search and scrape fresh listings from multiple sources",
    eyebrow="🕸️ Multi-Source Scraper",
)

init_db()

# ── Config ───────────────────────────────────────────────────────
config_path = os.path.join("config", "profile_config.json")
config_data = {}
try:
    if os.path.exists(config_path):
        with open(config_path) as f:
            config_data = json.load(f)
except Exception:
    pass

scraper_defaults = config_data.get("scraper_defaults", {})

# ── Source selector ──────────────────────────────────────────────
st.markdown(
    "<div style='margin-bottom:8px;'><span style='font-size:0.85rem;font-weight:600;color:var(--t1);'>Job Source</span></div>",
    unsafe_allow_html=True,
)
source = st.segmented_control(
    "", ["Naukri", "LinkedIn", "Indeed", "All Sources"], default="Naukri", label_visibility="collapsed"
)

# ── Form ─────────────────────────────────────────────────────────
section_header("Search Configuration", "All fields except Designation are optional.")

col1, col2 = st.columns(2)
with col1:
    designation = st.text_input(
        "Designation *",
        value=scraper_defaults.get("designation", ""),
        placeholder="e.g. Data Analyst, Software Engineer",
    )
    location = st.text_input(
        "Location", value=scraper_defaults.get("location", ""), placeholder="e.g. Bangalore, Hyderabad, India, Remote"
    )
    experience = st.select_slider(
        "Experience (min years)", options=list(range(0, 21)), value=scraper_defaults.get("experience", 0)
    )
    if source in ("Naukri", "All Sources"):
        salary = st.selectbox(
            "Salary (CTC)",
            options=list(SALARY_BUCKETS.keys()),
            index=(
                list(SALARY_BUCKETS.keys()).index(scraper_defaults.get("salary", "Any"))
                if scraper_defaults.get("salary") in SALARY_BUCKETS
                else 0
            ),
        )

with col2:
    if source in ("Naukri", "All Sources"):
        industry = st.selectbox(
            "Industry",
            options=list(INDUSTRIES.keys()),
            index=(
                list(INDUSTRIES.keys()).index(scraper_defaults.get("industry", "Any"))
                if scraper_defaults.get("industry") in INDUSTRIES
                else 0
            ),
        )
        time_period = st.selectbox(
            "Time Period",
            options=list(TIME_PERIODS.keys()),
            index=(
                list(TIME_PERIODS.keys()).index(scraper_defaults.get("time_period", "Last 3 days"))
                if scraper_defaults.get("time_period") in TIME_PERIODS
                else 2
            ),
        )
    else:
        industry = "Any"
        time_period = "Last 3 days"
    max_jobs = st.radio(
        "How many jobs?",
        options=[50, 100, 200, 500],
        index=(
            [50, 100, 200, 500].index(scraper_defaults.get("max_jobs", 100))
            if scraper_defaults.get("max_jobs") in [50, 100, 200, 500]
            else 1
        ),
        horizontal=True,
    )
    if source in ("Naukri", "All Sources"):
        work_mode = st.multiselect(
            "Work Mode", options=list(WORK_MODES.keys()), default=scraper_defaults.get("work_mode", [])
        )
    else:
        work_mode = []

headless = st.toggle("Headless Browser", value=scraper_defaults.get("headless", True))

# ── Trigger ──────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
start_col, _ = st.columns([1.2, 3.8])
with start_col:
    start_clicked = st.button("🚀 Start Scraping", type="primary", width="stretch")

if start_clicked:
    if not designation or not designation.strip():
        st.error("Please enter a Designation.")
        st.stop()

    clear_session_status()
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.metric("Source", source)
    with s2:
        st.metric("Location", location or "Any")
    with s3:
        st.metric("Target Jobs", max_jobs)
    with s4:
        pages = math.ceil(max_jobs / 20)
        st.metric("Pages", pages)

    progress_bar = st.progress(0, text="Initializing...")
    log_container = st.empty()

    def progress_callback(src, page_num, total_pages, jobs_found, stage_name, detail):
        pct = int((page_num / total_pages) * 100) if total_pages > 0 else 50
        progress_bar.progress(min(pct, 100), text=f"{src.title()} — {stage_name} page {page_num}/{total_pages}")
        log_container.markdown(
            f"<div class='log-tail'><div class='log-line'><span class='log-time'>{time.strftime('%H:%M:%S')}</span> "
            f"<b>{src.title()}</b> {stage_name}: Page {page_num}/{total_pages} | {jobs_found} jobs</div></div>",
            unsafe_allow_html=True,
        )

    with st.spinner("Scraping in progress..."):
        if source == "All Sources":
            runner = MultiScraperRunner(headless=headless)
            days = TIME_PERIODS.get(time_period, 0)
            results = runner.run_all(
                role=designation,
                location=location or "india",
                sources=["naukri", "linkedin", "indeed"],
                pages=pages,
                days=days,
                experience_min=experience if experience > 0 else None,
                max_jobs=max_jobs,
                progress_callback=progress_callback,
                salary_bucket=salary if salary != "Any" else None,
                industry_id=industry if industry != "Any" else None,
                work_mode=work_mode if work_mode else None,
            )
            total_found = sum(r.get("jobs_found", 0) for r in results.values())
            total_new = sum(r.get("new_jobs", 0) for r in results.values())
            errors = [f"{s}: {r['error']}" for s, r in results.items() if r.get("error")]

            progress_bar.empty()
            log_container.empty()

            if errors:
                st.error("Some scrapers failed:\n" + "\n".join(errors))
            if total_new > 0:
                st.success(f"Scraping complete! {total_found} jobs found, {total_new} new saved to database.")
                st.balloons()
            else:
                st.warning("No new jobs found with the given filters. Try broadening your search.")

            # Per-source breakdown
            st.divider()
            st.subheader("Results by Source")
            for src, r in results.items():
                emoji = "🟢" if not r.get("error") else "🔴"
                st.markdown(f"{emoji} **{src.title()}** — Found {r.get('jobs_found', 0)} ({r.get('new_jobs', 0)} new)")
        else:
            if source == "Naukri":
                scraper = NaukriScraper(headless=headless)
                days = TIME_PERIODS.get(time_period, 0)
                result = scraper.run(
                    role=designation,
                    location=location or "india",
                    pages=pages,
                    days=days,
                    experience_min=experience if experience > 0 else None,
                    salary_bucket=salary if salary != "Any" else None,
                    industry_id=industry if industry != "Any" else None,
                    work_mode=work_mode if work_mode else None,
                    max_jobs=max_jobs,
                    progress_callback=lambda p, t, j, s, d: progress_callback("naukri", p, t, j, s, d),
                )
            elif source == "LinkedIn":
                scraper = LinkedInScraper(headless=headless)
                result = scraper.run(
                    role=designation,
                    location=location or "India",
                    pages=pages,
                    max_jobs=max_jobs,
                    progress_callback=lambda p, t, j, s, d: progress_callback("linkedin", p, t, j, s, d),
                )
            elif source == "Indeed":
                scraper = IndeedScraper(headless=headless)
                result = scraper.run(
                    role=designation,
                    location=location or "India",
                    pages=pages,
                    max_jobs=max_jobs,
                    progress_callback=lambda p, t, j, s, d: progress_callback("indeed", p, t, j, s, d),
                )
            else:
                st.error("Unknown source")
                st.stop()

            progress_bar.empty()
            log_container.empty()

            if result.get("error"):
                st.error(f"Scraping failed: {result['error']}")
            elif result.get("new_jobs", 0) > 0:
                st.success(
                    f"Scraping complete! {result['jobs_found']} jobs found, {result['new_jobs']} new saved to database."
                )
                st.balloons()
            else:
                st.warning("No new jobs found with the given filters. Try broadening your search.")

# ── Recent scrapes ───────────────────────────────────────────────
st.divider()
section_header("Recent Scrapes", "")
scrapes = get_latest_scrapes(5)
if scrapes:
    for s in scrapes:
        status_color = "🟢" if s["status"] == "completed" else "🔴"
        st.markdown(
            f"{status_color} **{s['source'].title()}** — {s['role']} in {s['location']} | Found {s['jobs_found']} ({s['new_jobs']} new) | {s['started_at'][:16]}"
        )
else:
    st.caption("No scrape history yet.")
