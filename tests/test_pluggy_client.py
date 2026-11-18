import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations import pluggy_client


class PluggyClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.accounts_file = Path(self.temp_dir.name) / "contas.json"
        self.accounts_file_patch = patch.object(
            pluggy_client, "ACCOUNTS_FILE", self.accounts_file
        )
        self.accounts_file_patch.start()
        pluggy_client._api_key = None
        pluggy_client._api_key_expires_at = 0.0

    def tearDown(self) -> None:
        self.accounts_file_patch.stop()
        self.temp_dir.cleanup()

    def write_accounts(self, accounts: dict[str, object]) -> None:
        self.accounts_file.write_text(json.dumps(accounts), encoding="utf-8")

    def test_api_key_is_cached(self) -> None:
        settings = SimpleNamespace(
            pluggy_client_id="client-id",
            pluggy_client_secret="client-secret",
        )
        response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"apiKey": "server-only-key"},
            status_code=200,
        )
        with (
            patch.object(pluggy_client, "get_settings", return_value=settings),
            patch.object(pluggy_client.requests, "post", return_value=response) as post,
        ):
            self.assertEqual(pluggy_client.get_api_key(), "server-only-key")
            self.assertEqual(pluggy_client.get_api_key(), "server-only-key")
        post.assert_called_once()

    def test_accounts_use_local_json_without_calling_accounts_api(self) -> None:
        self.write_accounts(
            {
                "banco": {
                    "BANK": {
                        "id": "bank-account",
                        "itemId": "item-1",
                        "type": "BANK",
                        "name": "Conta corrente",
                        "balance": 125.5,
                        "currencyCode": "BRL",
                        "owner": "Private Name",
                        "number": "1234-5",
                    },
                    "CREDIT": {
                        "id": "credit-account",
                        "itemId": "item-1",
                        "type": "CREDIT",
                        "name": "Cartão",
                        "balance": 50,
                        "currencyCode": "BRL",
                    },
                }
            }
        )
        with patch.object(pluggy_client, "_get_all_results") as get_all_results:
            accounts = pluggy_client.get_accounts("BANK")

        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0]["id"], "bank-account")
        self.assertEqual(accounts[0]["institution"], "banco")
        self.assertEqual(accounts[0]["balance"], 125.5)
        self.assertNotIn("owner", accounts[0])
        self.assertNotIn("number", accounts[0])
        get_all_results.assert_not_called()

    def test_accounts_snapshot_timestamp_comes_from_local_json_file(self) -> None:
        self.write_accounts({"banco": {}})

        timestamp = pluggy_client.get_accounts_snapshot_timestamp()

        self.assertIsNotNone(timestamp)
        self.assertTrue(timestamp.endswith("+00:00"))

    def test_past_invoices_use_local_account_ids_without_loading_accounts(self) -> None:
        self.write_accounts(
            {
                "banco": {
                    "CREDIT": {
                        "id": "credit-account",
                        "itemId": "item-1",
                        "type": "CREDIT",
                        "name": "Cartão",
                        "balance": 50,
                    }
                }
            }
        )
        with patch.object(
            pluggy_client, "_get_all_results", return_value=[]
        ) as get_all_results:
            result = pluggy_client.get_past_invoices()

        self.assertEqual(result, {"PastInvoices": []})
        get_all_results.assert_called_once_with("/bills", {"accountId": "credit-account"})

    def test_summary_deducts_credit_card_debt_from_net_worth(self) -> None:
        accounts = [
            {"type": "BANK", "balance": 100.0, "currencyCode": "BRL"},
            {"type": "INVESTMENT", "balance": 200.0, "currencyCode": "BRL"},
            {"type": "BANK", "balance": 500.0, "currencyCode": "USD"},
            {"type": "CREDIT", "balance": 30.0, "currencyCode": "BRL"},
        ]
        with patch.object(pluggy_client, "get_accounts", return_value=accounts):
            summary = pluggy_client.get_dashboard_summary()

        self.assertEqual(summary, {"totalBalance": 270.0, "bankBalance": 100.0})

    def test_monthly_card_expenses_sum_installment_amount_not_full_purchase(self) -> None:
        self.write_accounts(
            {
                "banco": {
                    "CREDIT": {
                        "id": "credit-account",
                        "itemId": "item-1",
                        "type": "CREDIT",
                        "name": "Cartão",
                        "balance": 0,
                    }
                }
            }
        )
        transactions = [
            {
                "amount": 159.2,
                "currencyCode": "BRL",
                "date": "2026-10-14T00:00:00Z",
                "creditCardMetadata": {
                    "totalAmount": 320,
                    "totalInstallments": 2,
                    "installmentNumber": 2,
                    "billForecastDate": "2026-10",
                    "paymentType": "INSTALLMENT",
                },
            },
            {
                "amount": 40,
                "currencyCode": "BRL",
                "date": "2026-10-20T00:00:00Z",
            },
            {
                "amount": -120,
                "currencyCode": "BRL",
                "date": "2026-10-21T00:00:00Z",
                "type": "CREDIT",
            },
        ]
        with patch.object(
            pluggy_client, "_get_all_transactions", return_value=transactions
        ) as get_all_transactions:
            result = pluggy_client.get_monthly_credit_expenses()

        self.assertEqual(
            result,
            {
                "MonthlyExpenses": [
                    {"month": "2026-10", "amount": 199.2, "currencyCode": "BRL"}
                ]
            },
        )
        get_all_transactions.assert_called_once_with("credit-account")

    def test_transaction_history_returns_all_records_in_cursor_page_sorted(self) -> None:
        transactions = [
            {
                "date": f"{date(2026, 1, 1) + timedelta(days=day - 1)}T00:00:00Z",
                "amount": -day,
                "description": str(day),
            }
            for day in range(1, 103)
        ]
        with (
            patch.object(
                pluggy_client,
                "get_accounts",
                return_value=[{"id": "account-1"}],
            ),
            patch.object(
                pluggy_client,
                "_get_transaction_page",
                return_value=(transactions, None),
            ),
        ):
            result = pluggy_client.get_transaction_history("account-1")

        history = result["TransactionHistory"]
        self.assertEqual(len(history), 102)
        self.assertEqual(history[0]["date"], "2026-04-12T00:00:00Z")
        self.assertEqual(history[-1]["date"], "2026-01-01T00:00:00Z")
        self.assertIsNone(result["nextCursor"])

    def test_pagination_collects_all_pages(self) -> None:
        page_one = {"results": [{"id": "one"}], "totalPages": 2}
        page_two = {"results": [{"id": "two"}], "totalPages": 2}
        with patch.object(
            pluggy_client, "_request", side_effect=[page_one, page_two]
        ) as request:
            results = pluggy_client._get_all_results("/accounts", {"itemId": "item-1"})

        self.assertEqual([result["id"] for result in results], ["one", "two"])
        self.assertEqual(request.call_args_list[0].kwargs["params"]["page"], 1)
        self.assertEqual(request.call_args_list[1].kwargs["params"]["page"], 2)

    def test_transaction_cursor_pagination_uses_v2_endpoint(self) -> None:
        first_page = {
            "results": [{"id": "one"}],
            "next": "?accountId=account-1&after=cursor-1",
        }
        second_page = {"results": [{"id": "two"}], "next": None}
        with patch.object(
            pluggy_client, "_request", side_effect=[first_page, second_page]
        ) as request:
            transactions = pluggy_client._get_all_transactions("account-1")

        self.assertEqual([transaction["id"] for transaction in transactions], ["one", "two"])
        self.assertEqual(request.call_args_list[0].args, ("GET", "/v2/transactions"))
        self.assertEqual(
            request.call_args_list[0].kwargs["params"], {"accountId": "account-1"}
        )
        self.assertEqual(
            request.call_args_list[1].kwargs["params"],
            {"accountId": "account-1", "after": "cursor-1"},
        )

    def test_transaction_history_returns_one_api_page_and_next_cursor(self) -> None:
        page = [
            {
                "id": "transaction-1",
                "accountId": "account-1",
                "currencyCode": "BRL",
                "amount": -15.5,
                "date": "2026-10-10T00:00:00Z",
                "description": "Compra",
                "category": "Compras",
                "type": "DEBIT",
            }
        ]
        with (
            patch.object(
                pluggy_client,
                "get_accounts",
                return_value=[{"id": "account-1"}],
            ),
            patch.object(
                pluggy_client,
                "_get_transaction_page",
                return_value=(page, "next-cursor"),
            ) as get_page,
        ):
            result = pluggy_client.get_transaction_history("account-1", "current-cursor")

        self.assertEqual(result["nextCursor"], "next-cursor")
        self.assertEqual(result["TransactionHistory"][0]["id"], "transaction-1")
        self.assertEqual(result["TransactionHistory"][0]["type"], "DEBIT")
        get_page.assert_called_once_with("account-1", "current-cursor")


if __name__ == "__main__":
    unittest.main()
