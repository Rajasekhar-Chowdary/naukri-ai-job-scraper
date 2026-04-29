"""
Indeed India scraper.
Indeed uses heavy anti-bot measures; this implementation uses
stealth Selenium with randomized delays.
"""
import time
import random
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

logger = setup_logger("Indeed")


class IndeedScraper(BaseScraper):
    SOURCE_NAME = "indeed"

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
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception as e:
            logger.error(f"Indeed WebDriver init failed: {e}")
            raise

    def _quit_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def _build_url(self, role: str, location: str, page: int = 1) -> str:
        q = quote(role)
        loc = quote(location) if location else "India"
        url = f"https://in.indeed.com/jobs?q={q}&l={loc}"
        if page > 1:
            start = (page - 1) * 15
            url += f"&start={start}"
        return url

    def _parse_cards(self) -> List[Dict]:
        jobs = []
        try:
            wait = WebDriverWait(self.driver, 20)
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='slider_container']")))
            cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='slider_container']")
        except Exception:
            # Older Indeed layout fallback
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, ".job_seen_beacon, .slider_container")
            except Exception:
                cards = []

        for card in cards:
            try:
                title_els = card.find_elements(By.CSS_SELECTOR, "h2 a span, .jobTitle span")
                company_els = card.find_elements(By.CSS_SELECTOR, "[data-testid='company-name'], .companyName")
                loc_els = card.find_elements(By.CSS_SELECTOR, "[data-testid='text-location'], .companyLocation")
                summary_els = card.find_elements(By.CSS_SELECTOR, ".jobsearch-JobComponent-description, [data-testid='jobs-salary']")
                link_els = card.find_elements(By.CSS_SELECTOR, "h2 a")

                title = title_els[0].text.strip() if title_els else ""
                company = company_els[0].text.strip() if company_els else "Not mentioned"
                location = loc_els[0].text.strip() if loc_els else "Not mentioned"
                link = ""
                if link_els:
                    href = link_els[0].get_attribute("href")
                    link = f"https://in.indeed.com{href}" if href and href.startswith("/") else href

                if not title:
                    continue

                posted = "N/A"
                date_els = card.find_elements(By.CSS_SELECTOR, "[data-testid='job-date'], span.date")
                if date_els:
                    posted = date_els[0].text.strip()

                jobs.append(self._standardize_job({
                    "Title": title,
                    "Company": company,
                    "Location": location,
                    "Experience": "Not mentioned",
                    "Description": summary_els[0].text.strip()[:300] if summary_els else "No description",
                    "Skills": "N/A",
                    "Posted": posted,
                    "Job URL": link,
                }))
            except Exception as e:
                logger.debug(f"Skipping Indeed card: {e}")
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
            pages = min(pages, (max_jobs // 15) + 1)

        self._init_driver()
        all_jobs = []

        try:
            for page in range(1, pages + 1):
                url = self._build_url(role, location, page)
                logger.info(f"Indeed page {page}/{pages}: {url}")
                try:
                    self.driver.get(url)
                    self._jitter(3.0, 6.0)
                    page_jobs = self._parse_cards()
                    all_jobs.extend(page_jobs)
                    logger.info(f"Indeed page {page}: scraped {len(page_jobs)} jobs")
                    if progress_callback:
                        progress_callback(page, pages, len(all_jobs), "Fetching", url)
                except Exception as e:
                    logger.warning(f"Indeed page {page} failed: {e}")
                if max_jobs and len(all_jobs) >= max_jobs:
                    break
        finally:
            self._quit_driver()

        return all_jobs
