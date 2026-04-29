"""
LinkedIn Jobs scraper.
LinkedIn heavily bot-guards its job pages. This implementation uses
stealth Selenium and targets public job search pages.
For full results, LinkedIn login may be required.
"""
import time
import random
import re
from typing import List, Dict, Optional, Callable
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from src.scraper.base import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("LinkedIn")


class LinkedInScraper(BaseScraper):
    SOURCE_NAME = "linkedin"

    def __init__(self, headless=True):
        super().__init__(headless=headless)
        self.driver = None

    def _init_driver(self):
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
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise RuntimeError(f"LinkedIn WebDriver init failed: {e}") from e

    def _quit_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def _build_url(self, role: str, location: str, page: int = 1) -> str:
        q = quote(role)
        loc = quote(location) if location else ""
        geo_id = "102713980" if "india" in location.lower() else ""  # India geoId
        url = f"https://www.linkedin.com/jobs/search?keywords={q}"
        if loc:
            url += f"&location={loc}"
        if geo_id:
            url += f"&geoId={geo_id}"
        if page > 1:
            start = (page - 1) * 25
            url += f"&start={start}"
        return url

    def _parse_cards(self) -> List[Dict]:
        jobs = []
        try:
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.jobs-search__results-list > li")))
            cards = self.driver.find_elements(By.CSS_SELECTOR, "ul.jobs-search__results-list > li")
        except Exception:
            # Fallback selectors
            cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-job-id]")

        for card in cards:
            try:
                title_el = card.find_elements(By.CSS_SELECTOR, "h3.base-search-card__title, a.job-card-list__title")
                company_el = card.find_elements(By.CSS_SELECTOR, "h4.base-search-card__subtitle, a.job-card-container__company-name")
                loc_el = card.find_elements(By.CSS_SELECTOR, "span.job-search-card__location, span.job-card-container__metadata-item")
                link_el = card.find_elements(By.CSS_SELECTOR, "a.base-card__full-link, a.job-card-list__title")

                title = title_el[0].text.strip() if title_el else ""
                company = company_el[0].text.strip() if company_el else "Not mentioned"
                location = loc_el[0].text.strip() if loc_el else "Not mentioned"
                link = link_el[0].get_attribute("href") if link_el else ""

                if not title or not link:
                    continue

                # Try to extract posted time
                posted = "N/A"
                time_els = card.find_elements(By.CSS_SELECTOR, "time")
                if time_els:
                    posted = time_els[0].get_attribute("datetime") or time_els[0].text.strip()

                jobs.append(self._standardize_job({
                    "Title": title,
                    "Company": company,
                    "Location": location,
                    "Experience": "Not mentioned",  # LinkedIn hides this behind click
                    "Description": "Click to view description",
                    "Skills": "N/A",
                    "Posted": posted,
                    "Job URL": link,
                }))
            except Exception as e:
                logger.debug(f"Skipping LinkedIn card: {e}")
        return jobs

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
        if pages is None:
            pages = 1
        if max_jobs:
            pages = min(pages, (max_jobs // 25) + 1)

        self._init_driver()
        all_jobs = []

        try:
            for page in range(1, pages + 1):
                url = self._build_url(role, location, page)
                logger.info(f"LinkedIn page {page}/{pages}: {url}")
                try:
                    self.driver.get(url)
                    self._jitter(3.0, 6.0)
                    # Scroll to lazy-load
                    for _ in range(3):
                        self.driver.execute_script("window.scrollBy(0, 800);")
                        time.sleep(random.uniform(1.0, 2.0))
                    page_jobs = self._parse_cards()
                    all_jobs.extend(page_jobs)
                    logger.info(f"LinkedIn page {page}: scraped {len(page_jobs)} jobs")
                    if progress_callback:
                        progress_callback(page, pages, len(all_jobs), "Fetching", url)
                except Exception as e:
                    logger.warning(f"LinkedIn page {page} failed: {e}")
                if max_jobs and len(all_jobs) >= max_jobs:
                    break
        finally:
            self._quit_driver()

        return all_jobs
