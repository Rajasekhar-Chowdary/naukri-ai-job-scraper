"""
Indeed India scraper — native GraphQL API implementation.
Inspired by JobSpy (github.com/speedyapply/JobSpy).

Uses Indeed's internal GraphQL API instead of Selenium,
making it extremely fast (~1s for 10 jobs) and bypassing
Cloudflare challenges that block browser-based scrapers.
"""

import math
from datetime import datetime
from typing import List, Dict, Optional, Callable

import urllib3
import requests
from requests.adapters import HTTPAdapter, Retry

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = setup_logger("Indeed")

INDEED_API_URL = "https://apis.indeed.com/graphql"
INDEED_HEADERS = {
    "Host": "apis.indeed.com",
    "content-type": "application/json",
    "indeed-api-key": "161092c2017b5bbab13edb12461a62d5a833871e7cad6d9d475304573de67ac8",
    "accept": "application/json",
    "indeed-locale": "en-US",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Indeed App 193.1",
    "indeed-app-info": "appv=193.1; appid=com.indeed.jobsearch; osv=16.6.1; os=ios; dtype=phone",
    "indeed-co": "IN",
}

JOB_SEARCH_QUERY = """
query GetJobData {{
    jobSearch(
    {what}
    {location}
    limit: {limit}
    {cursor}
    sort: RELEVANCE
    {filters}
    ) {{
    pageInfo {{
        nextCursor
    }}
    results {{
        trackingKey
        job {{
        source {{ name }}
        key
        title
        datePublished
        dateOnIndeed
        description {{ html }}
        location {{
            countryName
            countryCode
            admin1Code
            city
            postalCode
            streetAddress
            formatted {{ short long }}
        }}
        compensation {{
            estimated {{
            currencyCode
            baseSalary {{
                unitOfWork
                range {{ ... on Range {{ min max }} }}
            }}
            }}
            baseSalary {{
            unitOfWork
            range {{ ... on Range {{ min max }} }}
            }}
            currencyCode
        }}
        attributes {{ key label }}
        employer {{
            relativeCompanyPageUrl
            name
            dossier {{
            employerDetails {{
                addresses
                industry
                employeesLocalizedLabel
                revenueLocalizedLabel
                briefDescription
                ceoName
                ceoPhotoUrl
            }}
            images {{
                squareLogoUrl
            }}
            links {{
                corporateWebsite
            }}
            }}
        }}
        recruit {{
            viewJobUrl
        }}
        }}
    }}
    }}
}}
"""


class IndeedScraper(BaseScraper):
    SOURCE_NAME = "indeed"
    USES_BROWSER = False
    JOBS_PER_PAGE = 100

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
        self.seen_urls = set()

    def _build_url(self, role: str, location: str, page: int, **kwargs) -> str:
        """Not used — we call the GraphQL API directly."""
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
        Scrape Indeed jobs via GraphQL API.
        """
        target = max_jobs or 25
        self._update_stage("Initializing", 5, f"Ready to scrape '{role}' in '{location or 'Any'}'")

        all_jobs: List[Dict] = []
        cursor = None
        page_num = 1

        while len(all_jobs) < target:
            self._update_stage(
                "Fetching",
                int(5 + (len(all_jobs) / target) * 50),
                f"Loading page {page_num}...",
                len(all_jobs),
            )
            if progress_callback:
                progress_callback(page_num, pages or 1, len(all_jobs), "Fetching", "GraphQL API")

            jobs, cursor = self._scrape_page(role, location or "India", cursor, days, target - len(all_jobs))
            if not jobs:
                break

            all_jobs.extend(jobs)
            self._update_stage(
                "Parsing",
                int(55 + (len(all_jobs) / target) * 20),
                f"Parsed {len(all_jobs)} jobs so far...",
                len(all_jobs),
            )
            if progress_callback:
                progress_callback(page_num, pages or 1, len(all_jobs), "Parsing", "GraphQL API")

            page_num += 1
            if not cursor:
                break

        self._update_stage("Saving", 95, f"Done! Parsed {len(all_jobs)} jobs.", len(all_jobs))
        return all_jobs

    def _scrape_page(
        self, role: str, location: str, cursor: Optional[str], days: int, limit: int
    ) -> tuple[List[Dict], Optional[str]]:
        """Call Indeed GraphQL API and return parsed jobs + next cursor."""
        search_term = role.replace('"', '\\"') if role else ""
        what_clause = f'what: "{search_term}"' if search_term else ""
        loc_clause = f'location: {{where: "{location}", radius: 50, radiusUnit: MILES}}' if location else ""
        cursor_clause = f'cursor: "{cursor}"' if cursor else ""

        filters = ""
        if days > 0:
            filters = f'filters: {{ date: {{ field: "dateOnIndeed", start: "{days * 24}h" }} }}'

        query = JOB_SEARCH_QUERY.format(
            what=what_clause,
            location=loc_clause,
            limit=min(limit, 100),
            cursor=cursor_clause,
            filters=filters,
        )

        try:
            resp = self.session.post(
                INDEED_API_URL,
                headers=INDEED_HEADERS,
                json={"query": query},
                timeout=15,
                verify=False,
            )
            if not resp.ok:
                logger.error(f"Indeed API error: {resp.status_code} — {resp.text[:200]}")
                return [], None

            data = resp.json()
            results = data.get("data", {}).get("jobSearch", {}).get("results", [])
            next_cursor = data.get("data", {}).get("jobSearch", {}).get("pageInfo", {}).get("nextCursor")

            jobs = []
            for item in results:
                job = item.get("job", {})
                parsed = self._parse_job(job)
                if parsed:
                    jobs.append(parsed)

            return jobs, next_cursor

        except Exception as e:
            logger.error(f"Indeed GraphQL request failed: {e}")
            return [], None

    def _parse_job(self, job: dict) -> Optional[Dict]:
        """Parse a single Indeed job dict from GraphQL response."""
        try:
            job_key = job.get("key", "")
            job_url = f"https://in.indeed.com/viewjob?jk={job_key}"
            if job_url in self.seen_urls:
                return None
            self.seen_urls.add(job_url)

            title = job.get("title", "")
            employer = job.get("employer", {}) or {}
            company = employer.get("name", "Not mentioned")

            loc = job.get("location", {})
            location_str = (
                loc.get("formatted", {}).get("short") or f"{loc.get('city', '')}, {loc.get('admin1Code', '')}"
            )
            location_str = location_str.strip(", ") or "Not mentioned"

            desc = "No description"
            if job.get("description") and job["description"].get("html"):
                desc = job["description"]["html"][:500]

            posted = "N/A"
            if job.get("datePublished"):
                try:
                    ts = job["datePublished"] / 1000
                    posted = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                except Exception:
                    pass

            return self._standardize_job(
                {
                    "Title": title,
                    "Company": company,
                    "Location": location_str,
                    "Experience": "Not mentioned",
                    "Description": desc,
                    "Skills": "N/A",
                    "Posted": posted,
                    "Job URL": job_url,
                }
            )
        except Exception as e:
            logger.debug(f"Skipping Indeed job: {e}")
            return None
