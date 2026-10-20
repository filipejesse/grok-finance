"""Credentials and runtime settings. No personal finance rules live here:
interpreting the data is left to Grok."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

PLUGGY_CLIENT_ID = os.getenv("PLUGGY_CLIENT_ID", "")
PLUGGY_CLIENT_SECRET = os.getenv("PLUGGY_CLIENT_SECRET", "")
# The Pluggy API has no "list my items" endpoint: copy each connection's Item ID
# from the Pluggy demo app, comma-separated.
PLUGGY_ITEM_IDS = [i.strip() for i in os.getenv("PLUGGY_ITEM_IDS", "").split(",") if i.strip()]

# Only needed for `cli.py --email`; in the cloud these come from Secret Manager.
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

# Cloud function: region and when the summary is e-mailed (cron, São Paulo time).
CLOUD_REGION = "southamerica-east1"
CLOUD_SCHEDULE = "0 8 * * 1"  # Mondays at 08:00

# Months of history fetched besides the current one (sent only as a short recap).
PREVIOUS_MONTHS = 1
# Categories listed per previous month in the recap.
RECAP_CATEGORIES = 8
