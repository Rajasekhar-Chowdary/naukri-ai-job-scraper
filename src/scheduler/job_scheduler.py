"""
Background job scheduler for 24/7 continuous scraping.
Uses APScheduler to run multiple scrapers on configurable intervals
and sends notifications when new high-score jobs are found.
"""

import os
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.database import init_db, get_stats, get_jobs
from src.scraper.naukri import NaukriScraper
from src.scraper.linkedin import LinkedInScraper
from src.scraper.indeed import IndeedScraper
from src.ai.ai_opportunity_finder import JobAIModel
from src.notifications.notifier import Notifier
from src.utils.logger import setup_logger

logger = setup_logger("Scheduler")

SCRAPER_REGISTRY = {
    "naukri": NaukriScraper,
    "linkedin": LinkedInScraper,
    "indeed": IndeedScraper,
}

DEFAULT_CONFIG = {
    "naukri": {"enabled": True, "interval_hours": 6, "pages": 3, "max_jobs": 60},
    "linkedin": {"enabled": False, "interval_hours": 12, "pages": 2, "max_jobs": 50},
    "indeed": {"enabled": False, "interval_hours": 12, "pages": 2, "max_jobs": 50},
}


class JobScheduler:
    """Central scheduler that manages all scrapers and notifications."""

    def __init__(self, config: Optional[Dict] = None, notify: bool = True):
        init_db()
        self.config = config or DEFAULT_CONFIG
        self.scheduler = BackgroundScheduler()
        self.ai_model = JobAIModel()
        self.notifier = Notifier() if notify else None
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        """Start the background scheduler."""
        if self._running:
            logger.warning("Scheduler is already running.")
            return

        for source, cfg in self.config.items():
            if not cfg.get("enabled", False):
                continue
            interval = cfg.get("interval_hours", 6)
            self.scheduler.add_job(
                func=self._run_scraper,
                trigger=IntervalTrigger(hours=interval),
                id=f"scrape_{source}",
                name=f"Scrape {source}",
                replace_existing=True,
                kwargs={"source": source, "cfg": cfg},
            )
            logger.info(f"Scheduled {source} every {interval}h")

        self.scheduler.start()
        self._running = True
        logger.info("JobScheduler started.")

    def stop(self):
        """Gracefully stop the scheduler."""
        if not self._running:
            return
        self.scheduler.shutdown(wait=False)
        self._running = False
        logger.info("JobScheduler stopped.")

    def run_now(self, source: str, role: str = "Data Analyst", location: str = "India") -> Dict:
        """Manually trigger a scraper run. Returns metadata."""
        cfg = self.config.get(source, {})
        return self._run_scraper(source, cfg, role=role, location=location)

    def _run_scraper(self, source: str, cfg: Dict, role: str = "Data Analyst", location: str = "India"):
        with self._lock:
            logger.info(f"[{source}] Scheduled scrape starting...")
            scraper_cls = SCRAPER_REGISTRY.get(source)
            if not scraper_cls:
                logger.error(f"Unknown source: {source}")
                return {"error": f"Unknown source: {source}"}

            try:
                scraper = scraper_cls(headless=True)
                result = scraper.run(
                    role=role,
                    location=location,
                    pages=cfg.get("pages", 1),
                    max_jobs=cfg.get("max_jobs", 50),
                )
            except Exception as e:
                logger.error(f"[{source}] Scraper crashed: {e}")
                return {"error": str(e)}

            new_jobs = result.get("new_jobs", 0)
            if new_jobs > 0:
                self._score_and_notify(source, result)

            logger.info(f"[{source}] Scrape complete. New: {new_jobs}")
            return result

    def _score_and_notify(self, source: str, scrape_result: Dict):
        """Score new jobs and send alerts for top matches."""
        try:
            # Fetch unscored jobs from this source
            unscored = get_jobs(source=source, min_score=0, limit=500)
            if not unscored:
                return

            import pandas as pd

            df = pd.DataFrame(unscored)
            df = self.ai_model.predict_with_breakdown(df)

            top_jobs = []
            for _, row in df.iterrows():
                score = int(row.get("AI_Score", 0))
                url = row.get("url", "")
                if score >= 85:
                    top_jobs.append(
                        {
                            "title": row.get("title", ""),
                            "company": row.get("company", ""),
                            "score": score,
                            "url": url,
                            "source": source,
                        }
                    )
                # Update DB with score
                from src.database import update_job_scores

                update_job_scores(url, row.to_dict())

            if top_jobs and self.notifier:
                self.notifier.send_top_matches_alert(top_jobs)
                logger.info(f"Sent alert for {len(top_jobs)} top jobs from {source}")
        except Exception as e:
            logger.error(f"Scoring/notify failed: {e}")

    def get_status(self) -> Dict:
        """Return current scheduler status and recent stats."""
        jobs = self.scheduler.get_jobs()
        return {
            "running": self._running,
            "scheduled_jobs": [{"id": j.id, "next_run": str(j.next_run_time)} for j in jobs],
            "stats": get_stats(),
        }


# ── Standalone runner ─────────────────────────────────────────────


def run_scheduler_foreground(config: Optional[Dict] = None):
    """Run the scheduler in the main thread (for Docker/containers)."""
    scheduler = JobScheduler(config=config)
    scheduler.start()
    logger.info("Scheduler running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(60)
            status = scheduler.get_status()
            logger.info(f"Heartbeat: {status['stats']}")
    except KeyboardInterrupt:
        scheduler.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    run_scheduler_foreground()
