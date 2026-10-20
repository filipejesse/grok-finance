"""Fetch bank data from Meu Pluggy and print a Grok-ready summary.

Usage:
    python main.py                 # print the summary
    python main.py --save          # also write output/resumo-YYYY-MM.txt and .json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import config
from pluggy_client import PluggyClient, PluggyError
from processor import TZ, build_summary, format_text, normalize

OUTPUT_DIR = Path(__file__).parent / "output"


def first_day_months_ago(today: date, months: int) -> date:
    month_index = today.year * 12 + today.month - 1 - months
    return date(month_index // 12, month_index % 12 + 1, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save", action="store_true", help="save .txt and .json to output/")
    args = parser.parse_args()

    missing = [
        name
        for name, value in [
            ("PLUGGY_CLIENT_ID", config.PLUGGY_CLIENT_ID),
            ("PLUGGY_CLIENT_SECRET", config.PLUGGY_CLIENT_SECRET),
            ("PLUGGY_ITEM_IDS", config.PLUGGY_ITEM_IDS),
        ]
        if not value
    ]
    if missing:
        print(f"Missing in .env: {', '.join(missing)} (see .env.example)", file=sys.stderr)
        return 1

    today = datetime.now(TZ).date()
    date_from = first_day_months_ago(today, config.PREVIOUS_MONTHS)

    try:
        client = PluggyClient(config.PLUGGY_CLIENT_ID, config.PLUGGY_CLIENT_SECRET)
        accounts, raw_transactions = [], []
        for item_id in config.PLUGGY_ITEM_IDS:
            item = client.get_item(item_id)
            connector = (item.get("connector") or {}).get("name", item_id)
            if item.get("status") != "UPDATED":
                print(f"Warning: {connector} status is {item.get('status')}; data may be stale.", file=sys.stderr)
            for account in client.get_accounts(item_id):
                accounts.append(account)
                raw_transactions += client.get_transactions(account["id"], date_from, today)
    except PluggyError as exc:
        print(exc, file=sys.stderr)
        return 1

    transactions = normalize(raw_transactions, {a["id"]: a for a in accounts})
    summary = build_summary(accounts, transactions, today)
    text = format_text(summary)
    print(text)

    if args.save:
        OUTPUT_DIR.mkdir(exist_ok=True)
        stem = OUTPUT_DIR / f"resumo-{today:%Y-%m}"
        stem.with_suffix(".txt").write_text(text, encoding="utf-8")
        stem.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {stem}.txt and {stem}.json", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
