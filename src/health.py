"""Health check endpoint for monitoring and load balancers."""

import os
import sqlite3
from src.database import _db_path
from src.utils.logger import setup_logger

logger = setup_logger("Health")


def check_health() -> dict:
    """Return system health status."""
    status = {"status": "healthy", "checks": {}}

    # Database check
    try:
        conn = sqlite3.connect(_db_path())
        conn.execute("SELECT 1 FROM jobs LIMIT 1")
        conn.close()
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {e}"
        status["status"] = "degraded"

    # Config check
    config_path = "config/profile_config.json"
    if os.path.exists(config_path):
        status["checks"]["config"] = "ok"
    else:
        status["checks"]["config"] = "missing (using defaults)"

    # Data directory check
    if os.path.exists("data") and os.path.isdir("data"):
        status["checks"]["data_dir"] = "ok"
    else:
        status["checks"]["data_dir"] = "missing"
        status["status"] = "degraded"

    return status
