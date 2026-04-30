"""
LinkedIn Jobs scraper — native HTTP request implementation.
Inspired by JobSpy (github.com/speedyapply/JobSpy).

Uses LinkedIn's public guest API endpoint instead of Selenium,
making it ~3x faster and much lighter on resources.
"""

import math
import random
import time
from datetime import datetime
from typing import List, Dict, Optional, Callable
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("LinkedIn")

LINKEDIN_HEADERS = {
    "authority": "www.linkedin.com",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


class LinkedInScraper(BaseScraper):
    SOURCE_NAME = "linkedin"
    USES_BROWSER = False
    JOBS_PER_PAGE = 25
    BASE_URL = "https://www.linkedin.com"

    def __init__(self, headless=True):
        # Skip BaseScraper __init__ driver setup since USES_BROWSER=False
        self.headless = headless
        self.logger = setup_logger(self.SOURCE_NAME)
        self.driver = None
        self._init_session()

    def _init_session(self):
        """Initialize requests session with retry logic."""
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
        self.session.headers.update(LINKEDIN_HEADERS)

    def _build_url(
        self,
        role: str,
        location: str,
        page: int,
        days: int = 0,
        experience_min: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Not used — we call the API directly in scrape()."""
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
        """
        Scrape LinkedIn jobs via public guest API.
        """
        if pages is None and max_jobs:
            pages = math.ceil(max_jobs / self.JOBS_PER_PAGE)
        elif pages is None:
            pages = 1

        target = max_jobs or (pages * self.JOBS_PER_PAGE)
        self._update_stage("Initializing", 5, f"Ready to scrape '{role}' in '{location or 'Any'}'")

        all_jobs: List[Dict] = []
        seen_ids = set()
        start = 0
        request_count = 0
        seconds_old = (days * 24 * 3600) if days > 0 else None

        while len(all_jobs) < target and start < 1000:
            request_count += 1
            self._update_stage(
                "Fetching",
                int(5 + (len(all_jobs) / target) * 50),
                f"Loading page {request_count}...",
                len(all_jobs),
            )
            if progress_callback:
                progress_callback(request_count, pages, len(all_jobs), "Fetching", f"start={start}")

            params = {
                "keywords": role,
                "location": location or "India",
                "pageNum": 0,
                "start": start,
            }
            if seconds_old is not None:
                params["f_TPR"] = f"r{seconds_old}"
            params = {k: v for k, v in params.items() if v is not None}

            try:
                resp = self.session.get(
                    f"{self.BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search?",
                    params=params,
                    timeout=15,
                )
                if resp.status_code not in range(200, 400):
                    logger.error(f"LinkedIn responded with {resp.status_code}")
                    break
            except Exception as e:
                logger.error(f"LinkedIn request failed: {e}")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.find_all("div", class_="base-search-card")
            if not cards:
                logger.info("No more job cards found.")
                break

            self._update_stage(
                "Parsing",
                int(55 + (len(all_jobs) / target) * 20),
                f"Parsing {len(cards)} cards...",
                len(all_jobs),
            )

            for card in cards:
                job = self._parse_card(card)
                if not job:
                    continue
                job_id = job.get("Job URL", "").split("-")[-1]
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                all_jobs.append(job)
                if max_jobs and len(all_jobs) >= max_jobs:
                    break

            if progress_callback:
                progress_callback(request_count, pages, len(all_jobs), "Parsing", f"start={start}")

            if len(all_jobs) < target:
                time.sleep(random.uniform(2.0, 4.0))
                start += len(cards)

        self._update_stage("Saving", 95, f"Done! Parsed {len(all_jobs)} jobs.", len(all_jobs))
        return all_jobs

    def _parse_card(self, card) -> Optional[Dict]:
        """Parse a single LinkedIn job card (BeautifulSoup Tag)."""
        try:
            href_tag = card.find("a", class_="base-card__full-link")
            if not href_tag or "href" not in href_tag.attrs:
                return None
            href = href_tag.attrs["href"].split("?")[0]
            job_id = href.split("-")[-1]

            title_tag = card.find("span", class_="sr-only")
            title = title_tag.get_text(strip=True) if title_tag else "N/A"

            company_tag = card.find("h4", class_="base-search-card__subtitle")
            company_a = company_tag.find("a") if company_tag else None
            company = company_a.get_text(strip=True) if company_a else "Not mentioned"

            metadata = card.find("div", class_="base-search-card__metadata")
            loc_tag = metadata.find("span", class_="job-search-card__location") if metadata else None
            location = loc_tag.get_text(strip=True) if loc_tag else "Not mentioned"

            posted = "N/A"
            time_tag = metadata.find("time", class_="job-search-card__listdate") if metadata else None
            if not time_tag and metadata:
                time_tag = metadata.find("time", class_="job-search-card__listdate--new")
            if time_tag and "datetime" in time_tag.attrs:
                posted = time_tag["datetime"]

            return self._standardize_job(
                {
                    "Title": title,
                    "Company": company,
                    "Location": location,
                    "Experience": "Not mentioned",
                    "Description": "Click to view description",
                    "Skills": "N/A",
                    "Posted": posted,
                    "Job URL": f"{self.BASE_URL}/jobs/view/{job_id}",
                }
            )
        except Exception as e:
            logger.debug(f"Skipping LinkedIn card: {e}")
            return None
