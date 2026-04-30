"""Tests for the SQLite database layer."""

import pytest
import os
import tempfile
from src.database import (
    init_db,
    insert_jobs,
    get_jobs,
    get_stats,
    save_feedback,
    get_feedback_counts,
    update_job_scores,
)


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """Use a temporary database for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("JOB_DB_PATH", path)
    init_db()
    yield path
    os.unlink(path)


def test_insert_and_dedup():
    jobs = [
        {"Title": "Analyst", "Company": "TCS", "Job URL": "http://example.com/1"},
        {"Title": "Analyst", "Company": "TCS", "Job URL": "http://example.com/1"},  # dup
        {"Title": "Engineer", "Company": "Infosys", "Job URL": "http://example.com/2"},
    ]
    inserted, duplicates = insert_jobs(jobs, source="naukri")
    assert inserted == 2
    assert duplicates == 1


def test_get_jobs_filtering():
    insert_jobs(
        [
            {"Title": "Python Dev", "Company": "A", "Job URL": "http://a.com/1", "Skills": "Python, SQL"},
            {"Title": "HR Manager", "Company": "B", "Job URL": "http://b.com/1", "Skills": "Communication"},
        ],
        source="naukri",
    )
    update_job_scores(
        "http://a.com/1", {"AI_Score": 90, "Score_Skill": 80, "Score_Title": 85, "Score_Desc": 88, "Score_Exp": 90}
    )
    update_job_scores(
        "http://b.com/1", {"AI_Score": 30, "Score_Skill": 20, "Score_Title": 25, "Score_Desc": 30, "Score_Exp": 40}
    )

    results = get_jobs(min_score=50)
    assert len(results) == 1
    assert results[0]["title"] == "Python Dev"

    results = get_jobs(search="HR")
    assert len(results) == 1
    assert results[0]["title"] == "HR Manager"


def test_feedback_and_stats():
    insert_jobs(
        [
            {"Title": "Data Analyst", "Company": "X", "Job URL": "http://x.com/1"},
            {"Title": "Data Scientist", "Company": "Y", "Job URL": "http://y.com/1"},
        ],
        source="naukri",
    )
    save_feedback("http://x.com/1", "applied")
    save_feedback("http://y.com/1", "rejected")

    counts = get_feedback_counts()
    assert counts["applied"] == 1
    assert counts["rejected"] == 1

    stats = get_stats()
    assert stats["total_jobs"] == 2
