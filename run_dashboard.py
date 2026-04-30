#!/usr/bin/env python3
"""
Naukri AI Opportunity Finder — Dashboard Launcher
===================================================
A polished launcher that shows system status before opening
the Streamlit multi-page dashboard in your browser.
"""

import os
import sys
import glob
import platform
from datetime import datetime


def _color(text, code):
    return f"\033[{code}m{text}\033[0m"


def cyan(t):
    return _color(t, "96")


def green(t):
    return _color(t, "92")


def yellow(t):
    return _color(t, "93")


def dim(t):
    return _color(t, "90")


def bold(t):
    return _color(t, "1")


def violet(t):
    return _color(t, "95")


def print_splash():
    print()
    print(cyan("  ╔═══════════════════════════════════════════════════════════════╗"))
    print(cyan("  ║") + "                                                               " + cyan("║"))
    print(
        cyan("  ║")
        + "   "
        + bold(violet("✦  Naukri AI Opportunity Finder"))
        + "                                "
        + cyan("║")
    )
    print(cyan("  ║") + "      " + dim("AI-powered job scraping, scoring & analytics") + "              " + cyan("║"))
    print(cyan("  ║") + "                                                               " + cyan("║"))
    print(cyan("  ╚═══════════════════════════════════════════════════════════════╝"))
    print()


def print_status():
    # Count data files
    data_dir = "data"
    csv_files = glob.glob(os.path.join(data_dir, "*.csv")) if os.path.exists(data_dir) else []
    job_files = [f for f in csv_files if "applied" not in f and "rejected" not in f and "top_matches" not in f]

    # Last scrape time
    last_scrape = None
    if job_files:
        latest = max(job_files, key=os.path.getmtime)
        mtime = os.path.getmtime(latest)
        last_scrape = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")

    # Queue count
    queue_file = os.path.join(data_dir, "top_matches.csv")
    queue_count = 0
    if os.path.exists(queue_file):
        try:
            with open(queue_file) as f:
                queue_count = max(0, len(f.readlines()) - 1)
        except Exception:
            pass

    # Profile config
    config_path = "config/profile_config.json"
    skills_count = 0
    experience = 0
    if os.path.exists(config_path):
        try:
            import json

            with open(config_path) as f:
                cfg = json.load(f)
                skills_count = len(cfg.get("profile_keywords", []))
                experience = cfg.get("min_experience_years", 0)
        except Exception:
            pass

    print(dim("  ── System Status ──────────────────────────────────────────────"))
    print()
    print(f"  {green('●')}  Job datasets:      {bold(str(len(job_files)))} file(s)")
    if last_scrape:
        print(f"  {green('●')}  Last scrape:       {last_scrape}")
    print(f"  {green('●')}  Top matches queue: {bold(str(queue_count))} job(s)")
    print(f"  {green('●')}  Profile skills:    {bold(str(skills_count))} skill(s)")
    print(f"  {green('●')}  Experience set:    {bold(str(experience))} year(s)")
    print()
    print(dim("  ── Pages ──────────────────────────────────────────────────────"))
    print()
    print(f"  {cyan('🏠')}  Home        → Browse AI-ranked jobs")
    print(f"  {cyan('🕸️')}  Scraper     → Configure & run scrapes")
    print(f"  {cyan('📊')}  Analytics   → Charts & raw data")
    print()
    print(dim("  ── Launching ──────────────────────────────────────────────────"))
    print()


def main():
    # Ensure root is in path
    root = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(root)

    print_splash()
    print_status()

    # Launch Streamlit
    cmd = "streamlit run src/dashboard/app.py"
    print(f"  {dim('>')} {cmd}")
    print()

    # Send macOS notification
    if platform.system() == "Darwin":
        os.system('osascript -e \'display notification "Dashboard is starting..." with title "Naukri AI"\'')

    os.system(cmd)


if __name__ == "__main__":
    main()
