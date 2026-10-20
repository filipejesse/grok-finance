import unittest
from datetime import date

from processor import brl, build_summary, format_text, normalize

BANKS = {"item-nu": "Nubank", "item-itau": "Itaú"}
ACCOUNTS = [
    {"id": "acc-itau", "itemId": "item-itau", "type": "BANK", "subtype": "CHECKING_ACCOUNT",
     "name": "Conta Corrente", "balance": 2500.5},
    {"id": "acc-card", "itemId": "item-nu", "type": "CREDIT", "subtype": "CREDIT_CARD",
     "name": "Nubank Ultravioleta", "balance": 820.0,
     "creditData": {"creditLimit": 5000, "availableCreditLimit": 4180,
                    "balanceDueDate": "2026-11-15T03:00:00.000Z"}},
]


def tx(id, account, day, amount, type, description, category=None, **extra):
    return {"id": id, "accountId": account, "date": f"{day}T03:00:00.000Z", "amount": amount,
            "type": type, "description": description, "category": category, **extra}


RAW = [
    tx("1", "acc-itau", "2026-10-06", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
    tx("2", "acc-itau", "2026-10-08", -1800, "DEBIT", "SAQUE  AG   1234", "Cash withdrawal"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),  # same id: dropped
    tx("3b", "acc-card", "2026-10-11", 45.9, "DEBIT", "Padaria", "Food and drinks"),  # 2nd identical purchase: kept
    tx("4", "acc-card", "2026-10-12", 300, "DEBIT", "LOJA X", "Shopping",
       creditCardMetadata={"installmentNumber": 2, "totalInstallments": 10}),
    tx("5", "acc-itau", "2026-10-15", -900, "DEBIT", "Pagamento fatura", "Credit card payment"),
    tx("6", "acc-card", "2026-10-15", 900, "CREDIT", "Pagamento recebido", "Credit card payment"),
    tx("7", "acc-itau", "2026-10-19", -50, "DEBIT", "Pix enviado", None, status="PENDING"),
    tx("8", "acc-itau", "2026-09-20", -300, "DEBIT", "Uber trip", "Transportation"),
    tx("9", "acc-itau", "2026-09-05", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
]


class ProcessorTest(unittest.TestCase):
    def setUp(self):
        self.txs = normalize(RAW, {a["id"]: a for a in ACCOUNTS}, BANKS)
        self.summary = build_summary(ACCOUNTS, self.txs, date(2026, 10, 20), BANKS)
        self.text = format_text(self.summary)

    def test_only_exact_duplicates_dropped(self):
        self.assertEqual(len(self.txs), 10)
        self.assertEqual(sum(t.description == "Padaria" for t in self.txs), 2)

    def test_cleans_without_reclassifying(self):
        saque = next(t for t in self.txs if t.id == "2")
        self.assertEqual(saque.description, "SAQUE AG 1234")
        self.assertEqual(saque.category, "Cash withdrawal")
        self.assertEqual(saque.account, "Itaú · Conta Corrente")
        self.assertFalse(saque.inflow)

    def test_gross_totals_with_internal_split_out(self):
        cur = self.summary["current_month"]
        self.assertEqual(cur["inflows"], 6900)
        self.assertEqual(cur["outflows"], round(1800 + 45.9 * 2 + 300 + 900 + 50, 2))
        self.assertEqual((cur["internal_inflows"], cur["internal_outflows"]), (900, 900))
        cats = {c["category"]: c for c in cur["outflows_by_category"]}
        self.assertNotIn("Credit card payment", cats)
        self.assertEqual(cats["Food and drinks"]["count"], 2)
        self.assertEqual(cats["Sem categoria"]["total"], 50)

    def test_every_current_transaction_listed_with_tags(self):
        self.assertEqual(len(self.summary["transactions"]), 8)
        self.assertIn("08/10 | Itaú · Conta Corrente | -R$ 1.800,00 | SAQUE AG 1234 | Cash withdrawal", self.text)
        self.assertIn("| LOJA X | Shopping [parcela 2/10]", self.text)
        self.assertIn("| Pagamento fatura | Credit card payment [interna]", self.text)
        self.assertIn("| Pix enviado | Sem categoria [pendente]", self.text)
        self.assertNotIn("Uber trip", self.text)  # previous month: totals only

    def test_accounts_and_reading_notes(self):
        self.assertTrue(self.text.startswith("=== DADOS FINANCEIROS - Outubro/2026 (01/10 a 20/10/2026) ==="))
        self.assertIn("COMO LER ESTES DADOS", self.text)
        self.assertIn("- Itaú · Conta Corrente (Conta corrente): saldo R$ 2.500,50", self.text)
        self.assertIn("- Nubank Ultravioleta (Cartão de crédito): fatura em aberto R$ 820,00 | limite R$ 5.000,00 "
                      "| disponível R$ 4.180,00 | vencimento 15/11", self.text)

    def test_previous_month_recap(self):
        (prev,) = self.summary["previous_months"]
        self.assertEqual((prev["period"], prev["net"]), ("Setembro/2026", 5700))
        self.assertIn("MÊS ANTERIOR - Setembro/2026 (só totais, 2 transações)", self.text)

    def test_brl(self):
        self.assertEqual(brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(brl(-50), "-R$ 50,00")


if __name__ == "__main__":
    unittest.main()
