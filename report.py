"""Fetch everything from Pluggy and build the summary. Shared by the CLI and the cloud function."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import config
from pluggy_client import PluggyClient
from processor import build_summary, format_text, normalize

log = logging.getLogger(__name__)


def first_day_months_ago(today: date, months: int) -> date:
    month_index = today.year * 12 + today.month - 1 - months
    return date(month_index // 12, month_index % 12 + 1, 1)


def generate(client_id: str, client_secret: str, item_ids: list[str], today: date) -> tuple[dict[str, Any], str]:
    """Return (summary dict, summary text). Raises PluggyError on API failures."""
    date_from = first_day_months_ago(today, config.PREVIOUS_MONTHS)
    client = PluggyClient(client_id, client_secret)
    accounts, raw_transactions = [], []
    for item_id in item_ids:
        item = client.get_item(item_id)
        if item.get("status") != "UPDATED":
            connector = (item.get("connector") or {}).get("name", item_id)
            log.warning("%s status is %s; data may be stale.", connector, item.get("status"))
        for account in client.get_accounts(item_id):
            accounts.append(account)
            raw_transactions += client.get_transactions(account["id"], date_from, today)

    transactions = normalize(raw_transactions, {a["id"]: a for a in accounts})
    summary = build_summary(accounts, transactions, today)
    return summary, format_text(summary)
