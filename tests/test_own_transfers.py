import unittest
from datetime import date

from processor import build_summary, format_text, normalize

ACCOUNTS = [
    {"id": "a", "itemId": "i", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "Conta A", "balance": 0},
    {"id": "b", "itemId": "i", "type": "BANK", "subtype": "CHECKING_ACCOUNT", "name": "Conta B", "balance": 0},
    {"id": "card", "itemId": "i", "type": "CREDIT", "subtype": "CREDIT_CARD", "name": "Cartão", "balance": 0},
]


def tx(id, account, day, amount, description, category="Transfers"):
    return {"id": id, "accountId": account, "date": f"{day}T15:00:00.000Z", "amount": amount,
            "type": "CREDIT" if amount > 0 else "DEBIT", "description": description, "category": category}


RAW = [
    tx("out", "a", "2026-10-10", -500, "Pix para conta B"),
    tx("in", "b", "2026-10-11", 500, "Pix recebido de conta A"),        # pairs with "out" (1 day apart)
    tx("late", "b", "2026-10-15", 500, "Pix recebido"),                 # same amount, too late: kept
    tx("same-acc", "a", "2026-10-12", 200, "Estorno"),                  # same account as an outflow below
    tx("same-acc-out", "a", "2026-10-12", -200, "Compra"),               # same account: never paired
    tx("salary", "b", "2026-10-06", 3000, "Salário", "Salary"),
    tx("bill", "a", "2026-10-16", -700, "Pagamento de fatura"),          # bank calls it Transfers
    tx("bill-card", "card", "2026-10-17", 700, "Pagamento recebido", "Credit card payment"),
    tx("rdb", "b", "2026-10-07", -1000, "Aplicação RDB", "Investments"),
]


class OwnTransferMatchingTest(unittest.TestCase):
    def setUp(self):
        self.txs = {t.id: t for t in normalize(RAW, {a["id"]: a for a in ACCOUNTS}, {})}
        self.summary = build_summary(ACCOUNTS, list(self.txs.values()), date(2026, 10, 20))

    def test_pairs_only_cross_account_same_amount_within_a_day(self):
        matched = {i for i, t in self.txs.items() if t.matched_transfer}
        self.assertEqual(matched, {"out", "in"})

    def test_pairs_left_out_of_totals_and_reported(self):
        cur = self.summary["current_month"]
        self.assertEqual(cur["inflows"], 500 + 200 + 3000)
        self.assertEqual(cur["outflows"], 200 + 1000 + 700)  # card paid once, from the card side
        self.assertEqual(cur["investments"], 1000)
        self.assertEqual((cur["own_transfers"], cur["own_transfers_count"]), (500, 1))
        text = format_text(self.summary)
        self.assertIn("- Não somado: R$ 500,00 em 1 transferência entre contas próprias", text)
        self.assertIn("| Pix para conta B | Transfers [provável transferência entre contas próprias]", text)
        self.assertIn("| Pagamento de fatura | Transfers [pagamento de cartão, já contado no cartão]", text)
        self.assertIn("  - das quais aplicações em investimentos (categoria Pluggy): R$ 1.000,00", text)


if __name__ == "__main__":
    unittest.main()
