"""Thin client for the Pluggy API (used by Meu Pluggy).

Only the endpoints this project needs: auth, items, accounts and transactions.
Docs: https://docs.pluggy.ai
"""
from __future__ import annotations

from datetime import date
from typing import Any

import requests

BASE_URL = "https://api.pluggy.ai"
TIMEOUT = 30
PAGE_SIZE = 500  # API maximum


class PluggyError(RuntimeError):
    pass


class PluggyClient:
    def __init__(self, client_id: str, client_secret: str, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._authenticate(client_id, client_secret)

    def _authenticate(self, client_id: str, client_secret: str) -> None:
        resp = self.session.post(
            f"{self.base_url}/auth",
            json={"clientId": client_id, "clientSecret": client_secret},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise PluggyError(f"Authentication failed (HTTP {resp.status_code}): {resp.text}")
        self.session.headers["X-API-KEY"] = resp.json()["apiKey"]

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            raise PluggyError(f"GET {path} failed (HTTP {resp.status_code}): {resp.text}")
        return resp.json()

    def get_item(self, item_id: str) -> dict[str, Any]:
        """An item is one bank connection."""
        return self._get(f"/items/{item_id}")

    def get_accounts(self, item_id: str) -> list[dict[str, Any]]:
        return self._get("/accounts", {"itemId": item_id})["results"]

    def get_transactions(self, account_id: str, date_from: date, date_to: date) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self._get(
                "/transactions",
                {
                    "accountId": account_id,
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                    "pageSize": PAGE_SIZE,
                    "page": page,
                },
            )
            results.extend(data["results"])
            if page >= data.get("totalPages", 1):
                return results
            page += 1
