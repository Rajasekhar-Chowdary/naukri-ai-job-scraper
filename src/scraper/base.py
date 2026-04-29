"""
Abstract base class for all job scrapers.
Enforces a unified interface so the scheduler and dashboard can treat
Naukri, LinkedIn, Indeed, etc. identically.
"""
import abc
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Callable
from src.database import insert_jobs, start_scrape, finish_scrape
from src.utils.logger import setup_logger

logger = setup_logger("BaseScraper")


class BaseScraper(abc.ABC):
    """All scrapers must inherit from this and implement scrape()."""

    SOURCE_NAME: str = "unknown"
    MAX_RETRIES: int = 2
    RETRY_WAIT_MIN: float = 4.0
    RETRY_WAIT_MAX: float = 8.0

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.logger = setup_logger(self.SOURCE_NAME)

    @abc.abstractmethod
    def scrape(
        self,
        role: str,
        location: str = "",
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> List[Dict]:
        """
        Scrape jobs and return a list of standardized job dicts.
        Each dict must contain at least: Title, Company, Location,
        Experience, Description, Skills, Posted, Job URL.
        """
        ...

    def run(
        self,
        role: str,
        location: str = "",
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        Wrapper that handles: scrape → persist to DB → return metadata.
        Returns {"jobs_found": int, "new_jobs": int, "error": str|None}.
        """
        scrape_id = start_scrape(self.SOURCE_NAME, role, location)
        jobs = []
        error_msg = None

        try:
            self.logger.info(
                f"[{self.SOURCE_NAME}] Starting scrape: '{role}' in '{location or 'Any'}'"
            )
            jobs = self.scrape(
                role=role,
                location=location,
                pages=pages,
                days=days,
                experience_min=experience_min,
                max_jobs=max_jobs,
                progress_callback=progress_callback,
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"[{self.SOURCE_NAME}] Scrape failed: {e}")

        new_jobs, duplicates = 0, 0
        if jobs:
            new_jobs, duplicates = insert_jobs(jobs, source=self.SOURCE_NAME)

        finish_scrape(scrape_id, len(jobs), new_jobs, error_msg)

        self.logger.info(
            f"[{self.SOURCE_NAME}] Done. Found {len(jobs)}, new {new_jobs}, dupes {duplicates}."
        )
        return {
            "jobs_found": len(jobs),
            "new_jobs": new_jobs,
            "duplicates": duplicates,
            "error": error_msg,
        }

    @staticmethod
    def _jitter(min_sec: float = 2.0, max_sec: float = 5.0):
        """Sleep for a random interval to mimic human behavior."""
        time.sleep(random.uniform(min_sec, max_sec))

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
