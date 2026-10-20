import unittest
from datetime import date

from processor import brl, build_summary, format_text, normalize

ACCOUNTS = [
    {"id": "acc-nu", "type": "BANK", "name": "Conta", "marketingName": "Nubank Conta", "balance": 2500.5},
    {
        "id": "acc-card",
        "type": "CREDIT",
        "name": "Nubank Cartão",
        "balance": 820.0,
        "creditData": {"creditLimit": 5000, "availableCreditLimit": 4180},
    },
]


def tx(id, account, day, amount, type, description, category=None):
    return {
        "id": id,
        "accountId": account,
        "date": f"{day}T03:00:00.000Z",
        "amount": amount,
        "type": type,
        "description": description,
        "category": category,
    }


RAW = [
    tx("1", "acc-nu", "2026-10-05", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
    tx("2", "acc-nu", "2026-10-10", -1800, "DEBIT", "Pix  ALUGUEL   Outubro", "Transfers"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "IFOOD *Restaurante", "Food delivery"),
    tx("3", "acc-card", "2026-10-11", 45.9, "DEBIT", "IFOOD *Restaurante", "Food delivery"),  # same id
    tx("3b", "acc-card", "2026-10-11", 45.9, "DEBIT", "IFOOD *Restaurante", "Food delivery"),  # same movement
    tx("4", "acc-card", "2026-10-12", 30, "DEBIT", "Padaria", "Food and drinks"),
    tx("5", "acc-card", "2026-10-13", 25, "DEBIT", "Lanche", "Food and drinks"),
    tx("6", "acc-card", "2026-10-14", 210, "DEBIT", "Restaurante caro", "Food and drinks"),
    tx("7", "acc-nu", "2026-10-15", -900, "DEBIT", "Pagamento fatura", "Credit card payment"),
    tx("8", "acc-nu", "2026-09-20", -300, "DEBIT", "Uber trip", "Transportation"),
    tx("9", "acc-nu", "2026-09-05", 6000, "CREDIT", "SALARIO EMPRESA", "Salary"),
]


class ProcessorTest(unittest.TestCase):
    def setUp(self):
        self.txs = normalize(RAW, {a["id"]: a for a in ACCOUNTS})
        self.summary = build_summary(ACCOUNTS, self.txs, date(2026, 10, 20))

    def test_dedupes_and_cleans(self):
        self.assertEqual(len(self.txs), 9)
        aluguel = next(t for t in self.txs if t.id == "2")
        self.assertEqual(aluguel.description, "Pix ALUGUEL Outubro")
        self.assertEqual(aluguel.category, "Moradia")  # keyword rule beats Pluggy category
        self.assertFalse(aluguel.inflow)
        self.assertEqual(aluguel.amount, 1800)

    def test_current_month_totals_ignore_card_payment(self):
        cur = self.summary["current_month"]
        self.assertEqual(cur["inflows"], 6000)
        self.assertEqual(cur["outflows"], 1800 + 45.9 + 30 + 25 + 210)
        self.assertEqual(cur["top_categories"][0], {"category": "Moradia", "total": 1800})

    def test_atypical(self):
        flagged = [t["description"] for t in self.summary["atypical"]]
        self.assertIn("Pix ALUGUEL Outubro", flagged)  # above fixed threshold
        self.assertIn("Restaurante caro", flagged)  # 3x the category average
        self.assertNotIn("Pagamento fatura", flagged)

    def test_previous_month_recap(self):
        (prev,) = self.summary["previous_months"]
        self.assertEqual(prev["period"], "Setembro/2026")
        self.assertEqual(prev["net"], 5700)

    def test_text_format(self):
        text = format_text(self.summary)
        self.assertTrue(text.startswith("=== RESUMO FINANCEIRO - Outubro/2026 ==="))
        self.assertIn("- Nubank Conta: R$ 2.500,50", text)
        self.assertIn("limite disponível R$ 4.180,00", text)
        self.assertIn("Limite cartão Nubank Cartão: R$ 5.000", text)

    def test_brl(self):
        self.assertEqual(brl(1234567.891), "R$ 1.234.567,89")
        self.assertEqual(brl(-50), "-R$ 50,00")


if __name__ == "__main__":
    unittest.main()
