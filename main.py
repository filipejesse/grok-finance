"""Cloud Functions for Firebase entry point (Python 3.10+). Locally, use cli.py instead.

Secrets live in Google Secret Manager; the GitHub Actions deploy copies them from
the repository's GitHub secrets. The summary is never logged, only e-mailed.
"""
from __future__ import annotations

import logging
from datetime import datetime

from firebase_functions import options, scheduler_fn
from firebase_functions.params import SecretParam

import config
import emailer
import report
from processor import TZ

PLUGGY_CLIENT_ID = SecretParam("PLUGGY_CLIENT_ID")
PLUGGY_CLIENT_SECRET = SecretParam("PLUGGY_CLIENT_SECRET")
PLUGGY_ITEM_IDS = SecretParam("PLUGGY_ITEM_IDS")
GMAIL_ADDRESS = SecretParam("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = SecretParam("GMAIL_APP_PASSWORD")

options.set_global_options(region=config.CLOUD_REGION, max_instances=1)


@scheduler_fn.on_schedule(
    schedule=config.CLOUD_SCHEDULE,
    timezone=scheduler_fn.Timezone("America/Sao_Paulo"),
    secrets=[PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET, PLUGGY_ITEM_IDS, GMAIL_ADDRESS, GMAIL_APP_PASSWORD],
    timeout_sec=300,
    memory=options.MemoryOption.MB_256,
)
def send_summary(event: scheduler_fn.ScheduledEvent) -> None:
    item_ids = [i.strip() for i in PLUGGY_ITEM_IDS.value.split(",") if i.strip()]
    summary, text = report.generate(
        PLUGGY_CLIENT_ID.value, PLUGGY_CLIENT_SECRET.value, item_ids, datetime.now(TZ).date()
    )
    emailer.send_summary(
        GMAIL_ADDRESS.value, GMAIL_APP_PASSWORD.value, f"Dados financeiros - {summary['period']}", text
    )
    logging.info("Summary for %s sent.", summary["period"])
