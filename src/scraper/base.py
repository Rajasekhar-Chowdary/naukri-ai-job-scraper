"""
Abstract base class for all job scrapers.
Enforces a unified interface so the scheduler, dashboard, and CLI can treat
Naukri, LinkedIn, Indeed, etc. identically.

Features shared by all scrapers:
  - Stealth Chrome WebDriver init/quit
  - Live session status tracking (data/.scrape_session.json)
  - Per-page retry logic with jitter
  - Progress callbacks
  - Fallback CSS selector helper (_find_text)
  - Standardized output formatting
"""

import abc
import os
import json
import time
import random
import math
from datetime import datetime
from typing import List, Dict, Optional, Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from src.database import insert_jobs, insert_gigs, start_scrape, finish_scrape
from src.utils.logger import setup_logger

logger = setup_logger("BaseScraper")

SESSION_STATUS_PATH = os.path.join("data", ".scrape_session.json")


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


class BaseScraper(abc.ABC):
    """All scrapers must inherit from this and implement _build_url() + _parse_cards()."""

    SOURCE_NAME: str = "unknown"
    STAGES: List[str] = ["Initializing", "Fetching", "Parsing", "Saving"]
    MAX_RETRIES: int = 2
    RETRY_WAIT_MIN: float = 4.0
    RETRY_WAIT_MAX: float = 8.0
    JOBS_PER_PAGE: int = 20
    USES_BROWSER: bool = True  # Set to False for API/request-based scrapers
    IS_GIG: bool = False  # Set to True for freelance gig scrapers

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.logger = setup_logger(self.SOURCE_NAME)
        self.driver: Optional[webdriver.Chrome] = None
        if self.USES_BROWSER:
            self._init_driver()

    # ── WebDriver lifecycle ───────────────────────────────────────────

    def _init_driver(self):
        """Initialize stealth Chrome WebDriver."""
        self.logger.info("Initializing Chrome WebDriver...")
        self._update_stage("Initializing", 0, "Starting Chrome WebDriver...")
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--log-level=3")
        # Stealth options
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("WebDriver initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver: {e}")
            self._update_stage("Initializing", 0, f"Error: {e}", error=True)
            raise RuntimeError(f"Failed to initialize Chrome WebDriver: {e}") from e

    def _quit_driver(self):
        """Safely quit the WebDriver."""
        if getattr(self, "driver", None):
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None

    # ── Session tracking ──────────────────────────────────────────────

    def _update_stage(
        self,
        stage_name: str,
        percent: int,
        message: str,
        jobs_found: int = 0,
        error: bool = False,
        done: bool = False,
        result: Optional[Dict] = None,
    ):
        """Write live JSON status for the dashboard to poll."""
        stage_idx = self.STAGES.index(stage_name) if stage_name in self.STAGES else 0
        status = {
            "source": self.SOURCE_NAME,
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

    # ── Shared helpers ────────────────────────────────────────────────

    @staticmethod
    def _jitter(min_sec: float = 2.0, max_sec: float = 5.0):
        """Sleep for a random interval to mimic human behavior."""
        time.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    def _find_text(parent, selectors, attr=None, default=""):
        """Try each CSS selector in order, return first non-empty text or attribute."""
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

    @staticmethod
    def _standardize_job(raw: Dict) -> Dict:
        """Ensure every scraper outputs the same field names."""
        return {
            "Title": raw.get("Title", "").strip(),
            "Company": raw.get("Company", "").strip() or "Not mentioned",
            "Location": raw.get("Location", "").strip() or "Not mentioned",
            "Experience": raw.get("Experience", "").strip() or "Not mentioned",
            "Description": raw.get("Description", "").strip() or "No description",
            "Skills": raw.get("Skills", "").strip() or "N/A",
            "Posted": raw.get("Posted", "").strip() or "N/A",
            "Job URL": raw.get("Job URL", "").strip(),
        }

    # ── Abstract methods (subclass must implement) ────────────────────

    def _build_url(
        self,
        role: str,
        location: str,
        page: int,
        days: int = 0,
        experience_min: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Build the search URL for a given page."""
        raise NotImplementedError

    def _parse_cards(self) -> List[Dict]:
        """Extract job dicts from the current page. Must call self.driver.get() first."""
        raise NotImplementedError

    # ── Core scrape logic (can be overridden, but usually not needed) ─

    def scrape(
        self,
        role: str,
        location: str = "",
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs,
    ) -> List[Dict]:
        """
        Scrape jobs with per-page retry, session tracking, and progress callbacks.
        Subclasses normally only need to implement _build_url() and _parse_cards().
        """
        if pages is None and max_jobs:
            pages = math.ceil(max_jobs / self.JOBS_PER_PAGE)
        elif pages is None:
            pages = 1

        self._update_stage(
            "Initializing",
            5,
            f"Ready to scrape '{role}' in '{location or 'Any'}'",
        )

        all_jobs: List[Dict] = []

        try:
            for page in range(1, pages + 1):
                url = self._build_url(
                    role=role,
                    location=location,
                    page=page,
                    days=days,
                    experience_min=experience_min,
                    **kwargs,
                )
                fetch_pct = int(5 + (page / pages) * 50)
                self._update_stage("Fetching", fetch_pct, f"Loading page {page} of {pages}...", len(all_jobs))
                self.logger.info(f"[{self.SOURCE_NAME}] Page {page}/{pages}: {url}")
                if progress_callback:
                    progress_callback(page, pages, len(all_jobs), "Fetching", url)

                page_jobs: List[Dict] = []
                last_error = None
                for attempt in range(self.MAX_RETRIES + 1):
                    try:
                        self.driver.get(url)
                        self._jitter(2.0, 4.0)
                        page_jobs = self._parse_cards()
                        last_error = None
                        break
                    except Exception as e:
                        last_error = e
                        if attempt < self.MAX_RETRIES:
                            wait = random.uniform(self.RETRY_WAIT_MIN, self.RETRY_WAIT_MAX)
                            self.logger.warning(
                                f"[{self.SOURCE_NAME}] Page {page} attempt {attempt + 1} failed, retrying in {wait:.1f}s..."
                            )
                            time.sleep(wait)
                        else:
                            self.logger.error(
                                f"[{self.SOURCE_NAME}] Page {page} failed after {self.MAX_RETRIES} retries: {e}"
                            )

                if last_error and not page_jobs:
                    self._update_stage(
                        "Fetching",
                        fetch_pct,
                        f"Page {page} failed. Continuing with collected jobs.",
                        len(all_jobs),
                        error=True,
                    )
                    continue

                all_jobs.extend(page_jobs)
                parse_pct = int(55 + (page / pages) * 20)
                self._update_stage("Parsing", parse_pct, f"Parsed {len(all_jobs)} jobs so far...", len(all_jobs))
                if progress_callback:
                    progress_callback(page, pages, len(all_jobs), "Parsing", url)

                if max_jobs and len(all_jobs) >= max_jobs:
                    self.logger.info(f"Reached max_jobs limit ({max_jobs}). Stopping.")
                    break
        finally:
            self._quit_driver()

        return all_jobs

    # ── High-level wrapper (DB persistence) ───────────────────────────

    def run(
        self,
        role: str,
        location: str = "",
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs,
    ) -> Dict:
        """
        Wrapper that handles: scrape → persist to DB → return metadata.
        Returns {"jobs_found": int, "new_jobs": int, "duplicates": int, "error": str|None}.
        """
        scrape_id = start_scrape(self.SOURCE_NAME, role, location)
        jobs = []
        error_msg = None

        try:
            self.logger.info(f"[{self.SOURCE_NAME}] Starting scrape: '{role}' in '{location or 'Any'}'")
            jobs = self.scrape(
                role=role,
                location=location,
                pages=pages,
                days=days,
                experience_min=experience_min,
                max_jobs=max_jobs,
                progress_callback=progress_callback,
                **kwargs,
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"[{self.SOURCE_NAME}] Scrape failed: {e}")

        new_jobs, duplicates = 0, 0
        if jobs:
            if getattr(self, "IS_GIG", False):
                new_jobs, duplicates = insert_gigs(jobs, source=self.SOURCE_NAME)
            else:
                new_jobs, duplicates = insert_jobs(jobs, source=self.SOURCE_NAME)

        finish_scrape(scrape_id, len(jobs), new_jobs, error_msg)

        self.logger.info(f"[{self.SOURCE_NAME}] Done. Found {len(jobs)}, new {new_jobs}, dupes {duplicates}.")
        return {
            "jobs_found": len(jobs),
            "new_jobs": new_jobs,
            "duplicates": duplicates,
            "error": error_msg,
        }
