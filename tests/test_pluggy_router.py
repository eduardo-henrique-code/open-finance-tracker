import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app


class PluggyRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("app.routers.pluggy.get_accounts")
    def test_accounts_response_includes_account_list_and_summary(
        self, get_accounts: MagicMock
    ) -> None:
        get_accounts.return_value = [
            {"id": "bank-1", "type": "BANK", "balance": 120.5, "currencyCode": "BRL"},
            {
                "id": "investment-1",
                "type": "INVESTMENT",
                "balance": 300.0,
                "currencyCode": "BRL",
            },
            {"id": "bank-2", "type": "BANK", "balance": 500.0, "currencyCode": "USD"},
            {"id": "credit-1", "type": "CREDIT", "balance": 75.0, "currencyCode": "BRL"},
        ]

        response = self.client.get("/routers/pluggy/get_accounts")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["totalBalance"], 345.5)
        self.assertEqual(response.json()["bankBalance"], 120.5)
        self.assertEqual(len(response.json()["Accounts"]), 4)

    @patch("app.routers.pluggy.get_transaction_history")
    def test_transaction_history_uses_the_selected_account_id(
        self, get_history: MagicMock
    ) -> None:
        get_history.return_value = {"TransactionHistory": [], "nextCursor": "next"}

        response = self.client.get(
            "/routers/pluggy/get_transaction_history",
            params={"accountId": "account-1", "after": "cursor-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["nextCursor"], "next")
        get_history.assert_called_once_with("account-1", "cursor-1")


if __name__ == "__main__":
    unittest.main()
