"""
Naukri.com scraper — inherits from BaseScraper.
Implements source-specific URL building and card parsing.
"""

import math
from typing import List, Dict, Optional
from urllib.parse import urlencode

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.scraper.base import BaseScraper, clear_session_status
from src.utils.logger import setup_logger

logger = setup_logger("Naukri")

# ── Filter mappings (exported for dashboard / CLI) ─────────────────
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
    role, location, page_num=1, days=0, experience_min=None, salary_bucket=None, industry_id=None, work_mode=None
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


class NaukriScraper(BaseScraper):
    SOURCE_NAME = "naukri"
    STAGES = ["Initializing", "Fetching", "Parsing", "AI Scoring", "Saving"]
    JOBS_PER_PAGE = 20

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

    def _build_url(
        self,
        role: str,
        location: str,
        page: int,
        days: int = 0,
        experience_min: Optional[int] = None,
        salary_bucket: Optional[str] = None,
        industry_id: Optional[str] = None,
        work_mode: Optional[list] = None,
        **kwargs,
    ) -> str:
        return build_naukri_url(
            role=role,
            location=location,
            page_num=page,
            days=days,
            experience_min=experience_min,
            salary_bucket=salary_bucket,
            industry_id=industry_id,
            work_mode=work_mode,
        )

    def _parse_cards(self) -> List[Dict]:
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

                job = self._standardize_job(
                    {
                        "Title": title,
                        "Company": self._find_text(card, self._COMPANY_SELECTORS, default="Not mentioned"),
                        "Location": self._find_text(card, self._LOCATION_SELECTORS, default="Not mentioned"),
                        "Experience": self._find_text(card, self._EXPERIENCE_SELECTORS, default="Not mentioned"),
                        "Description": self._find_text(card, self._DESC_SELECTORS, default="No description"),
                        "Posted": self._find_text(card, self._POSTED_SELECTORS, default="N/A"),
                        "Skills": ", ".join(
                            t.text.strip()
                            for t in card.find_elements(By.CSS_SELECTOR, ", ".join(self._TAGS_SELECTORS))
                            if t.text.strip()
                        )
                        or "N/A",
                        "Job URL": link,
                    }
                )
                jobs.append(job)
            except Exception as e:
                logger.debug(f"Skipping card due to parse error: {e}")
        return jobs
