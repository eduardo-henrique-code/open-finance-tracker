from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

from app.integrations.pluggy_client import (
    PluggyAPIError,
    get_accounts,
    get_accounts_snapshot_timestamp,
    get_dashboard_summary,
    get_monthly_credit_expenses,
    get_past_invoices,
    summarize_accounts,
    get_transaction_history,
    get_total_balance,
    get_webhooks,
)

router = APIRouter()


def _run_pluggy(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except PluggyAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/get_webhooks")
def get_webhooks_endpoint() -> Any:
    return _run_pluggy(get_webhooks)


@router.get("/get_accounts")
def get_accounts_endpoint() -> dict[str, Any]:
    accounts = _run_pluggy(get_accounts)
    return {
        "Accounts": accounts,
        **summarize_accounts(accounts),
        "dataUpdatedAt": _run_pluggy(get_accounts_snapshot_timestamp),
    }


@router.get("/get_name_accounts")
def get_name_accounts_endpoint() -> dict[str, list[dict[str, Any]]]:
    return {"Accounts": _run_pluggy(lambda: get_accounts("BANK"))}


@router.get("/get_dashboard_summary")
def get_dashboard_summary_endpoint() -> dict[str, float]:
    return _run_pluggy(get_dashboard_summary)


@router.get("/get_total_balance")
def get_total_balance_endpoint() -> list[float]:
    return _run_pluggy(get_total_balance)


@router.get("/get_past_invoices")
def get_past_invoices_endpoint() -> dict[str, list[dict[str, Any]]]:
    return _run_pluggy(get_past_invoices)


@router.get("/get_monthly_credit_expenses")
def get_monthly_credit_expenses_endpoint() -> dict[str, list[dict[str, Any]]]:
    return _run_pluggy(get_monthly_credit_expenses)


@router.get("/get_transaction_history")
def get_transaction_history_endpoint(
    account_id: str = Query(alias="accountId", min_length=1),
    after: str | None = Query(default=None, max_length=1024),
) -> dict[str, Any]:
    try:
        return get_transaction_history(account_id, after)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PluggyAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
