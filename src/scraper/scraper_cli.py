import argparse
import pandas as pd
import time
import random
import os
import math
import json
from datetime import datetime
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from src.ai.ai_opportunity_finder import JobAIModel
from src.utils.logger import setup_logger

logger = setup_logger("Scraper")

# ── Session status file for live dashboard tracking ─────────────
SESSION_STATUS_PATH = os.path.join("data", ".scrape_session.json")

# Retry config
_MAX_PAGE_RETRIES = 2
_RETRY_WAIT_MIN = 4.0
_RETRY_WAIT_MAX = 8.0


def _write_session_status(status: dict):
    """Write scrape session status for the dashboard to read."""
    try:
        os.makedirs("data", exist_ok=True)
        with open(SESSION_STATUS_PATH, "w") as f:
            json.dump(status, f)
    except Exception:
        pass


def clear_session_status():
    """Clear the session status file."""
    if os.path.exists(SESSION_STATUS_PATH):
        try:
            os.remove(SESSION_STATUS_PATH)
        except Exception:
            pass


# ── Naukri filter mappings ──────────────────────────────────────
SALARY_BUCKETS = {
    "Any": None,
    "0 - 3 Lakhs": "0to3",
    "3 - 6 Lakhs": "3to6",
    "6 - 10 Lakhs": "6to10",
    "10 - 15 Lakhs": "10to15",
    "15 - 25 Lakhs": "15to25",
    "25+ Lakhs": "25to50",
}

INDUSTRIES = {
    "Any": None,
    "IT - Software": "3",
    "IT - Hardware / Networking": "5",
    "Banking / Financial Services": "8",
    "Insurance": "9",
    "Healthcare / Medical": "12",
    "Education / Teaching": "15",
    "Telecom / ISP": "18",
    "Automobile / Auto Ancillaries": "20",
    "Construction / Engineering": "22",
    "FMCG / Foods / Beverage": "25",
    "Retail / E-commerce": "28",
    "Media / Entertainment": "30",
    "BPO / Call Center": "33",
    "Manufacturing / Industrial": "35",
    "Pharma / Biotech": "38",
    "Hospitality / Travel": "40",
    "Real Estate / Property": "42",
}

WORK_MODES = {
    "On-site": "0",
    "Hybrid": "1",
    "Remote": "2",
}

TIME_PERIODS = {
    "Any time": 0,
    "Last 24 hours": 1,
    "Last 3 days": 3,
    "Last 7 days": 7,
    "Last 15 days": 15,
    "Last 30 days": 30,
}


def build_naukri_url(
    role, location, page_num=1, days=0, experience_min=None, salary_bucket=None, industry_id=None, work_mode=None
):
    """Build a Naukri search URL with query parameters."""
    formatted_role = role.replace(" ", "-").lower()
    loc = location.lower().strip() if location else ""

    loc_path = f"-in-{loc}" if loc else ""
    page_path = f"-{page_num}" if page_num > 1 else ""

    url = f"https://www.naukri.com/{formatted_role}-jobs{loc_path}{page_path}"

    params = {}
    params["k"] = role
    if location:
        params["l"] = location
    if days > 0:
        params["jobAge"] = days
    if experience_min is not None and experience_min > 0:
        params["experience"] = experience_min
    if salary_bucket and salary_bucket in SALARY_BUCKETS and SALARY_BUCKETS[salary_bucket]:
        params["ctcFilter"] = SALARY_BUCKETS[salary_bucket]
    if industry_id and industry_id in INDUSTRIES and INDUSTRIES[industry_id]:
        params["functionAreaIdGid"] = INDUSTRIES[industry_id]
    if work_mode:
        mode_vals = [WORK_MODES[m] for m in work_mode if m in WORK_MODES]
        if mode_vals:
            for mv in mode_vals:
                params.setdefault("wfhType", []).append(mv)
            if len(params["wfhType"]) == 1:
                params["wfhType"] = params["wfhType"][0]

    if params:
        url += "?" + urlencode(params, doseq=True)

    return url


class NaukriScraper:
    STAGES = ["Initializing", "Fetching", "Parsing", "AI Scoring", "Saving"]

    # ── CSS selector sets with fallbacks ──────────────────────────
    _CARD_SELECTORS = [
        "div.srp-jobtuple-wrapper",
        "article.jobTuple",
        "div.jobTuple",
    ]
    _TITLE_SELECTORS = ["a.title", "a[class*='title']"]
    _COMPANY_SELECTORS = ["a.comp-name", "a[class*='comp-name']", "span[class*='comp-name']"]
    _LOCATION_SELECTORS = ["span.locWdth", "span[class*='locWdth']", "li[class*='location'] span"]
    _EXPERIENCE_SELECTORS = ["span.expwdth", "span[class*='expwdth']", "li[class*='experience'] span"]
    _DESC_SELECTORS = ["span.job-desc", "span[class*='job-desc']", "div[class*='job-desc']"]
    _POSTED_SELECTORS = ["span.job-post-day", "span[class*='job-post-day']", "span[class*='postDay']"]
    _TAGS_SELECTORS = ["ul.tags-gt li", "ul[class*='tags'] li", "li[class*='tag']"]

    def __init__(self, headless=True):
        logger.info("Initializing Chrome WebDriver...")
        self._update_stage("Initializing", 0, "Starting Chrome WebDriver...")
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("WebDriver initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            self._update_stage("Initializing", 0, f"Error: {e}", error=True)
            # Raise so the UI can catch and display the error — never kill the server
            raise RuntimeError(f"Failed to initialize Chrome WebDriver: {e}") from e

    def _update_stage(self, stage_name, percent, message, jobs_found=0, error=False, done=False, result=None):
        """Write session status for live dashboard tracking."""
        stage_idx = self.STAGES.index(stage_name) if stage_name in self.STAGES else 0
        status = {
            "stage": stage_name,
            "stage_index": stage_idx,
            "total_stages": len(self.STAGES),
            "percent": percent,
            "message": message,
            "jobs_found": jobs_found,
            "error": error,
            "done": done,
            "timestamp": datetime.now().isoformat(),
            "result": result,
        }
        _write_session_status(status)

    @staticmethod
    def _find_text(parent, selectors, attr=None, default=""):
        """Try each CSS selector in order and return the first match's text or attribute."""
        for sel in selectors:
            try:
                els = parent.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    if attr:
                        val = els[0].get_attribute(attr)
                        if val:
                            return val.strip()
                    else:
                        val = els[0].text.strip()
                        if val:
                            return val
            except Exception:
                continue
        return default

    def _quit_driver(self):
        """Safely quit the WebDriver, guarding against partial init failures."""
        if hasattr(self, "driver") and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def _scrape_page(self) -> list:
        """
        Parse the currently loaded Naukri results page and return a list of job dicts.
        Returns an empty list on failure (caller handles retries).
        """
        # Try compound card selector
        card_selector = ", ".join(self._CARD_SELECTORS)
        wait = WebDriverWait(self.driver, 15)
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, card_selector)))

        cards = self.driver.find_elements(By.CSS_SELECTOR, card_selector)
        logger.info(f"Found {len(cards)} job cards on page")

        jobs = []
        for card in cards:
            try:
                title_els = card.find_elements(By.CSS_SELECTOR, ", ".join(self._TITLE_SELECTORS))
                if not title_els:
                    continue

                title = title_els[0].text.strip()
                link = title_els[0].get_attribute("href") or ""
                if not title:
                    continue

                company = self._find_text(card, self._COMPANY_SELECTORS, default="Not mentioned")
                loc = self._find_text(card, self._LOCATION_SELECTORS, default="Not mentioned")
                experience = self._find_text(card, self._EXPERIENCE_SELECTORS, default="Not mentioned")
                desc = self._find_text(card, self._DESC_SELECTORS, default="No description")
                posted = self._find_text(card, self._POSTED_SELECTORS, default="N/A")

                tag_els = card.find_elements(By.CSS_SELECTOR, ", ".join(self._TAGS_SELECTORS))
                tags = ", ".join(t.text.strip() for t in tag_els if t.text.strip()) or "N/A"

                jobs.append(
                    {
                        "Title": title,
                        "Company": company,
                        "Location": loc,
                        "Experience": experience,
                        "Description": desc,
                        "Skills": tags,
                        "Posted": posted,
                        "Job URL": link,
                    }
                )
            except Exception as e:
                logger.debug(f"Skipping a card due to parse error: {e}")

        return jobs

    def scrape(
        self,
        role,
        location,
        pages=None,
        output_file=None,
        days=0,
        experience_min=None,
        salary_bucket=None,
        industry_id=None,
        work_mode=None,
        max_jobs=None,
        progress_callback=None,
    ):
        all_jobs = []

        if pages is None and max_jobs:
            pages = math.ceil(max_jobs / 20)
        elif pages is None:
            pages = 1

        self._update_stage("Initializing", 5, f"Ready to scrape '{role}' in '{location or 'India'}'")

        try:
            for page in range(pages):
                page_num = page + 1
                url = build_naukri_url(
                    role,
                    location,
                    page_num=page_num,
                    days=days,
                    experience_min=experience_min,
                    salary_bucket=salary_bucket,
                    industry_id=industry_id,
                    work_mode=work_mode,
                )

                stage_pct = int(5 + ((page + 1) / pages) * 50)
                self._update_stage("Fetching", stage_pct, f"Loading page {page + 1} of {pages}...", len(all_jobs))
                logger.info(f"Scraping Page {page + 1}/{pages}... URL: {url}")

                if progress_callback:
                    progress_callback(page + 1, pages, len(all_jobs), "Fetching", url)

                # Load page with retry
                page_jobs = []
                last_error = None
                for attempt in range(_MAX_PAGE_RETRIES + 1):
                    try:
                        self.driver.get(url)
                        time.sleep(random.uniform(2.0, 4.0))
                        page_jobs = self._scrape_page()
                        last_error = None
                        break  # success
                    except Exception as e:
                        last_error = e
                        if attempt < _MAX_PAGE_RETRIES:
                            wait_secs = random.uniform(_RETRY_WAIT_MIN, _RETRY_WAIT_MAX)
                            logger.warning(
                                f"Page {page + 1} attempt {attempt + 1}/{_MAX_PAGE_RETRIES} failed "
                                f"({e}). Retrying in {wait_secs:.1f}s..."
                            )
                            time.sleep(wait_secs)
                        else:
                            logger.error(f"Page {page + 1} failed after {_MAX_PAGE_RETRIES} retries: {e}")

                if last_error and not page_jobs:
                    self._update_stage(
                        "Fetching",
                        stage_pct,
                        f"Page {page + 1} failed (Timeout/CAPTCHA). Continuing with collected jobs.",
                        len(all_jobs),
                        error=True,
                    )
                    # Don't break — try remaining pages
                    continue

                all_jobs.extend(page_jobs)

                parse_pct = int(55 + ((page + 1) / pages) * 20)
                self._update_stage("Parsing", parse_pct, f"Parsed {len(all_jobs)} jobs so far...", len(all_jobs))
                if progress_callback:
                    progress_callback(page + 1, pages, len(all_jobs), "Parsing", url)

                if max_jobs and len(all_jobs) >= max_jobs:
                    logger.info(f"Reached max_jobs limit ({max_jobs}). Stopping.")
                    break

        finally:
            self._quit_driver()

        if all_jobs:
            df = pd.DataFrame(all_jobs)
            initial_len = len(df)
            df = df.drop_duplicates(subset=["Title", "Company"], keep="first").reset_index(drop=True)

            # Cross-scrape deduplication: Remove jobs already found in previous runs
            data_dir = "data"
            historical_urls = set()
            if os.path.exists(data_dir):
                for f in os.listdir(data_dir):
                    if f.startswith("naukri_") and f.endswith(".csv"):
                        try:
                            hist_df = pd.read_csv(os.path.join(data_dir, f), usecols=["Job URL"])
                            historical_urls.update(hist_df["Job URL"].dropna().tolist())
                        except Exception:
                            pass

            df = df[~df["Job URL"].isin(historical_urls)].reset_index(drop=True)

            if initial_len > len(df):
                logger.info(f"Filtered {initial_len - len(df)} duplicate or previously scraped jobs.")

            if df.empty:
                logger.warning("All scraped jobs were already found in previous runs.")
                self._update_stage("Parsing", 0, "All jobs already scraped previously. No new jobs.", 0, done=True)
                return None, None

            self._update_stage("AI Scoring", 80, f"Scoring {len(df)} jobs with AI...", len(df))
            if progress_callback:
                progress_callback(pages, pages, len(df), "AI Scoring", "")

            try:
                ai_model = JobAIModel()
                df["AI_Score"] = ai_model.predict_scores(df)
                df = df.sort_values(by="AI_Score", ascending=False).reset_index(drop=True)
            except Exception as e:
                logger.error(f"Failed to score jobs with AI: {e}")

            if not output_file:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                output_file = f"data/naukri_{role.replace(' ', '_')}_{location or 'india'}_jobs_{timestamp}.csv"

            if not output_file.endswith(".csv"):
                output_file += ".csv"

            os.makedirs("data", exist_ok=True)

            self._update_stage("Saving", 95, f"Saving {len(df)} jobs to CSV...", len(df))
            if progress_callback:
                progress_callback(pages, pages, len(df), "Saving", output_file)

            df.to_csv(output_file, index=False, encoding="utf-8-sig")
            logger.info(f"Saved {len(df)} job listings to '{output_file}'")

            # ── Top matches queue: append only NEW high-score jobs ────
            if "AI_Score" in df.columns:
                high_score_jobs = df[df["AI_Score"] >= 85].copy()
                if not high_score_jobs.empty:
                    apply_file = os.path.join("data", "top_matches.csv")
                    if os.path.exists(apply_file):
                        try:
                            existing_q = pd.read_csv(apply_file)
                            if "Job URL" in existing_q.columns and "Job URL" in high_score_jobs.columns:
                                high_score_jobs = high_score_jobs[
                                    ~high_score_jobs["Job URL"].isin(existing_q["Job URL"])
                                ]
                        except Exception as e:
                            logger.warning(f"Could not read top_matches for dedup: {e}")
                    if not high_score_jobs.empty:
                        header = not os.path.exists(apply_file)
                        high_score_jobs.to_csv(apply_file, mode="a", header=header, index=False)
                        logger.info(f"Auto-saved {len(high_score_jobs)} new top jobs (Score 85+) to '{apply_file}'")

            top = len(df[df["AI_Score"] >= 85]) if "AI_Score" in df.columns else 0
            good = len(df[df["AI_Score"] >= 50]) if "AI_Score" in df.columns else 0
            result = {
                "total": len(df),
                "top_matches": top,
                "good_matches": good,
                "file": output_file,
                "filename": os.path.basename(output_file),
            }
            self._update_stage("Saving", 100, f"Done! {len(df)} jobs saved.", len(df), done=True, result=result)
            return df, output_file
        else:
            logger.warning("No jobs extracted.")
            self._update_stage("Parsing", 0, "No jobs found.", 0, done=True)
            return None, None


def run_cli():
    parser = argparse.ArgumentParser(description="Multi-Source Job Scraper CLI")
    parser.add_argument(
        "--source",
        type=str,
        default="naukri",
        choices=["naukri", "linkedin", "indeed", "all"],
        help="Job source to scrape",
    )
    parser.add_argument("--role", type=str, required=False, help="Job role to search for")
    parser.add_argument("--location", type=str, required=False, help="Location")
    parser.add_argument("--pages", type=int, default=1, help="Number of pages to scrape")
    parser.add_argument("--days", type=int, default=0, help="Filter by jobs posted in last X days")
    parser.add_argument("--experience", type=int, default=None, help="Minimum experience in years")
    parser.add_argument("--salary", type=str, default=None, help="Salary bucket")
    parser.add_argument("--industry", type=str, default=None, help="Industry name")
    parser.add_argument("--work-mode", type=str, nargs="+", default=None, help="Work modes")
    parser.add_argument("--max-jobs", type=int, default=None, help="Maximum number of jobs")
    parser.add_argument("--output", type=str, help="Output CSV filename (legacy naukri only)")
    parser.add_argument("--visible", action="store_true", help="Run browser in visible mode")

    args = parser.parse_args()

    role = args.role
    if not role:
        print("\n🤖 Welcome to AI Job Scraper!")
        role = input("👉 What job role are you looking for? (e.g. 'software engineer'): ").strip()

    location = args.location
    if not location:
        location = input("👉 Where are you looking? (e.g. 'india', 'bangalore', 'remote'): ").strip()

    if args.source == "naukri":
        logger.info(f"Starting Naukri Scraper for role: '{role}' in '{location}' for {args.pages} pages...")
        scraper = NaukriScraper(headless=not args.visible)
        scraper.scrape(
            role=role,
            location=location,
            pages=args.pages,
            output_file=args.output,
            days=args.days,
            experience_min=args.experience,
            salary_bucket=args.salary,
            industry_id=args.industry,
            work_mode=args.work_mode,
            max_jobs=args.max_jobs,
        )
    else:
        from src.scraper.multi_runner import MultiScraperRunner
        from src.database import init_db

        init_db()
        sources = ["naukri", "linkedin", "indeed"] if args.source == "all" else [args.source]
        runner = MultiScraperRunner(headless=not args.visible)
        logger.info(f"Starting {args.source} scraper(s) for role: '{role}' in '{location}'...")
        results = runner.run_all(
            role=role,
            location=location,
            sources=sources,
            pages=args.pages,
            days=args.days,
            experience_min=args.experience,
            max_jobs=args.max_jobs,
            salary_bucket=args.salary,
            industry_id=args.industry,
            work_mode=args.work_mode,
        )
        print("\n✅ Scraping complete!")
        for src, result in results.items():
            status = "✅" if not result.get("error") else "❌"
            print(f"  {status} {src.title()}: {result.get('jobs_found', 0)} found, {result.get('new_jobs', 0)} new")
            if result.get("error"):
                print(f"     Error: {result['error']}")
