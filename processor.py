"""Cleaning, categorization and summary generation. No network access here."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import config

TZ = ZoneInfo("America/Sao_Paulo")
MONTHS_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


@dataclass
class Transaction:
    id: str
    account: str
    date: date
    description: str
    amount: float  # always positive; see `inflow`
    inflow: bool
    category: str
    ignored: bool  # internal transfer / card bill payment


def brl(value: float, decimals: int = 2) -> str:
    s = f"{abs(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if value < 0 else ''}R$ {s}"


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_PT[month - 1]}/{year}"


def account_name(account: dict[str, Any]) -> str:
    return account.get("marketingName") or account.get("name") or account["id"]


def _parse_date(raw: str) -> date:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(TZ).date()


def _clean_description(raw: str) -> str:
    return re.sub(r"\s+", " ", raw or "").strip() or "(sem descrição)"


def categorize(description: str, pluggy_category: str | None) -> str:
    desc = description.lower()
    for keyword, label in config.KEYWORD_RULES.items():
        if keyword.lower() in desc:
            return label
    if pluggy_category:
        return config.CATEGORY_LABELS.get(pluggy_category.lower(), pluggy_category)
    return config.UNCATEGORIZED


def _is_ignored(pluggy_category: str | None) -> bool:
    cat = (pluggy_category or "").lower()
    return any(ignored in cat for ignored in config.IGNORED_CATEGORIES)


def normalize(raw_transactions: list[dict[str, Any]], accounts_by_id: dict[str, dict[str, Any]]) -> list[Transaction]:
    """Convert raw Pluggy transactions, dropping duplicates."""
    seen_ids: set[str] = set()
    seen_keys: set[tuple] = set()
    result: list[Transaction] = []
    for raw in raw_transactions:
        if raw["id"] in seen_ids:
            continue
        seen_ids.add(raw["id"])

        description = _clean_description(raw.get("description") or raw.get("descriptionRaw"))
        amount = float(raw.get("amountInAccountCurrency") or raw["amount"])
        tx_type = raw.get("type")
        inflow = tx_type == "CREDIT" if tx_type in ("CREDIT", "DEBIT") else amount > 0
        tx = Transaction(
            id=raw["id"],
            account=account_name(accounts_by_id[raw["accountId"]]),
            date=_parse_date(raw["date"]),
            description=description,
            amount=abs(amount),
            inflow=inflow,
            category=categorize(description, raw.get("category")),
            ignored=_is_ignored(raw.get("category")),
        )
        # Same movement reported twice under different IDs (e.g. pending -> posted).
        key = (tx.account, tx.date, round(tx.amount, 2), tx.inflow, tx.description.lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        result.append(tx)
    result.sort(key=lambda t: t.date)
    return result


def _totals(transactions: list[Transaction]) -> dict[str, Any]:
    counted = [t for t in transactions if not t.ignored]
    inflows = sum(t.amount for t in counted if t.inflow)
    outflows = sum(t.amount for t in counted if not t.inflow)
    by_category: dict[str, float] = defaultdict(float)
    for t in counted:
        if not t.inflow:
            by_category[t.category] += t.amount
    top = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "net": round(inflows - outflows, 2),
        "top_categories": [{"category": c, "total": round(v, 2)} for c, v in top[: config.TOP_CATEGORIES]],
    }


def _atypical(transactions: list[Transaction]) -> list[Transaction]:
    outflows = [t for t in transactions if not t.inflow and not t.ignored]
    amounts_by_category: dict[str, list[float]] = defaultdict(list)
    for t in outflows:
        amounts_by_category[t.category].append(t.amount)

    flagged = []
    for t in outflows:
        amounts = amounts_by_category[t.category]
        # Compare against the category average excluding the transaction itself.
        others_avg = (sum(amounts) - t.amount) / (len(amounts) - 1) if len(amounts) > 1 else 0
        if t.amount >= config.ATYPICAL_MIN_AMOUNT or (
            len(amounts) >= 3 and t.amount >= others_avg * config.ATYPICAL_CATEGORY_FACTOR
        ):
            flagged.append(t)
    flagged.sort(key=lambda t: t.amount, reverse=True)
    return flagged[: config.MAX_ATYPICAL]


def _account_summary(account: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "name": account_name(account),
        "type": account.get("type"),
        "balance": round(float(account.get("balance") or 0), 2),
    }
    credit = account.get("creditData") or {}
    if account.get("type") == "CREDIT":
        entry["credit_limit"] = credit.get("creditLimit")
        entry["available_limit"] = credit.get("availableCreditLimit")
    return entry


def build_summary(
    accounts: list[dict[str, Any]],
    transactions: list[Transaction],
    today: date,
) -> dict[str, Any]:
    current = [t for t in transactions if (t.date.year, t.date.month) == (today.year, today.month)]
    previous: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for t in transactions:
        if (t.date.year, t.date.month) != (today.year, today.month):
            previous[(t.date.year, t.date.month)].append(t)

    return {
        "period": month_label(today.year, today.month),
        "generated_on": today.isoformat(),
        "accounts": [_account_summary(a) for a in accounts],
        "current_month": _totals(current),
        "atypical": [
            {
                "date": t.date.isoformat(),
                "description": t.description,
                "amount": round(t.amount, 2),
                "category": t.category,
                "account": t.account,
            }
            for t in _atypical(current)
        ],
        "previous_months": [
            {"period": month_label(y, m), **_totals(txs)}
            for (y, m), txs in sorted(previous.items(), reverse=True)
        ],
        "fixed_context": list(config.FIXED_CONTEXT),
    }


def format_text(summary: dict[str, Any]) -> str:
    lines = [f"=== RESUMO FINANCEIRO - {summary['period']} ===", "Contas:"]
    for acc in summary["accounts"]:
        if acc["type"] == "CREDIT":
            line = f"- {acc['name']} (cartão): fatura atual {brl(acc['balance'])}"
            if acc.get("available_limit") is not None:
                line += f", limite disponível {brl(acc['available_limit'])}"
            lines.append(line)
        else:
            lines.append(f"- {acc['name']}: {brl(acc['balance'])}")

    cur = summary["current_month"]
    lines += [
        "",
        f"Movimentação do período (até {date.fromisoformat(summary['generated_on']).strftime('%d/%m')}):",
        f"- Entradas: {brl(cur['inflows'])}",
        f"- Saídas: {brl(cur['outflows'])}",
        f"- Saldo líquido: {brl(cur['net'])}",
        "",
        "Principais categorias:",
    ]
    if cur["top_categories"]:
        for i, cat in enumerate(cur["top_categories"], 1):
            lines.append(f"{i}. {cat['category']}: {brl(cat['total'], 0)}")
    else:
        lines.append("- (nenhuma saída no período)")

    lines += ["", "Transações atípicas:"]
    if summary["atypical"]:
        for t in summary["atypical"]:
            day = date.fromisoformat(t["date"]).strftime("%d/%m")
            lines.append(f"- [{day}] {t['description']} - {brl(t['amount'])} ({t['category']}, {t['account']})")
    else:
        lines.append("- nenhuma")

    if summary["previous_months"]:
        lines += ["", "Meses anteriores:"]
        for p in summary["previous_months"]:
            cats = ", ".join(f"{c['category']} {brl(c['total'], 0)}" for c in p["top_categories"][:3])
            lines.append(
                f"- {p['period']}: entradas {brl(p['inflows'])}, saídas {brl(p['outflows'])}, "
                f"líquido {brl(p['net'])}" + (f" | maiores: {cats}" if cats else "")
            )

    context = list(summary["fixed_context"])
    for acc in summary["accounts"]:
        if acc.get("credit_limit") is not None:
            context.append(f"Limite cartão {acc['name']}: {brl(acc['credit_limit'], 0)}")
    if context:
        lines += ["", "Contexto fixo:"] + [f"- {c}" for c in context]
    return "\n".join(lines) + "\n"
