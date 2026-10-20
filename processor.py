"""Turn raw Pluggy data into a neutral, Grok-readable report. No network access here.

Cash view: money counts in the month it leaves or enters a bank account. Card purchases
are listed as detail and count as spending only when the card is paid, for the amount
paid. No personal rules: categories are Pluggy's own and interpretation is left to Grok.
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
CARD_PAYMENT_LABEL = "Pagamento de cartão"
# Aggregator connectors that say nothing about the actual bank.
NON_BANK_CONNECTORS = ("meupluggy",)
# Pluggy categories (case-insensitive substrings).
SAME_OWNER_TRANSFER = "same person transfer"
CARD_PAYMENT = "credit card payment"
INSTALLMENT_SUFFIX = re.compile(r"\s*\d+\s*/\s*\d+\s*$")


@dataclass
class Transaction:
    id: str
    account: str
    on_card: bool
    date: date
    description: str
    amount: float  # always positive; see `inflow`
    inflow: bool
    category: str
    pending: bool
    installment_number: int | None
    total_installments: int | None
    purchase_date: date | None

    @property
    def is_card_payment(self) -> bool:
        return CARD_PAYMENT in self.category.lower()

    @property
    def is_same_owner_transfer(self) -> bool:
        return SAME_OWNER_TRANSFER in self.category.lower()

    @property
    def counted_payment(self) -> bool:
        """Card payment seen from the card side: the cash-view card spending."""
        return self.on_card and self.inflow and self.is_card_payment

    @property
    def not_counted(self) -> bool:
        """Account movement left out of the cash totals: own-account transfers, and card
        payments seen from the paying account (counted once, from the card side)."""
        return not self.on_card and (self.is_same_owner_transfer or self.is_card_payment)


def brl(value: float) -> str:
    s = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if value < 0 else ''}R$ {s}"


def signed_brl(value: float, inflow: bool) -> str:
    return f"{'+' if inflow else '-'}{brl(value)}"


def month_label(year: int, month: int) -> str:
    return f"{MONTHS_PT[month - 1]}/{year}"


def add_months(year: int, month: int, n: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + n
    return index // 12, index % 12 + 1


def account_label(account: dict[str, Any], banks: dict[str, str]) -> str:
    name = account.get("marketingName") or account.get("name") or account["id"]
    bank = banks.get(account.get("itemId", ""), "")
    if not bank or bank.lower() in NON_BANK_CONNECTORS or bank.lower() in name.lower():
        return name
    return f"{bank} · {name}"


def _parse_date(raw: str) -> date:
    """Pluggy sends real timestamps and date-only values (as midnight UTC) in the same fields.
    Only real timestamps are converted to São Paulo time; midnight UTC keeps its calendar date."""
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None or (dt.utcoffset().total_seconds() == 0 and dt.time() == datetime.min.time()):
        return dt.date()
    return dt.astimezone(TZ).date()


def _clean_description(raw: str | None) -> str:
    return re.sub(r"\s+", " ", raw or "").strip() or "(sem descrição)"


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
        account = accounts_by_id[raw["accountId"]]
        amount = float(raw.get("amountInAccountCurrency") or raw["amount"])
        tx_type = raw.get("type")
        meta = raw.get("creditCardMetadata") or {}
        total = meta.get("totalInstallments")
        result.append(
            Transaction(
                id=raw["id"],
                account=account_label(account, banks),
                on_card=account.get("type") == "CREDIT",
                date=_parse_date(raw["date"]),
                description=_clean_description(raw.get("description") or raw.get("descriptionRaw")),
                amount=abs(amount),
                inflow=tx_type == "CREDIT" if tx_type in ("CREDIT", "DEBIT") else amount > 0,
                category=raw.get("category") or UNCATEGORIZED,
                pending=raw.get("status") == "PENDING",
                installment_number=meta.get("installmentNumber") if total and total > 1 else None,
                total_installments=total if total and total > 1 else None,
                purchase_date=_parse_date(meta["purchaseDate"]) if meta.get("purchaseDate") else None,
            )
        )
    result.sort(key=lambda t: (t.date, t.account, t.description))
    return result


def _by_category(txs: list[Transaction]) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for t in txs:
        groups[t.category].append(t.amount)
    ordered = sorted(groups.items(), key=lambda kv: sum(kv[1]), reverse=True)
    return [{"category": c, "total": round(sum(v), 2), "count": len(v)} for c, v in ordered]


def _cash_totals(transactions: list[Transaction]) -> dict[str, Any]:
    account_txs = [t for t in transactions if not t.on_card and not t.not_counted]
    payments = [t for t in transactions if t.counted_payment]
    account_out = [t for t in account_txs if not t.inflow]
    inflows = round(sum(t.amount for t in account_txs if t.inflow), 2)
    card_paid = round(sum(t.amount for t in payments), 2)
    outflows = round(sum(t.amount for t in account_out) + card_paid, 2)
    categories = _by_category(account_out)
    if card_paid:
        categories.append({"category": CARD_PAYMENT_LABEL, "total": card_paid, "count": len(payments)})
        categories.sort(key=lambda c: c["total"], reverse=True)
    return {
        "inflows": inflows,
        "outflows": outflows,
        "net": round(inflows - outflows, 2),
        "card_payments": [
            {"date": t.date.isoformat(), "card": t.account, "amount": round(t.amount, 2)} for t in payments
        ],
        "card_paid": card_paid,
        "outflows_by_category": categories,
    }


def _card_purchases(transactions: list[Transaction]) -> list[Transaction]:
    return [t for t in transactions if t.on_card and not t.is_card_payment]


def _future_installments(transactions: list[Transaction], today: date) -> dict[str, Any]:
    """Installments still to be charged, from the latest installment seen of each purchase."""
    latest: dict[tuple, Transaction] = {}
    for t in transactions:
        if not (t.on_card and t.installment_number and t.total_installments) or t.inflow:
            continue
        key = (t.account, INSTALLMENT_SUFFIX.sub("", t.description).lower(), t.purchase_date, t.total_installments)
        if key not in latest or t.installment_number > latest[key].installment_number:
            latest[key] = t

    by_month: dict[tuple[int, int], float] = defaultdict(float)
    purchases = []
    for t in latest.values():
        remaining = t.total_installments - t.installment_number
        if remaining <= 0:
            continue
        for k in range(1, remaining + 1):
            ym = add_months(t.date.year, t.date.month, k)
            if ym >= (today.year, today.month):  # current month: installments not posted yet
                by_month[ym] += t.amount
        last = add_months(t.date.year, t.date.month, remaining)
        purchases.append({
            "description": INSTALLMENT_SUFFIX.sub("", t.description),
            "card": t.account,
            "installment_amount": round(t.amount, 2),
            "last_seen": f"{t.installment_number}/{t.total_installments}",
            "remaining": remaining,
            "remaining_total": round(t.amount * remaining, 2),
            "ends": month_label(*last),
        })
    purchases.sort(key=lambda p: p["remaining_total"], reverse=True)
    return {
        "by_month": [
            {"period": month_label(y, m) + (" (ainda a lançar)" if (y, m) == (today.year, today.month) else ""),
             "total": round(v, 2)}
            for (y, m), v in sorted(by_month.items())
        ],
        "total": round(sum(by_month.values()), 2),
        "purchases": purchases,
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
        entry.update(credit_limit=credit.get("creditLimit"), available_limit=credit.get("availableCreditLimit"))
    return entry


def _tx_dict(t: Transaction) -> dict[str, Any]:
    return {
        "date": t.date.isoformat(),
        "account": t.account,
        "description": t.description,
        "amount": round(t.amount, 2),
        "direction": "in" if t.inflow else "out",
        "category": t.category,
        "pending": t.pending,
        "installment": f"{t.installment_number}/{t.total_installments}" if t.installment_number else None,
        "not_counted": t.not_counted,
        "card_payment": t.counted_payment,
    }


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
    purchases = _card_purchases(current)

    return {
        "period": month_label(today.year, today.month),
        "period_start": today.replace(day=1).isoformat(),
        "generated_on": today.isoformat(),
        "accounts": [_account_summary(a, banks) for a in accounts],
        "current_month": _cash_totals(current),
        "card_purchases_by_category": _by_category([t for t in purchases if not t.inflow]),
        "card_purchases_total": round(sum(t.amount for t in purchases if not t.inflow), 2),
        "future_installments": _future_installments(transactions, today),
        "account_transactions": [_tx_dict(t) for t in current if not t.on_card],
        "card_transactions": [_tx_dict(t) for t in current if t.on_card],
        "previous_months": [
            {"period": month_label(y, m), **_cash_totals(txs)}
            for (y, m), txs in sorted(previous.items(), reverse=True)
        ],
    }


READING_NOTES = [
    "Dados extraídos automaticamente via Open Finance (Pluggy), sem nenhuma interpretação "
    "ou regra pessoal aplicada. A análise fica a cargo de quem lê.",
    "Visão de caixa: um gasto conta no mês em que o dinheiro sai da conta. Compras no cartão "
    "só entram nos gastos quando o cartão é pago, pelo valor pago, no mês do pagamento. As "
    "compras do cartão aparecem à parte, como detalhe, e não são somadas aos gastos.",
    "Valores em reais. Nas transações, \"+\" é dinheiro entrando e \"-\" é dinheiro saindo.",
    "Saldo de conta é o saldo atual informado pelo banco. No cartão, \"saldo devedor total\" é tudo "
    "o que ainda será pago, incluindo compras recentes e parcelas futuras.",
    "Transferências entre contas do mesmo titular e pagamentos de cartão vistos pela conta que "
    "pagou são marcados [não somado]: o pagamento de cartão já é contado pelo lado do cartão "
    "([pagamento do cartão]). Transferências que a Pluggy não reconhecer como do mesmo titular "
    "contam como entrada/saída normal.",
    "As categorias são a classificação automática da Pluggy (em inglês) e podem estar erradas; "
    "a descrição original do banco vem sempre junto.",
    "Saques em dinheiro e Pix/transferências para terceiros só dizem para onde o dinheiro saiu, "
    "não o que foi pago com ele.",
    "A previsão de gastos futuros só inclui parcelas que o banco informa. Alguns bancos não "
    "enviam compras parceladas pelo Open Finance; nesses cartões, os valores reais serão maiores.",
    "[pendente] = ainda não compensada pelo banco; o valor pode mudar. "
    "[parcela n/N] = compra parcelada no cartão.",
]


def _cash_lines(t: dict[str, Any]) -> list[str]:
    lines = [f"- Entradas: {brl(t['inflows'])}", f"- Saídas: {brl(t['outflows'])}"]
    if t["card_payments"]:
        detail = "; ".join(
            f"{p['card']} {brl(p['amount'])} em {date.fromisoformat(p['date']).strftime('%d/%m')}"
            for p in t["card_payments"]
        )
        lines.append(f"  - das quais pagamentos de cartão: {brl(t['card_paid'])} ({detail})")
    lines.append(f"- Líquido: {brl(t['net'])}")
    return lines


def _category_lines(categories: list[dict[str, Any]]) -> list[str]:
    if not categories:
        return ["- nenhuma"]
    return [f"- {c['category']}: {brl(c['total'])} ({c['count']}x)" for c in categories]


def _tx_lines(txs: list[dict[str, Any]]) -> list[str]:
    if not txs:
        return ["- nenhuma"]
    lines = []
    for t in txs:
        tags = [label for flag, label in ((t["not_counted"], "não somado"), (t["card_payment"], "pagamento do cartão"),
                                          (t["pending"], "pendente")) if flag]
        if t["installment"]:
            tags.append(f"parcela {t['installment']}")
        lines.append(
            f"{date.fromisoformat(t['date']).strftime('%d/%m')} | {t['account']} | "
            f"{signed_brl(t['amount'], t['direction'] == 'in')} | {t['description']} | {t['category']}"
            + "".join(f" [{tag}]" for tag in tags)
        )
    return lines


def format_text(summary: dict[str, Any]) -> str:
    start = date.fromisoformat(summary["period_start"]).strftime("%d/%m")
    end = date.fromisoformat(summary["generated_on"]).strftime("%d/%m/%Y")
    lines = [f"=== DADOS FINANCEIROS - {summary['period']} ({start} a {end}) ===", "", "COMO LER ESTES DADOS"]
    lines += [f"- {note}" for note in READING_NOTES]

    lines += ["", "CONTAS"]
    for acc in summary["accounts"]:
        if acc["is_credit"]:
            parts = [f"saldo devedor total {brl(acc['balance'])}"]
            for key, label in (("credit_limit", "limite"), ("available_limit", "disponível")):
                if acc.get(key) is not None:
                    parts.append(f"{label} {brl(acc[key])}")
            lines.append(f"- {acc['name']} ({acc['kind']}): " + " | ".join(parts))
        else:
            lines.append(f"- {acc['name']} ({acc['kind']}): saldo {brl(acc['balance'])}")

    lines += ["", "GASTOS DO MÊS (visão de caixa)"] + _cash_lines(summary["current_month"])
    lines += ["", "SAÍDAS DO MÊS POR CATEGORIA"] + _category_lines(summary["current_month"]["outflows_by_category"])
    lines += ["", f"COMPRAS NO CARTÃO NO MÊS POR CATEGORIA ({brl(summary['card_purchases_total'])}; "
                  "detalhe, não somado aos gastos)"]
    lines += _category_lines(summary["card_purchases_by_category"])

    future = summary["future_installments"]
    lines += ["", "PREVISÃO DE GASTOS FUTUROS (parcelas informadas pelos bancos)"]
    if future["purchases"]:
        lines += [f"- {m['period']}: {brl(m['total'])}" for m in future["by_month"]]
        lines.append(f"- Total a vencer: {brl(future['total'])}")
        lines.append("- Compras parceladas:")
        lines += [
            f"  - {p['description']} ({p['card']}): {brl(p['installment_amount'])}/mês, última vista "
            f"{p['last_seen']}, faltam {p['remaining']} ({brl(p['remaining_total'])}), termina {p['ends']}"
            for p in future["purchases"]
        ]
    else:
        lines.append("- nenhuma parcela futura informada")

    lines += ["", "MOVIMENTAÇÕES EM CONTA DO MÊS (data | conta | valor | descrição | categoria Pluggy)"]
    lines += _tx_lines(summary["account_transactions"])
    lines += ["", "LANÇAMENTOS NO CARTÃO DO MÊS (data | cartão | valor | descrição | categoria Pluggy)"]
    lines += _tx_lines(summary["card_transactions"])

    for p in summary["previous_months"]:
        lines += ["", f"MÊS ANTERIOR - {p['period']} (só totais, visão de caixa)"] + _cash_lines(p)
        cats = p["outflows_by_category"]
        if cats:
            top = ", ".join(f"{c['category']} {brl(c['total'])}" for c in cats[: config.RECAP_CATEGORIES])
            rest = sum(c["total"] for c in cats[config.RECAP_CATEGORIES:])
            lines.append(f"- Saídas por categoria: {top}" + (f", demais {brl(rest)}" if rest else ""))
    return "\n".join(lines) + "\n"
