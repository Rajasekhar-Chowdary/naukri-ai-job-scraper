"""
Guru.com scraper — native HTTP request implementation.
Parses public job search pages with BeautifulSoup.
"""

import math
import time
import random
import re
from typing import List, Dict, Optional, Callable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("Guru")

GURU_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


class GuruScraper(BaseScraper):
    SOURCE_NAME = "guru"
    USES_BROWSER = False
    IS_GIG = True
    JOBS_PER_PAGE = 20
    BASE_URL = "https://www.guru.com"

    def __init__(self, headless=True):
        self.headless = headless
        self.logger = setup_logger(self.SOURCE_NAME)
        self.driver = None
        self._init_session()

    def _init_session(self):
        self.session = requests.Session()
        retries = Retry(
            total=3,
            connect=3,
            status=3,
            status_forcelist=[500, 502, 503, 504, 429],
            backoff_factor=2,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(GURU_HEADERS)

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
        """Scrape Guru.com jobs via HTTP."""
        if pages is None and max_jobs:
            pages = math.ceil(max_jobs / self.JOBS_PER_PAGE)
        elif pages is None:
            pages = 1

        target = max_jobs or (pages * self.JOBS_PER_PAGE)
        self._update_stage("Initializing", 5, f"Ready to scrape '{role}' on Guru.com")

        all_jobs: List[Dict] = []

        for page_num in range(1, pages + 1):
            self._update_stage(
                "Fetching",
                int(5 + (page_num / pages) * 50),
                f"Loading page {page_num} of {pages}...",
                len(all_jobs),
            )
            if progress_callback:
                progress_callback(page_num, pages, len(all_jobs), "Fetching", f"page={page_num}")

            url = f"{self.BASE_URL}/d/jobs/?q={role.replace(' ', '+')}"
            if page_num > 1:
                url += f"&page={page_num}"

            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code not in range(200, 400):
                    logger.error(f"Guru responded with {resp.status_code}")
                    break
            except Exception as e:
                logger.error(f"Guru request failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.find_all("div", class_="jobRecord")
            if not items:
                logger.info("No more job records found.")
                break

            self._update_stage(
                "Parsing",
                int(55 + (page_num / pages) * 20),
                f"Parsing {len(items)} records...",
                len(all_jobs),
            )

            for item in items:
                job = self._parse_record(item)
                if job:
                    all_jobs.append(job)
                if max_jobs and len(all_jobs) >= max_jobs:
                    break

            if progress_callback:
                progress_callback(page_num, pages, len(all_jobs), "Parsing", f"page={page_num}")

            if max_jobs and len(all_jobs) >= max_jobs:
                break
            if page_num < pages:
                time.sleep(random.uniform(2.0, 4.0))

        self._update_stage("Saving", 95, f"Done! Parsed {len(all_jobs)} gigs.", len(all_jobs))
        return all_jobs

    def _parse_record(self, record) -> Optional[Dict]:
        """Parse a single Guru.com job record."""
        try:
            title_tag = record.find("h2", class_="jobRecord__title")
            if not title_tag:
                return None
            a_tag = title_tag.find("a")
            title = a_tag.get_text(strip=True) if a_tag else "N/A"
            href = a_tag.get("href", "") if a_tag else ""
            job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            if not job_url:
                return None

            desc = record.find("div", class_="jobRecord__description")
            description = ""
            if desc:
                p = desc.find("p")
                description = p.get_text(strip=True)[:500] if p else desc.get_text(strip=True)[:500]

            budget_tag = record.find("div", class_="jobRecord__budget")
            budget_text = budget_tag.get_text(strip=True) if budget_tag else "N/A"

            meta = record.find("div", class_="jobRecord__meta")
            posted = "N/A"
            proposals = None
            if meta:
                meta_text = meta.get_text(separator=" ", strip=True)
                # Extract posted time and quotes
                posted_match = re.search(r"Posted\s+(.+?)\s*·", meta_text)
                if posted_match:
                    posted = posted_match.group(1).strip()
                quotes_match = re.search(r"(\d+)\s+Quotes", meta_text)
                if quotes_match:
                    proposals = int(quotes_match.group(1))

            tags = record.find_all("a", class_="record__skill")
            skills = ", ".join(t.get_text(strip=True) for t in tags) or "N/A"

            budget_type, budget_min, budget_max, currency = self._parse_budget(budget_text)

            return self._standardize_job(
                {
                    "Title": title,
                    "Company": "Guru Client",
                    "Location": "Remote / Worldwide",
                    "Experience": "Not mentioned",
                    "Description": description,
                    "Skills": skills,
                    "Posted": posted,
                    "Job URL": job_url,
                }
            ) | {
                "Budget Type": budget_type,
                "Budget Min": budget_min,
                "Budget Max": budget_max,
                "Currency": currency,
                "Proposals": proposals,
                "Time Left": "N/A",
                "Verified": False,
            }
        except Exception as e:
            logger.debug(f"Skipping Guru record: {e}")
            return None

    @staticmethod
    def _parse_budget(text: str):
        """Parse budget text like 'Fixed Price $250-750' or 'Hourly $15-25'."""
        numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", text)]
        currency = "USD"
        if "₹" in text or "INR" in text:
            currency = "INR"

        text_lower = text.lower()
        if "hourly" in text_lower:
            if len(numbers) >= 2:
                return "hourly", numbers[0], numbers[1], currency
            elif len(numbers) == 1:
                return "hourly", numbers[0], numbers[0], currency
        elif "fixed" in text_lower:
            if len(numbers) >= 2:
                return "fixed", numbers[0], numbers[1], currency
            elif len(numbers) == 1:
                return "fixed", numbers[0], numbers[0], currency

        if len(numbers) >= 2:
            return "range", numbers[0], numbers[1], currency
        elif len(numbers) == 1:
            return "fixed", numbers[0], numbers[0], currency
        return "unknown", None, None, currency
