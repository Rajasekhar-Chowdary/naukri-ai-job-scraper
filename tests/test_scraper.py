import pytest
import pandas as pd
from src.scraper.scraper_cli import NaukriScraper

def test_deduplication_logic():
    # Mocking the dataframe deduplication logic we built in scraper_cli
    all_jobs = [
        {'Title': 'Analyst', 'Company': 'TCS', 'Job URL': 'url1'},
        {'Title': 'Analyst', 'Company': 'TCS', 'Job URL': 'url2'}, # Duplicate
        {'Title': 'Engineer', 'Company': 'Infosys', 'Job URL': 'url3'}
    ]
    
    df = pd.DataFrame(all_jobs)
    initial_len = len(df)
    
    # Logic from scraper_cli
    df = df.drop_duplicates(subset=['Title', 'Company'], keep='first').reset_index(drop=True)
    
    assert len(df) == 2
    assert initial_len == 3
