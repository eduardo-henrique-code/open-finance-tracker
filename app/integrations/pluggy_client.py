import json
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from app.core.config import PROJECT_ROOT, get_settings

PLUGGY_API_URL = "https://api.pluggy.ai"
ACCOUNTS_FILE = PROJECT_ROOT / "contas.json"
API_KEY_TTL_SECONDS = 115 * 60
PAGE_SIZE = 500
REQUEST_TIMEOUT_SECONDS = 15

_api_key: str | None = None
_api_key_expires_at = 0.0
_api_key_lock = Lock()


class PluggyAPIError(RuntimeError):
    """Raised when Pluggy cannot fulfill an API request."""


def _raise_for_response(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        status = response.status_code
        raise PluggyAPIError(f"Pluggy API request failed (HTTP {status}).") from exc


def get_api_key() -> str:
    global _api_key, _api_key_expires_at

    with _api_key_lock:
        if _api_key and time.monotonic() < _api_key_expires_at:
            return _api_key

        settings = get_settings()
        try:
            response = requests.post(
                f"{PLUGGY_API_URL}/auth",
                json={
                    "clientId": settings.pluggy_client_id,
                    "clientSecret": settings.pluggy_client_secret,
                },
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_response(response)
            payload = response.json()
        except requests.RequestException as exc:
            raise PluggyAPIError("Could not authenticate with Pluggy.") from exc
        except ValueError as exc:
            raise PluggyAPIError("Pluggy returned an invalid authentication response.") from exc

        api_key = payload.get("apiKey") if isinstance(payload, dict) else None
        if not isinstance(api_key, str) or not api_key:
            raise PluggyAPIError("Pluggy authentication response did not contain an API key.")

        _api_key = api_key
        _api_key_expires_at = time.monotonic() + API_KEY_TTL_SECONDS
        return api_key


def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    try:
        response = requests.request(
            method,
            f"{PLUGGY_API_URL}{path}",
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": get_api_key(),
            },
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        _raise_for_response(response)
        return response.json()
    except PluggyAPIError:
        raise
    except requests.RequestException as exc:
        raise PluggyAPIError("Could not communicate with the Pluggy API.") from exc
    except ValueError as exc:
        raise PluggyAPIError("Pluggy returned an invalid JSON response.") from exc


def _get_all_results(path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    page = 1

    while True:
        page_params = {**(params or {}), "page": page, "pageSize": PAGE_SIZE}
        payload = _request("GET", path, params=page_params)
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise PluggyAPIError(f"Pluggy returned an invalid list for {path}.")

        page_results = payload["results"]
        if any(not isinstance(result, dict) for result in page_results):
            raise PluggyAPIError(f"Pluggy returned an invalid record for {path}.")
        results.extend(page_results)

        try:
            total_pages = max(1, int(payload.get("totalPages", page)))
        except (TypeError, ValueError) as exc:
            raise PluggyAPIError(f"Pluggy returned invalid pagination for {path}.") from exc
        if page >= total_pages:
            return results
        page += 1


def _get_transaction_page(
    account_id: str,
    after: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    params: dict[str, Any] = {"accountId": account_id}
    if after is not None:
        params["after"] = after
    payload = _request("GET", "/v2/transactions", params=params)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise PluggyAPIError("Pluggy returned an invalid transaction list.")

    transactions = payload["results"]
    if any(not isinstance(transaction, dict) for transaction in transactions):
        raise PluggyAPIError("Pluggy returned an invalid transaction record.")

    next_page = payload.get("next")
    if not next_page:
        return transactions, None
    if not isinstance(next_page, str):
        raise PluggyAPIError("Pluggy returned an invalid transaction cursor.")

    next_cursor = parse_qs(urlparse(next_page).query).get("after", [None])[0]
    if not isinstance(next_cursor, str) or next_cursor == after:
        raise PluggyAPIError("Pluggy returned an invalid transaction cursor.")
    return transactions, next_cursor


def _get_all_transactions(account_id: str) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    after: str | None = None
    seen_cursors: set[str] = set()

    while True:
        page_results, next_cursor = _get_transaction_page(account_id, after)
        transactions.extend(page_results)
        if next_cursor is None:
            return transactions
        if next_cursor in seen_cursors:
            raise PluggyAPIError("Pluggy returned a repeated transaction cursor.")
        seen_cursors.add(next_cursor)
        after = next_cursor


def get_accounts_snapshot_timestamp() -> str | None:
    if not ACCOUNTS_FILE.exists():
        return None
    try:
        timestamp = ACCOUNTS_FILE.stat().st_mtime
    except OSError as exc:
        raise RuntimeError("Could not read the accounts JSON file timestamp.") from exc
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _configured_accounts() -> list[dict[str, Any]] | None:
    if not ACCOUNTS_FILE.exists():
        return None

    try:
        with ACCOUNTS_FILE.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read the configured accounts file: {ACCOUNTS_FILE}.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("The configured accounts file must contain a JSON object.")

    accounts: list[dict[str, Any]] = []
    for institution, institution_accounts in payload.items():
        if not isinstance(institution_accounts, dict):
            raise RuntimeError("Each institution in the configured accounts file must be an object.")
        for account_type, account in institution_accounts.items():
            if not isinstance(account, dict):
                raise RuntimeError("Each configured account must be an object.")
            account_id = account.get("id")
            item_id = account.get("itemId")
            if not isinstance(account_id, str) or not account_id:
                raise RuntimeError("Every configured account must have an id.")
            if not isinstance(item_id, str) or not item_id:
                raise RuntimeError("Every configured account must have an itemId.")
            current_type = str(account.get("type") or account_type).upper()
            balance = account.get("balance")
            accounts.append(
                {
                    "id": account_id,
                    "itemId": item_id,
                    "type": current_type,
                    "subtype": account.get("subtype"),
                    "name": account.get("marketingName") or account.get("name") or current_type,
                    "institution": str(institution),
                    "balance": balance if isinstance(balance, (int, float)) else 0,
                    "currencyCode": account.get("currencyCode") or "BRL",
                }
            )
    return accounts


def get_accounts(account_type: str | None = None) -> list[dict[str, Any]]:
    configured_accounts = _configured_accounts()
    if configured_accounts is None:
        live_accounts = _get_all_results("/accounts")
        source_accounts = [
            {
                "id": account.get("id"),
                "itemId": account.get("itemId"),
                "type": str(account.get("type") or "").upper(),
                "subtype": account.get("subtype"),
                "name": account.get("marketingName") or account.get("name"),
                "institution": None,
                "balance": account.get("balance", 0),
                "currencyCode": account.get("currencyCode") or "BRL",
            }
            for account in live_accounts
        ]
    else:
        source_accounts = configured_accounts

    accounts: list[dict[str, Any]] = []
    for account in source_accounts:
        current_type = str(account.get("type") or "").upper()
        if account_type and current_type != account_type.upper():
            continue
        accounts.append(
            {
                "id": account.get("id"),
                "itemId": account.get("itemId"),
                "type": current_type,
                "subtype": account.get("subtype"),
                "name": account.get("name") or current_type,
                "institution": account.get("institution"),
                "balance": account.get("balance", 0),
                "currencyCode": account.get("currencyCode", "BRL"),
            }
        )
    return accounts


def get_dashboard_summary() -> dict[str, float]:
    return summarize_accounts(get_accounts())


def summarize_accounts(accounts: list[dict[str, Any]]) -> dict[str, float]:
    bank_balance = sum(
        account["balance"]
        for account in accounts
        if account["type"] == "BANK" and account["currencyCode"] == "BRL"
    )
    assets = sum(
        account["balance"]
        for account in accounts
        if account["type"] in {"BANK", "INVESTMENT"}
        and account["currencyCode"] == "BRL"
    )
    credit_balance = sum(
        account["balance"]
        for account in accounts
        if account["type"] == "CREDIT" and account["currencyCode"] == "BRL"
    )
    return {
        "totalBalance": assets - credit_balance,
        "bankBalance": bank_balance,
    }


def get_total_balance() -> list[float]:
    return [account["balance"] for account in get_accounts("BANK")]


def get_past_invoices() -> dict[str, list[dict[str, Any]]]:
    invoices: list[dict[str, Any]] = []
    for account in get_accounts("CREDIT"):
        bills = _get_all_results("/bills", {"accountId": account["id"]})
        for bill in bills:
            invoices.append(
                {
                    "accountId": account["id"],
                    "totalAmountCurrencyCode": bill.get("totalAmountCurrencyCode") or account["currencyCode"],
                    "totalAmount": bill.get("totalAmount"),
                    "dueDate": bill.get("dueDate"),
                }
            )
    invoices.sort(key=lambda invoice: str(invoice.get("dueDate") or ""), reverse=True)
    return {"PastInvoices": invoices}


def get_monthly_credit_expenses() -> dict[str, list[dict[str, Any]]]:
    totals_by_month: dict[str, float] = {}
    for account in get_accounts("CREDIT"):
        transactions = _get_all_transactions(account["id"])
        for transaction in transactions:
            if (transaction.get("currencyCode") or account["currencyCode"]) != "BRL":
                continue

            amount = transaction.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                continue

            metadata = transaction.get("creditCardMetadata")
            forecast_month = (
                metadata.get("billForecastDate")
                if isinstance(metadata, dict)
                else None
            )
            transaction_date = transaction.get("date")
            month = (
                forecast_month[:7]
                if isinstance(forecast_month, str) and len(forecast_month) >= 7
                else transaction_date[:7]
                if isinstance(transaction_date, str) and len(transaction_date) >= 7
                else None
            )
            if month is None:
                continue

            # Positive transaction amounts are purchases/installments. Negative
            # credits and repayments must not reduce the spending chart.
            # `metadata.totalAmount` is the full purchase amount, not the installment.
            totals_by_month[month] = totals_by_month.get(month, 0) + amount

    return {
        "MonthlyExpenses": [
            {"month": month, "amount": totals_by_month[month], "currencyCode": "BRL"}
            for month in sorted(totals_by_month)
        ]
    }


def get_transaction_history(
    account_id: str,
    after: str | None = None,
) -> dict[str, Any]:
    if not any(account["id"] == account_id for account in get_accounts()):
        raise LookupError("The requested account is not configured.")

    transactions, next_cursor = _get_transaction_page(account_id, after)
    history = [
        {
            "id": transaction.get("id"),
            "accountId": transaction.get("accountId") or account_id,
            "amountCurrencyCode": transaction.get("currencyCode") or "BRL",
            "amount": transaction.get("amount"),
            "date": transaction.get("date"),
            "description": transaction.get("description") or "Transação sem descrição",
            "category": transaction.get("category") or "Sem categoria",
            "type": transaction.get("type"),
        }
        for transaction in transactions
    ]
    history.sort(key=lambda transaction: str(transaction.get("date") or ""), reverse=True)
    return {"TransactionHistory": history, "nextCursor": next_cursor}


def get_webhooks() -> Any:
    return _request("GET", "/webhooks")
