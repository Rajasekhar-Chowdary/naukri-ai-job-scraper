import streamlit as st
import os
import sys
import glob
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.dashboard.design import inject_css, welcome_card, top_nav

st.set_page_config(
    page_title="Dream Hunt — Naukri AI Opportunity Finder",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
top_nav("app.py")

# ══════════════════════════════════════════════════════════════════
#  WELCOME / LANDING PAGE  —  Dream Hunt
# ══════════════════════════════════════════════════════════════════

# Hero
st.markdown("""
<div style="text-align:center; padding:40px 0 30px 0;">
  <div class="eyebrow" style="margin-bottom:18px;">✦ AI-Powered Career Discovery</div>
  <div class="welcome-title-big" style="font-size:clamp(2.2rem,6vw,3.6rem); margin-bottom:16px;">
    Welcome to <span style="color:#c4b5fd;">Dream Hunt</span>
  </div>
  <p style="font-size:1.05rem; color:var(--t3); max-width:560px; margin:0 auto 40px; line-height:1.7;">
    Your intelligent companion for discovering, scoring, and analysing job opportunities on Naukri.com.
    Upload your profile, scrape fresh listings, and let AI rank the best matches for you.
  </p>
</div>
""", unsafe_allow_html=True)

# System status bar
status_html = ""
data_dir = "data"
csv_files = glob.glob(os.path.join(data_dir, "*.csv")) if os.path.exists(data_dir) else []
job_files = [f for f in csv_files if "applied" not in f and "rejected" not in f and "top_matches" not in f]

last_scrape = None
if job_files:
    latest = max(job_files, key=os.path.getmtime)
    mtime = os.path.getmtime(latest)
    last_scrape = datetime.fromtimestamp(mtime).strftime("%d %b %Y, %H:%M")

queue_count = 0
queue_file = os.path.join(data_dir, "top_matches.csv")
if os.path.exists(queue_file):
    try:
        with open(queue_file) as f:
            queue_count = max(0, len(f.readlines()) - 1)
    except Exception:
        pass

st.markdown(f"""
<div style="max-width:720px; margin:0 auto 40px;">
  <div class="dash-card-outer">
    <div class="dash-card-inner" style="display:flex; align-items:center; justify-content:center; gap:32px; flex-wrap:wrap; text-align:center;">
      <div>
        <div style="font-size:1.6rem; font-weight:800; color:var(--t1);">{len(job_files)}</div>
        <div style="font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--t3); margin-top:4px;">Datasets</div>
      </div>
      <div style="width:1px; height:36px; background:var(--div);"></div>
      <div>
        <div style="font-size:1.6rem; font-weight:800; color:var(--t1);">{last_scrape or "—"}</div>
        <div style="font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--t3); margin-top:4px;">Last Scrape</div>
      </div>
      <div style="width:1px; height:36px; background:var(--div);"></div>
      <div>
        <div style="font-size:1.6rem; font-weight:800; color:var(--t1);">{queue_count}</div>
        <div style="font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--t3); margin-top:4px;">In Queue</div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# How it works — 4 step cards
st.markdown("""
<div style="text-align:center; margin-bottom:12px;">
  <div style="font-size:1.15rem; font-weight:700; color:var(--t1); margin-bottom:6px;">How it works</div>
  <div style="font-size:0.85rem; color:var(--t3);">Four simple steps from search to insight</div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="welcome-grid" style="max-width:900px; margin:0 auto;">
  {welcome_card("Step 1", "🕸️ Scrape", "Configure your search — designation, location, experience, salary, industry, and time period. One click launches the browser scraper and collects fresh listings from Naukri.com.")}
  {welcome_card("Step 2", "🧠 AI Scoring", "The AI reads your profile (skills, experience, resume PDF) and scores every job 0–100. Teach the AI by marking Good Fit / Bad Fit. Retrain the model anytime.")}
  {welcome_card("Step 3", "📋 Browse Jobs", "Explore AI-ranked job cards with colour-coded scores. Filter by score, search by skill or company, and view full descriptions with direct Naukri links.")}
  {welcome_card("Step 4", "📊 Dashboard", "Deep-dive analytics — top hiring companies, score distribution, location heatmaps, and raw data export. Everything you need to understand the market.")}
</div>
""", unsafe_allow_html=True)

# CTA removed — use the top navigation bar to switch pages

# Footer
st.markdown("""
<div style="text-align:center; margin-top:48px; padding-top:24px; border-top:1px solid var(--div);">
  <p style="font-size:0.78rem; color:var(--t3);">
    Dream Hunt · Naukri AI Opportunity Finder · Built with Streamlit & Selenium
  </p>
</div>
""", unsafe_allow_html=True)
