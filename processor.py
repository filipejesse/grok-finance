"""Turn raw Pluggy data into a neutral, Grok-readable report. No network access here.

The report states facts only (balances, totals, every transaction of the month).
It applies no personal rules: categories are Pluggy's own, nothing is hidden or
reclassified, and interpretation is left to Grok.
"""
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
ACCOUNT_KINDS = {
    "CHECKING_ACCOUNT": "Conta corrente",
    "SAVINGS_ACCOUNT": "Poupança",
    "CREDIT_CARD": "Cartão de crédito",
}
UNCATEGORIZED = "Sem categoria"
# Pluggy categories that only move money between the user's own accounts or pay a card
# bill. They stay in every list and total; they are just also summed apart so Grok can
# avoid counting the same money twice. Matched case-insensitively as substrings.
INTERNAL_CATEGORIES = ("same person transfer", "credit card payment")


@dataclass
class Transaction:
    id: str
    account: str
    date: date
    description: str
    amount: float  # always positive; see `inflow`
    inflow: bool
    category: str
    internal: bool
    pending: bool
    installment: str | None  # e.g. "3/10" for card purchases in installments


def brl(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if value < 0 else ''}R$ {s}"


def signed_brl(value: float, inflow: bool) -> str:
    return f"{'+' if inflow else '-'}{brl(value)}"


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_PT[month - 1]}/{year}"


def account_label(account: dict[str, Any], banks: dict[str, str]) -> str:
    name = account.get("marketingName") or account.get("name") or account["id"]
    bank = banks.get(account.get("itemId", ""))
    return f"{bank} · {name}" if bank and bank.lower() not in name.lower() else name


def _parse_date(raw: str) -> date:
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt.astimezone(TZ).date() if dt.tzinfo else dt.date()


def _ddmm(raw: str | None) -> str | None:
    return _parse_date(raw).strftime("%d/%m") if raw else None


def _clean_description(raw: str | None) -> str:
    return re.sub(r"\s+", " ", raw or "").strip() or "(sem descrição)"


def _installment(raw: dict[str, Any]) -> str | None:
    meta = raw.get("creditCardMetadata") or {}
    number, total = meta.get("installmentNumber"), meta.get("totalInstallments")
    return f"{number}/{total}" if number and total and total > 1 else None


def normalize(
    raw_transactions: list[dict[str, Any]],
    accounts_by_id: dict[str, dict[str, Any]],
    banks: dict[str, str],
) -> list[Transaction]:
    """Convert raw Pluggy transactions, dropping only exact duplicates (same ID)."""
    seen: set[str] = set()
    result: list[Transaction] = []
    for raw in raw_transactions:
        if raw["id"] in seen:
            continue
        seen.add(raw["id"])
        amount = float(raw.get("amountInAccountCurrency") or raw["amount"])
        tx_type = raw.get("type")
        category = raw.get("category") or UNCATEGORIZED
        result.append(
            Transaction(
                id=raw["id"],
                account=account_label(accounts_by_id[raw["accountId"]], banks),
                date=_parse_date(raw["date"]),
                description=_clean_description(raw.get("description") or raw.get("descriptionRaw")),
                amount=abs(amount),
                inflow=tx_type == "CREDIT" if tx_type in ("CREDIT", "DEBIT") else amount > 0,
                category=category,
                internal=any(c in category.lower() for c in INTERNAL_CATEGORIES),
                pending=raw.get("status") == "PENDING",
                installment=_installment(raw),
            )
        )
    result.sort(key=lambda t: (t.date, t.account, t.description))
    return result


def _totals(transactions: list[Transaction]) -> dict[str, Any]:
    def total(txs, inflow):
        return round(sum(t.amount for t in txs if t.inflow == inflow), 2)

    internal = [t for t in transactions if t.internal]
    by_category: dict[str, list[float]] = defaultdict(list)
    for t in transactions:
        if not t.inflow and not t.internal:
            by_category[t.category].append(t.amount)
    categories = sorted(by_category.items(), key=lambda kv: sum(kv[1]), reverse=True)
    inflows, outflows = total(transactions, True), total(transactions, False)
    return {
        "count": len(transactions),
        "inflows": inflows,
        "outflows": outflows,
        "net": round(inflows - outflows, 2),
        "internal_inflows": total(internal, True),
        "internal_outflows": total(internal, False),
        "outflows_by_category": [
            {"category": c, "total": round(sum(v), 2), "count": len(v)} for c, v in categories
        ],
    }


def _account_summary(account: dict[str, Any], banks: dict[str, str]) -> dict[str, Any]:
    credit = account.get("creditData") or {}
    entry = {
        "name": account_label(account, banks),
        "kind": ACCOUNT_KINDS.get(account.get("subtype"), account.get("subtype") or account.get("type")),
        "is_credit": account.get("type") == "CREDIT",
        "balance": round(float(account.get("balance") or 0), 2),
    }
    if entry["is_credit"]:
        entry.update(
            credit_limit=credit.get("creditLimit"),
            available_limit=credit.get("availableCreditLimit"),
            minimum_payment=credit.get("minimumPayment"),
            close_date=_ddmm(credit.get("balanceCloseDate")),
            due_date=_ddmm(credit.get("balanceDueDate")),
        )
    return entry


def build_summary(
    accounts: list[dict[str, Any]],
    transactions: list[Transaction],
    today: date,
    banks: dict[str, str] | None = None,
) -> dict[str, Any]:
    banks = banks or {}
    current = [t for t in transactions if (t.date.year, t.date.month) == (today.year, today.month)]
    previous: dict[tuple[int, int], list[Transaction]] = defaultdict(list)
    for t in transactions:
        if (t.date.year, t.date.month) != (today.year, today.month):
            previous[(t.date.year, t.date.month)].append(t)

    return {
        "period": month_label(today.year, today.month),
        "period_start": today.replace(day=1).isoformat(),
        "generated_on": today.isoformat(),
        "accounts": [_account_summary(a, banks) for a in accounts],
        "current_month": _totals(current),
        "transactions": [
            {
                "date": t.date.isoformat(),
                "account": t.account,
                "description": t.description,
                "amount": round(t.amount, 2),
                "direction": "in" if t.inflow else "out",
                "category": t.category,
                "internal": t.internal,
                "pending": t.pending,
                "installment": t.installment,
            }
            for t in current
        ],
        "previous_months": [
            {"period": month_label(y, m), **_totals(txs)}
            for (y, m), txs in sorted(previous.items(), reverse=True)
        ],
    }


READING_NOTES = [
    "Dados extraídos automaticamente via Open Finance (Pluggy), sem nenhuma interpretação "
    "ou regra pessoal aplicada. A análise fica a cargo de quem lê.",
    "Valores em reais. Nas transações, \"+\" é dinheiro entrando na conta e \"-\" é dinheiro saindo.",
    "Saldo de conta corrente/poupança é o saldo atual informado pelo banco. Em cartão de "
    "crédito, o saldo é o valor da fatura em aberto.",
    "As categorias são a classificação automática da Pluggy (em inglês) e podem estar erradas; "
    "a descrição original do banco vem sempre junto.",
    "Todas as contas conectadas aparecem juntas. Dinheiro movido entre contas próprias aparece "
    "duas vezes: como saída numa conta e entrada na outra.",
    "Compras no cartão são saídas no cartão. O pagamento da fatura aparece de novo como saída "
    "na conta corrente (e como entrada no cartão). Somar os dois conta o mesmo gasto duas vezes.",
    "Transações marcadas [interna] têm categoria Pluggy de transferência entre contas do mesmo "
    "titular ou pagamento de fatura. Elas entram nos totais brutos e também são somadas à parte; "
    "\"Saídas por categoria\" as exclui.",
    "Saques em dinheiro e Pix/transferências para terceiros só dizem para onde o dinheiro saiu, "
    "não o que foi pago com ele.",
    "[pendente] = ainda não compensada pelo banco; o valor pode mudar. "
    "[parcela n/N] = compra parcelada no cartão.",
]


def _totals_lines(t: dict[str, Any]) -> list[str]:
    return [
        f"- Entradas: {brl(t['inflows'])}",
        f"- Saídas: {brl(t['outflows'])}",
        f"- Líquido: {brl(t['net'])}",
        f"- Das quais internas [interna]: entradas {brl(t['internal_inflows'])}, "
        f"saídas {brl(t['internal_outflows'])}",
    ]


def format_text(summary: dict[str, Any]) -> str:
    start = date.fromisoformat(summary["period_start"]).strftime("%d/%m")
    end = date.fromisoformat(summary["generated_on"]).strftime("%d/%m/%Y")
    lines = [f"=== DADOS FINANCEIROS - {summary['period']} ({start} a {end}) ===", "", "COMO LER ESTES DADOS"]
    lines += [f"- {note}" for note in READING_NOTES]

    lines += ["", "CONTAS"]
    for acc in summary["accounts"]:
        if acc["is_credit"]:
            parts = [f"fatura em aberto {brl(acc['balance'])}"]
            for key, label in (("credit_limit", "limite"), ("available_limit", "disponível"),
                               ("minimum_payment", "pagamento mínimo")):
                if acc.get(key) is not None:
                    parts.append(f"{label} {brl(acc[key])}")
            for key, label in (("close_date", "fechamento"), ("due_date", "vencimento")):
                if acc.get(key):
                    parts.append(f"{label} {acc[key]}")
            lines.append(f"- {acc['name']} ({acc['kind']}): " + " | ".join(parts))
        else:
            lines.append(f"- {acc['name']} ({acc['kind']}): saldo {brl(acc['balance'])}")

    cur = summary["current_month"]
    lines += ["", f"TOTAIS DO MÊS ({cur['count']} transações, valores brutos)"] + _totals_lines(cur)

    lines += ["", "SAÍDAS POR CATEGORIA (sem internas)"]
    for c in cur["outflows_by_category"] or [{"category": "(nenhuma saída)", "total": 0, "count": 0}]:
        lines.append(f"- {c['category']}: {brl(c['total'])} ({c['count']}x)")

    lines += ["", "TRANSAÇÕES DO MÊS (data | conta | valor | descrição | categoria Pluggy)"]
    for t in summary["transactions"]:
        tags = [label for flag, label in ((t["internal"], "interna"), (t["pending"], "pendente")) if flag]
        if t["installment"]:
            tags.append(f"parcela {t['installment']}")
        lines.append(
            f"{date.fromisoformat(t['date']).strftime('%d/%m')} | {t['account']} | "
            f"{signed_brl(t['amount'], t['direction'] == 'in')} | {t['description']} | {t['category']}"
            + "".join(f" [{tag}]" for tag in tags)
        )
    if not summary["transactions"]:
        lines.append("- nenhuma")

    for p in summary["previous_months"]:
        lines += ["", f"MÊS ANTERIOR - {p['period']} (só totais, {p['count']} transações)"] + _totals_lines(p)
        cats = p["outflows_by_category"]
        if cats:
            top = ", ".join(f"{c['category']} {brl(c['total'])}" for c in cats[: config.RECAP_CATEGORIES])
            rest = sum(c["total"] for c in cats[config.RECAP_CATEGORIES:])
            lines.append(f"- Saídas por categoria (sem internas): {top}" + (f", demais {brl(rest)}" if rest else ""))
    return "\n".join(lines) + "\n"
