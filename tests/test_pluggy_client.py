import unittest
from datetime import date
from unittest import mock

from pluggy_client import PluggyClient


def response(payload, status=200):
    return mock.Mock(status_code=status, json=mock.Mock(return_value=payload), text="")


class TransactionsPaginationTest(unittest.TestCase):
    def test_follows_cursor_until_next_is_null(self):
        session = mock.Mock(headers={})
        session.post.return_value = response({"apiKey": "key"})
        session.get.side_effect = [
            response({"results": [{"id": "1"}], "next": "/v2/transactions?accountId=a&after=CUR%3D%3D"}),
            response({"results": [{"id": "2"}], "next": None}),
        ]
        with mock.patch("pluggy_client.requests.Session", return_value=session):
            client = PluggyClient("id", "secret")
            txs = client.get_transactions("a", date(2026, 9, 1), date(2026, 10, 20))

        self.assertEqual([t["id"] for t in txs], ["1", "2"])
        first, second = (call.kwargs["params"] for call in session.get.call_args_list)
        self.assertEqual(session.get.call_args_list[0].args[0], "https://api.pluggy.ai/v2/transactions")
        self.assertEqual(first, {"accountId": "a", "dateFrom": "2026-09-01", "dateTo": "2026-10-20"})
        self.assertNotIn("after", first)
        self.assertEqual(second["after"], "CUR==")


if __name__ == "__main__":
    unittest.main()
