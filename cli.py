"""Fetch bank data from Meu Pluggy and print a Grok-ready summary.

Usage:
    python cli.py                 # print the summary
    python cli.py --save          # also write output/resumo-YYYY-MM.txt and .json
    python cli.py --email         # also e-mail it (needs GMAIL_* in .env)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import config
import emailer
import report
from pluggy_client import PluggyError
from processor import TZ

OUTPUT_DIR = Path(__file__).parent / "output"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save", action="store_true", help="save .txt and .json to output/")
    parser.add_argument("--email", action="store_true", help="send the summary by e-mail")
    args = parser.parse_args()

    required = [
        ("PLUGGY_CLIENT_ID", config.PLUGGY_CLIENT_ID),
        ("PLUGGY_CLIENT_SECRET", config.PLUGGY_CLIENT_SECRET),
        ("PLUGGY_ITEM_IDS", config.PLUGGY_ITEM_IDS),
    ]
    if args.email:
        required += [("GMAIL_ADDRESS", config.GMAIL_ADDRESS), ("GMAIL_APP_PASSWORD", config.GMAIL_APP_PASSWORD)]
    missing = [name for name, value in required if not value]
    if missing:
        print(f"Missing in .env: {', '.join(missing)} (see .env.example)", file=sys.stderr)
        return 1

    today = datetime.now(TZ).date()
    try:
        summary, text = report.generate(
            config.PLUGGY_CLIENT_ID, config.PLUGGY_CLIENT_SECRET, config.PLUGGY_ITEM_IDS, today
        )
    except PluggyError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(text)

    if args.save:
        OUTPUT_DIR.mkdir(exist_ok=True)
        stem = OUTPUT_DIR / f"resumo-{today:%Y-%m}"
        stem.with_suffix(".txt").write_text(text, encoding="utf-8")
        stem.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {stem}.txt and {stem}.json", file=sys.stderr)
    if args.email:
        emailer.send_summary(
            config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD, f"Resumo financeiro - {summary['period']}", text
        )
        print(f"E-mailed to {config.GMAIL_ADDRESS}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
