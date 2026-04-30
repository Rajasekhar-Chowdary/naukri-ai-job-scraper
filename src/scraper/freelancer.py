"""
Freelancer.com scraper — native HTTP request implementation.
Parses public job search pages with BeautifulSoup.
"""

import math
import time
import random
from typing import List, Dict, Optional, Callable

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("Freelancer")

FREELANCER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


class FreelancerScraper(BaseScraper):
    SOURCE_NAME = "freelancer"
    USES_BROWSER = False
    IS_GIG = True
    JOBS_PER_PAGE = 50
    BASE_URL = "https://www.freelancer.com"

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
        self.session.headers.update(FREELANCER_HEADERS)

    def _build_url(self, role: str, location: str, page: int, **kwargs) -> str:
        """Not used — we build URLs inline."""
        return ""

    def _parse_cards(self) -> List[Dict]:
        """Not used — parsing is inline."""
        return []

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
        """Scrape Freelancer.com jobs via HTTP."""
        if pages is None and max_jobs:
            pages = math.ceil(max_jobs / self.JOBS_PER_PAGE)
        elif pages is None:
            pages = 1

        target = max_jobs or (pages * self.JOBS_PER_PAGE)
        self._update_stage("Initializing", 5, f"Ready to scrape '{role}' on Freelancer.com")

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

            url = f"{self.BASE_URL}/jobs/?keyword={role.replace(' ', '%20')}"
            if page_num > 1:
                url += f"&page={page_num}"

            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code not in range(200, 400):
                    logger.error(f"Freelancer responded with {resp.status_code}")
                    break
            except Exception as e:
                logger.error(f"Freelancer request failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            list_container = soup.find("div", class_="JobSearchCard-list")
            if not list_container:
                logger.info("No job list container found.")
                break

            items = list_container.find_all("div", class_="JobSearchCard-item", recursive=False)
            if not items:
                logger.info("No more job items found.")
                break

            self._update_stage(
                "Parsing",
                int(55 + (page_num / pages) * 20),
                f"Parsing {len(items)} cards...",
                len(all_jobs),
            )

            for item in items:
                job = self._parse_item(item)
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

    def _parse_item(self, item) -> Optional[Dict]:
        """Parse a single Freelancer.com job item."""
        try:
            title_link = item.find("a", class_="JobSearchCard-primary-heading-link")
            if not title_link:
                return None
            title = title_link.get_text(strip=True)
            href = title_link.get("href", "")
            job_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            desc = item.find("p", class_="JobSearchCard-primary-description")
            description = desc.get_text(strip=True)[:500] if desc else "No description"

            budget = item.find("div", class_="JobSearchCard-secondary-price")
            budget_text = budget.get_text(strip=True) if budget else "N/A"

            bids = item.find("div", class_="JobSearchCard-secondary-entry")
            bids_text = bids.get_text(strip=True) if bids else "N/A"
            proposals = self._extract_number(bids_text)

            tags = item.find_all("a", class_="JobSearchCard-primary-tagsLink")
            skills = ", ".join(t.get_text(strip=True) for t in tags) or "N/A"

            time_left = item.find("span", class_="JobSearchCard-primary-heading-days")
            time_left_text = time_left.get_text(strip=True) if time_left else "N/A"

            verified = bool(item.find("div", class_="JobSearchCard-primary-heading-status"))

            budget_type, budget_min, budget_max, currency = self._parse_budget(budget_text)

            return self._standardize_job(
                {
                    "Title": title,
                    "Company": "Freelancer Client",
                    "Location": "Remote / Worldwide",
                    "Experience": "Not mentioned",
                    "Description": description,
                    "Skills": skills,
                    "Posted": "N/A",
                    "Job URL": job_url,
                }
            ) | {
                "Budget Type": budget_type,
                "Budget Min": budget_min,
                "Budget Max": budget_max,
                "Currency": currency,
                "Proposals": proposals,
                "Time Left": time_left_text,
                "Verified": verified,
            }
        except Exception as e:
            logger.debug(f"Skipping Freelancer item: {e}")
            return None

    @staticmethod
    def _extract_number(text: str) -> Optional[int]:
        """Extract first number from text like '142 bids'."""
        import re

        match = re.search(r"\d+", text)
        return int(match.group()) if match else None

    @staticmethod
    def _parse_budget(text: str):
        """Parse budget text like '$414 Avg Bid' or '$250 - $750 USD'."""
        import re

        currency = "USD"
        if "₹" in text or "INR" in text:
            currency = "INR"
        elif "€" in text or "EUR" in text:
            currency = "EUR"
        elif "£" in text or "GBP" in text:
            currency = "GBP"

        numbers = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", text)]
        if len(numbers) >= 2:
            return "range", numbers[0], numbers[1], currency
        elif len(numbers) == 1:
            if "avg" in text.lower() or "bid" in text.lower():
                return "avg_bid", numbers[0], numbers[0], currency
            return "fixed", numbers[0], numbers[0], currency
        return "unknown", None, None, currency
