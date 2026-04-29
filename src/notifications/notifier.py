"""
Notification dispatcher for new high-score jobs.
Supports Email (SMTP), Discord webhooks, and Slack webhooks.
Reads credentials from environment variables (never hardcoded).
"""
import os
import json
from typing import List, Dict
from datetime import datetime

import requests
from src.utils.logger import setup_logger

logger = setup_logger("Notifier")


class Notifier:
    def __init__(self):
        self.email_enabled = os.getenv("NOTIFY_EMAIL", "false").lower() == "true"
        self.discord_enabled = bool(os.getenv("DISCORD_WEBHOOK_URL"))
        self.slack_enabled = bool(os.getenv("SLACK_WEBHOOK_URL"))

    def send_top_matches_alert(self, jobs: List[Dict]):
        """Dispatch alerts for new top-match jobs (score >= 85)."""
        if not jobs:
            return
        if self.email_enabled:
            self._send_email(jobs)
        if self.discord_enabled:
            self._send_discord(jobs)
        if self.slack_enabled:
            self._send_slack(jobs)

    def _send_email(self, jobs: List[Dict]):
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            sender = os.getenv("SMTP_USER", "")
            password = os.getenv("SMTP_PASS", "")
            recipient = os.getenv("NOTIFY_EMAIL_TO", sender)

            if not sender or not password:
                logger.warning("Email credentials not configured. Skipping email alert.")
                return

            body_lines = [f"🎯 {j['title']} at {j['company']} — Score: {j['score']}\n{j['url']}\n" for j in jobs[:5]]
            body = f"""Dream Hunt found {len(jobs)} new top-match job(s):

{chr(10).join(body_lines)}

— Dream Hunt AI Scheduler
"""
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = recipient
            msg["Subject"] = f"🚀 {len(jobs)} New Top Matches — Dream Hunt"
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(sender, password)
                server.send_message(msg)
            logger.info(f"Email alert sent to {recipient}")
        except Exception as e:
            logger.error(f"Email alert failed: {e}")

    def _send_discord(self, jobs: List[Dict]):
        try:
            webhook = os.getenv("DISCORD_WEBHOOK_URL")
            if not webhook:
                return
            embeds = []
            for j in jobs[:5]:
                embeds.append({
                    "title": j["title"],
                    "description": f"**{j['company']}** | Score: {j['score']}\n{j['url']}",
                    "color": 0x10b981,
                })
            payload = {
                "content": f"🚀 Dream Hunt found **{len(jobs)}** new top-match job(s)!",
                "embeds": embeds,
            }
            requests.post(webhook, json=payload, timeout=10)
            logger.info("Discord alert sent.")
        except Exception as e:
            logger.error(f"Discord alert failed: {e}")

    def _send_slack(self, jobs: List[Dict]):
        try:
            webhook = os.getenv("SLACK_WEBHOOK_URL")
            if not webhook:
                return
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚀 Dream Hunt found {len(jobs)} new top-match job(s)!*",
                    },
                }
            ]
            for j in jobs[:5]:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*<{j['url']}|{j['title']}>*\n{j['company']} | Score: {j['score']}",
                    },
                })
            requests.post(webhook, json={"blocks": blocks}, timeout=10)
            logger.info("Slack alert sent.")
        except Exception as e:
            logger.error(f"Slack alert failed: {e}")
