import unittest
from datetime import date

from processor import brl, build_summary, format_text, normalize

BANKS = {"item-nu": "Nubank", "item-itau": "Itaú", "item-mp": "MeuPluggy"}
ACCOUNTS = [
    {"id": "acc-itau", "itemId": "item-itau", "type": "BANK", "subtype": "CHECKING_ACCOUNT",
     "name": "Conta Corrente", "balance": 2500.5},
    {"id": "acc-card", "itemId": "item-nu", "type": "CREDIT", "subtype": "CREDIT_CARD",
     "name": "Nubank Ultravioleta", "balance": 820.0,
     "creditData": {"creditLimit": 5000, "availableCreditLimit": 4180}},
    {"id": "acc-btg", "itemId": "item-mp", "type": "CREDIT", "subtype": "CREDIT_CARD",
     "name": "Cartão BTG BLACK", "balance": 100.0, "creditData": {}},
]


def tx(id, account, day, amount, type, description, category=None, **extra):
    return {"id": id, "accountId": account, "date": f"{day}T03:00:00.000Z", "amount": amount,
            "type": type, "description": description, "category": category, **extra}


def inst(n, total, purchase):
    return {"creditCardMetadata": {"installmentNumber": n, "totalInstallments": total,
                                   "purchaseDate": f"{purchase}T00:00:00.000Z"}}


RAW = [
    tx("1", "acc-itau", "2026-10-06", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
    tx("2", "acc-itau", "2026-10-08", -1800, "DEBIT", "SAQUE  AG   1234", "Cash withdrawal"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),  # same id: dropped
    tx("3b", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),  # 2nd identical purchase: kept
    tx("4p", "acc-card", "2026-09-12", 300, "DEBIT", "LOJA X 1/10", "Shopping", **inst(1, 10, "2026-09-12")),
    tx("4", "acc-card", "2026-10-12", 300, "DEBIT", "LOJA X 2/10", "Shopping", **inst(2, 10, "2026-09-12")),
    tx("5", "acc-itau", "2026-10-15", -900, "DEBIT", "Pagamento fatura", "Credit card payment"),
    tx("6", "acc-card", "2026-10-15", 900, "CREDIT", "Pagamento recebido", "Credit card payment"),
    tx("11", "acc-itau", "2026-10-18", -1000, "DEBIT", "Transf para poupança", "Same person transfer"),
    tx("7", "acc-itau", "2026-10-19", -50, "DEBIT", "Pix enviado", None, status="PENDING"),
    tx("12", "acc-btg", "2026-10-10", 20, "DEBIT", "Uber", "Taxi and ride-hailing"),
    tx("13", "acc-btg", "2026-09-20", 49.66, "DEBIT", "Vanezi 2/3", "Clothing", **inst(2, 3, "2026-08-02")),
    tx("8", "acc-itau", "2026-09-20", -300, "DEBIT", "Uber trip", "Transportation"),
    tx("9", "acc-itau", "2026-09-05", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
]


class ProcessorTest(unittest.TestCase):
    def setUp(self):
        self.txs = normalize(RAW, {a["id"]: a for a in ACCOUNTS}, BANKS)
        self.summary = build_summary(ACCOUNTS, self.txs, date(2026, 10, 20), BANKS)
        self.text = format_text(self.summary)

    def test_only_exact_duplicates_dropped(self):
        self.assertEqual(len(self.txs), 14)
        self.assertEqual(sum(t.description == "Padaria" for t in self.txs), 2)

    def test_cleans_without_reclassifying(self):
        saque = next(t for t in self.txs if t.id == "2")
        self.assertEqual((saque.description, saque.category), ("SAQUE AG 1234", "Cash withdrawal"))
        self.assertEqual(saque.account, "Itaú · Conta Corrente")
        self.assertEqual(next(t for t in self.txs if t.id == "12").account, "Cartão BTG BLACK")  # MeuPluggy hidden

    def test_cash_view_counts_card_when_paid(self):
        cur = self.summary["current_month"]
        self.assertEqual(cur["inflows"], 6000)
        self.assertEqual(cur["card_paid"], 900)
        self.assertEqual(cur["outflows"], 1800 + 50 + 900)  # no card purchases, no own transfers
        self.assertEqual(cur["net"], 3250)
        cats = {c["category"]: c["total"] for c in cur["outflows_by_category"]}
        self.assertEqual(cats, {"Cash withdrawal": 1800, "Pagamento de cartão": 900, "Sem categoria": 50})

    def test_card_purchases_are_detail(self):
        self.assertEqual(self.summary["card_purchases_total"], round(45.9 * 2 + 300 + 20, 2))
        self.assertIn("COMPRAS NO CARTÃO NO MÊS POR CATEGORIA (R$ 411,80; detalhe, não somado aos gastos)", self.text)
        self.assertIn("  - das quais pagamentos de cartão: R$ 900,00 (Nubank Ultravioleta R$ 900,00 em 15/10)",
                      self.text)

    def test_future_installments(self):
        future = self.summary["future_installments"]
        self.assertEqual(future["by_month"][0], {"period": "Outubro/2026 (ainda a lançar)", "total": 49.66})
        self.assertEqual(future["by_month"][1], {"period": "Novembro/2026", "total": 300})
        self.assertEqual(future["total"], 2449.66)
        loja = next(p for p in future["purchases"] if p["description"] == "LOJA X")
        self.assertEqual((loja["last_seen"], loja["remaining"], loja["ends"]), ("2/10", 8, "Junho/2027"))

    def test_transaction_lists_and_tags(self):
        self.assertIn("15/10 | Itaú · Conta Corrente | -R$ 900,00 | Pagamento fatura | Credit card payment [não somado]",
                      self.text)
        self.assertIn("| Pagamento recebido | Credit card payment [pagamento do cartão]", self.text)
        self.assertIn("| Transf para poupança | Same person transfer [não somado]", self.text)
        self.assertIn("| LOJA X 2/10 | Shopping [parcela 2/10]", self.text)
        self.assertIn("| Pix enviado | Sem categoria [pendente]", self.text)
        self.assertNotIn("fatura em aberto", self.text)
        self.assertNotIn("Uber trip", self.text)  # previous month: totals only

    def test_accounts(self):
        self.assertTrue(self.text.startswith("=== DADOS FINANCEIROS - Outubro/2026 (01/10 a 20/10/2026) ==="))
        self.assertIn("- Nubank Ultravioleta (Cartão de crédito): saldo devedor total R$ 820,00 "
                      "| limite R$ 5.000,00 | disponível R$ 4.180,00", self.text)

    def test_previous_month_recap(self):
        (prev,) = self.summary["previous_months"]
        self.assertEqual((prev["period"], prev["outflows"], prev["net"]), ("Setembro/2026", 300, 5700))

    def test_dates(self):
        from processor import _parse_date
        self.assertEqual(_parse_date("2026-09-01T00:00:00.000Z"), date(2026, 9, 1))  # date-only: no shift
        self.assertEqual(_parse_date("2026-09-01T02:30:00.000Z"), date(2026, 8, 31))  # real time, SP is UTC-3
        self.assertEqual(_parse_date("2026-09-01"), date(2026, 9, 1))

    def test_brl(self):
        self.assertEqual(brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(brl(-50), "-R$ 50,00")


if __name__ == "__main__":
    unittest.main()
