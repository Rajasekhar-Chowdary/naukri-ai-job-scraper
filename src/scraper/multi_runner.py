"""
Multi-source scraper runner.
Runs jobs and gigs scrapers sequentially (or in threads)
with a single call and aggregates results.
"""

import threading
from typing import List, Dict, Optional, Callable

from src.scraper.naukri import NaukriScraper
from src.scraper.linkedin import LinkedInScraper
from src.scraper.indeed import IndeedScraper
from src.scraper.freelancer import FreelancerScraper
from src.scraper.guru import GuruScraper
from src.scraper.base import clear_session_status
from src.utils.logger import setup_logger

logger = setup_logger("MultiRunner")

SCRAPER_REGISTRY = {
    "naukri": NaukriScraper,
    "linkedin": LinkedInScraper,
    "indeed": IndeedScraper,
    "freelancer": FreelancerScraper,
    "guru": GuruScraper,
}

DEFAULT_JOB_SOURCES = ["naukri", "linkedin", "indeed"]
DEFAULT_GIG_SOURCES = ["freelancer", "guru"]


class MultiScraperRunner:
    """
    Run multiple scrapers with one call.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless

    def run_all(
        self,
        role: str,
        location: str = "",
        sources: Optional[List[str]] = None,
        pages: Optional[int] = None,
        days: int = 0,
        experience_min: Optional[int] = None,
        max_jobs: Optional[int] = None,
        progress_callback: Optional[Callable] = None,
        per_source_callback: Optional[Callable] = None,
        parallel: bool = False,
        **kwargs,
    ) -> Dict[str, Dict]:
        """
        Run selected scrapers and return aggregated results.
        """
        if sources is None:
            sources = DEFAULT_JOB_SOURCES.copy()

        clear_session_status()
        results: Dict[str, Dict] = {}

        if parallel:
            threads = []
            lock = threading.Lock()

            def _run_one(source: str):
                result = self._run_single(
                    source=source,
                    role=role,
                    location=location,
                    pages=pages,
                    days=days,
                    experience_min=experience_min,
                    max_jobs=max_jobs,
                    progress_callback=progress_callback,
                    **kwargs,
                )
                with lock:
                    results[source] = result
                if per_source_callback:
                    per_source_callback(source, result)

            for source in sources:
                t = threading.Thread(target=_run_one, args=(source,), daemon=True)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()
        else:
            for source in sources:
                logger.info(f"[MultiRunner] Starting {source}...")
                result = self._run_single(
                    source=source,
                    role=role,
                    location=location,
                    pages=pages,
                    days=days,
                    experience_min=experience_min,
                    max_jobs=max_jobs,
                    progress_callback=progress_callback,
                    **kwargs,
                )
                results[source] = result
                if per_source_callback:
                    per_source_callback(source, result)
                logger.info(
                    f"[MultiRunner] {source} complete: {result.get('jobs_found', 0)} found, "
                    f"{result.get('new_jobs', 0)} new"
                )

        return results

    def _run_single(
        self,
        source: str,
        role: str,
        location: str,
        pages: Optional[int],
        days: int,
        experience_min: Optional[int],
        max_jobs: Optional[int],
        progress_callback: Optional[Callable],
        **kwargs,
    ) -> Dict:
        scraper_cls = SCRAPER_REGISTRY.get(source)
        if not scraper_cls:
            return {"error": f"Unknown source: {source}"}

        wrapped_callback = None
        if progress_callback:

            def wrapped(page, total, found, stage, detail):
                progress_callback(source, page, total, found, stage, detail)

            wrapped_callback = wrapped

        try:
            scraper = scraper_cls(headless=self.headless)
            run_kwargs = {
                "role": role,
                "location": location,
                "pages": pages,
                "days": days,
                "experience_min": experience_min,
                "max_jobs": max_jobs,
                "progress_callback": wrapped_callback,
            }
            if source == "naukri":
                run_kwargs.update(
                    {k: v for k, v in kwargs.items() if k in ("salary_bucket", "industry_id", "work_mode")}
                )
            result = scraper.run(**run_kwargs)
            return result
        except Exception as e:
            logger.error(f"[MultiRunner] {source} failed: {e}")
            return {"jobs_found": 0, "new_jobs": 0, "duplicates": 0, "error": str(e)}
