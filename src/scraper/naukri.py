"""
Naukri.com scraper — refactored to inherit from BaseScraper
and output directly to the unified SQLite database.
"""
import math
import time
import random
import os
import json
from datetime import datetime
from urllib.parse import urlencode
from typing import List, Dict, Optional, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("Naukri")

SESSION_STATUS_PATH = os.path.join("data", ".scrape_session.json")

# ── Filter mappings ─────────────────────────────────────────────
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
WORK_MODES = {"On-site": "0", "Hybrid": "1", "Remote": "2"}
TIME_PERIODS = {
    "Any time": 0,
    "Last 24 hours": 1,
    "Last 3 days": 3,
    "Last 7 days": 7,
    "Last 15 days": 15,
    "Last 30 days": 30,
}


def build_naukri_url(
    role, location, page_num=1, days=0, experience_min=None,
    salary_bucket=None, industry_id=None, work_mode=None
):
    formatted_role = role.replace(" ", "-").lower()
    loc = location.lower().strip() if location else ""
    loc_path = f"-in-{loc}" if loc else ""
    page_path = f"-{page_num}" if page_num > 1 else ""
    url = f"https://www.naukri.com/{formatted_role}-jobs{loc_path}{page_path}"

    params = {"k": role}
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


def _write_session_status(status: dict):
    try:
        os.makedirs("data", exist_ok=True)
        with open(SESSION_STATUS_PATH, "w") as f:
            json.dump(status, f)
    except Exception:
        pass


def clear_session_status():
    if os.path.exists(SESSION_STATUS_PATH):
        try:
            os.remove(SESSION_STATUS_PATH)
        except Exception:
            pass


class NaukriScraper(BaseScraper):
    SOURCE_NAME = "naukri"
    STAGES = ["Initializing", "Fetching", "Parsing", "AI Scoring", "Saving"]

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
        super().__init__(headless=headless)
        self.driver = None
        self._init_driver()

    def _init_driver(self):
        logger.info("Initializing Chrome WebDriver...")
        self._update_stage("Initializing", 0, "Starting Chrome WebDriver...")
        chrome_options = Options()
        if self.headless:
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
            raise RuntimeError(f"Failed to initialize Chrome WebDriver: {e}") from e

    def _update_stage(self, stage_name, percent, message, jobs_found=0, error=False, done=False, result=None):
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
        if hasattr(self, "driver") and self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def _scrape_page(self) -> List[Dict]:
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

                job = self._standardize_job({
                    "Title": title,
                    "Company": self._find_text(card, self._COMPANY_SELECTORS, default="Not mentioned"),
                    "Location": self._find_text(card, self._LOCATION_SELECTORS, default="Not mentioned"),
                    "Experience": self._find_text(card, self._EXPERIENCE_SELECTORS, default="Not mentioned"),
                    "Description": self._find_text(card, self._DESC_SELECTORS, default="No description"),
                    "Posted": self._find_text(card, self._POSTED_SELECTORS, default="N/A"),
                    "Skills": ", ".join(
                        t.text.strip() for t in card.find_elements(By.CSS_SELECTOR, ", ".join(self._TAGS_SELECTORS)) if t.text.strip()
                    ) or "N/A",
                    "Job URL": link,
                })
                jobs.append(job)
            except Exception as e:
                logger.debug(f"Skipping card due to parse error: {e}")
        return jobs

    def scrape(
        self,
        role: str,
        location: str = "",
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        salary_bucket: Optional[str] = None,
        industry_id: Optional[str] = None,
        work_mode: Optional[List[str]] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
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
                    role, location, page_num=page_num, days=days,
                    experience_min=experience_min, salary_bucket=salary_bucket,
                    industry_id=industry_id, work_mode=work_mode
                )
                stage_pct = int(5 + ((page + 1) / pages) * 50)
                self._update_stage("Fetching", stage_pct, f"Loading page {page_num} of {pages}...", len(all_jobs))
                logger.info(f"Scraping Page {page_num}/{pages}... URL: {url}")
                if progress_callback:
                    progress_callback(page_num, pages, len(all_jobs), "Fetching", url)

                page_jobs = []
                last_error = None
                for attempt in range(self.MAX_RETRIES + 1):
                    try:
                        self.driver.get(url)
                        self._jitter(2.0, 4.0)
                        page_jobs = self._scrape_page()
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e
                        if attempt < self.MAX_RETRIES:
                            self._jitter(self.RETRY_WAIT_MIN, self.RETRY_WAIT_MAX)
                        else:
                            logger.error(f"Page {page_num} failed after {self.MAX_RETRIES} retries: {e}")

                if last_error and not page_jobs:
                    self._update_stage(
                        "Fetching", stage_pct,
                        f"Page {page_num} failed. Continuing with collected jobs.",
                        len(all_jobs), error=True
                    )
                    continue

                all_jobs.extend(page_jobs)
                parse_pct = int(55 + ((page + 1) / pages) * 20)
                self._update_stage("Parsing", parse_pct, f"Parsed {len(all_jobs)} jobs so far...", len(all_jobs))
                if progress_callback:
                    progress_callback(page_num, pages, len(all_jobs), "Parsing", url)

                if max_jobs and len(all_jobs) >= max_jobs:
                    logger.info(f"Reached max_jobs limit ({max_jobs}). Stopping.")
                    break
        finally:
            self._quit_driver()

        return all_jobs
