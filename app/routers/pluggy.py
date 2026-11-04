from fastapi import APIRouter
from app.integrations.pluggy_client import get_accounts, get_api_key, get_past_invoices, get_webhooks, get_total_balance
router = APIRouter()


@router.get("/get_api_key")
def get_api_key_endpoint():
    return {"access_token": get_api_key()}


@router.get("/get_webhooks")
def get_webhooks_endpoint():
    return {"Webhooks": get_webhooks()}

@router.get("/get_name_accounts")
def get_accounts_endpoint():
    return get_accounts('name', 'BANK')

@router.get("/get_total_balance")
def get_total_balance_endpoint():
    itemsIds = get_accounts('itemId', 'BANK')
    return get_total_balance(itemsIds)

@router.get("/get_past_invoices")
def get_past_invoices_endpoint():
    ids = get_accounts('id', 'CREDIT')
    return get_past_invoices(ids)