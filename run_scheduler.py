#!/usr/bin/env python3
"""
Dream Hunt — Background Scheduler
Runs scrapers continuously on configured intervals and sends alerts.
Use this in Docker or as a systemd service for 24/7 operation.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.scheduler.job_scheduler import run_scheduler_foreground

if __name__ == "__main__":
    run_scheduler_foreground()
