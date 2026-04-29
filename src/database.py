"""
Unified SQLite database layer for job storage across all scrapers.
Replaces fragile CSV files with ACID transactions and cross-source deduplication.
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
from src.utils.logger import setup_logger

logger = setup_logger("Database")
def _db_path() -> str:
    return os.environ.get("JOB_DB_PATH", "data/jobs.db")


def _get_conn() -> sqlite3.Connection:
    path = _db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                external_id TEXT,
                title TEXT NOT NULL,
                company TEXT,
                location TEXT,
                experience TEXT,
                description TEXT,
                skills TEXT,
                url TEXT UNIQUE NOT NULL,
                posted TEXT,
                ai_score INTEGER,
                score_skill REAL,
                score_title REAL,
                score_desc REAL,
                score_exp REAL,
                is_applied INTEGER DEFAULT 0,
                is_rejected INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
            CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(ai_score);
            CREATE INDEX IF NOT EXISTS idx_jobs_url ON jobs(url);
            CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT NOT NULL,
                label TEXT NOT NULL CHECK(label IN ('applied','rejected')),
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(job_url) REFERENCES jobs(url)
            );

            CREATE TABLE IF NOT EXISTS scrapes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                role TEXT,
                location TEXT,
                status TEXT DEFAULT 'pending',
                jobs_found INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                error_msg TEXT,
                started_at TEXT DEFAULT (datetime('now')),
                completed_at TEXT
            );
        """)
        conn.commit()
    logger.info("Database initialized.")


# ── Job CRUD ──────────────────────────────────────────────────────

def insert_jobs(jobs: List[Dict], source: str) -> Tuple[int, int]:
    """
    Bulk insert jobs with cross-source deduplication by URL.
    Returns (inserted_count, duplicate_count).
    """
    if not jobs:
        return 0, 0

    inserted = 0
    duplicates = 0

    with _get_conn() as conn:
        for job in jobs:
            url = job.get("Job URL") or job.get("url") or ""
            if not url:
                continue
            try:
                conn.execute(
                    """
                    INSERT INTO jobs (
                        source, external_id, title, company, location,
                        experience, description, skills, url, posted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source,
                        job.get("id"),
                        job.get("Title", ""),
                        job.get("Company", ""),
                        job.get("Location", ""),
                        job.get("Experience", ""),
                        job.get("Description", ""),
                        job.get("Skills", ""),
                        url,
                        job.get("Posted", ""),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()

    logger.info(f"Inserted {inserted} new jobs from {source} ({duplicates} duplicates skipped).")
    return inserted, duplicates


def get_jobs(
    min_score: int = 0,
    source: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict]:
    """Fetch jobs with optional filters. Returns list of dicts."""
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if min_score > 0:
        query += " AND ai_score >= ?"
        params.append(min_score)
    if source:
        query += " AND source = ?"
        params.append(source)
    if search:
        query += " AND (title LIKE ? OR company LIKE ? OR skills LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    query += " ORDER BY ai_score DESC, created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_job_by_url(url: str) -> Optional[Dict]:
    with _get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None


def update_job_scores(url: str, scores: Dict):
    """Update AI scores for a job."""
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE jobs SET
                ai_score = ?,
                score_skill = ?,
                score_title = ?,
                score_desc = ?,
                score_exp = ?,
                updated_at = datetime('now')
            WHERE url = ?
            """,
            (
                scores.get("AI_Score"),
                scores.get("Score_Skill"),
                scores.get("Score_Title"),
                scores.get("Score_Desc"),
                scores.get("Score_Exp"),
                url,
            ),
        )
        conn.commit()


def save_feedback(url: str, label: str):
    """Save applied/rejected feedback and update job flags."""
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO feedback (job_url, label) VALUES (?, ?)",
            (url, label),
        )
        flag = "is_applied" if label == "applied" else "is_rejected"
        conn.execute(f"UPDATE jobs SET {flag} = 1 WHERE url = ?", (url,))
        conn.commit()


def get_feedback_counts() -> Dict[str, int]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT label, COUNT(*) FROM feedback GROUP BY label"
        ).fetchall()
        return {row[0]: row[1] for row in rows}


# ── Scrape log ────────────────────────────────────────────────────

def start_scrape(source: str, role: str, location: str) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scrapes (source, role, location, status) VALUES (?, ?, ?, 'running')",
            (source, role, location),
        )
        conn.commit()
        return cur.lastrowid


def finish_scrape(scrape_id: int, jobs_found: int, new_jobs: int, error_msg: Optional[str] = None):
    with _get_conn() as conn:
        conn.execute(
            """
            UPDATE scrapes SET
                status = ?,
                jobs_found = ?,
                new_jobs = ?,
                error_msg = ?,
                completed_at = datetime('now')
            WHERE id = ?
            """,
            ("failed" if error_msg else "completed", jobs_found, new_jobs, error_msg, scrape_id),
        )
        conn.commit()


def get_latest_scrapes(limit: int = 10) -> List[Dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM scrapes ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


# ── Stats ─────────────────────────────────────────────────────────

def get_stats() -> Dict:
    with _get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        top = conn.execute("SELECT COUNT(*) FROM jobs WHERE ai_score >= 85").fetchone()[0]
        good = conn.execute("SELECT COUNT(*) FROM jobs WHERE ai_score >= 50").fetchone()[0]
        sources = conn.execute(
            "SELECT source, COUNT(*) FROM jobs GROUP BY source"
        ).fetchall()
        return {
            "total_jobs": total,
            "top_matches": top,
            "good_matches": good,
            "sources": {s: c for s, c in sources},
        }
