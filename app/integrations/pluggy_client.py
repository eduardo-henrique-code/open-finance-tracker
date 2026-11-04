from http.client import HTTPException
import json
from typing import Any
import requests
from app.core.config import get_settings
import json

PLUGGY_API_URL = "https://api.pluggy.ai"


def get_api_key() -> str:
    settings = get_settings()
    response = requests.post(
        f"{PLUGGY_API_URL}/auth",
        json={
            "clientId": settings.pluggy_client_id,
            "clientSecret": settings.pluggy_client_secret,
        },
        headers={"Content-Type": "application/json"},
        timeout=15,
    )
    response.raise_for_status()
    api_key = response.json().get("apiKey")
    if not isinstance(api_key, str) or not api_key:
        raise RuntimeError("Pluggy authentication response did not contain an API key.")
    return api_key


def get_webhooks() -> Any:
    response = requests.get(
        f"{PLUGGY_API_URL}/webhooks",
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": get_api_key(),
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

def get_bank_accounts(type):
    with open("contas.json", "r", encoding="utf-8") as f:
        dados = json.load(f)

    contas = []
    for nome, conta in dados.items():
        if type in conta:
            dados_bank = conta[type]
            contas.append({"name": dados_bank.get("name"), "itemId": dados_bank.get("itemId"), "id": dados_bank.get("id") })
    return contas

def get_accounts(field, type):
    contas = get_bank_accounts(type)

    return {"Accounts": [{field: conta.get(field)} for conta in contas]}

def get_total_balance(itemsIds):
    infos = []
    for i in itemsIds.get('Accounts', []):
        response = requests.get(
            f"{PLUGGY_API_URL}/accounts",
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": get_api_key(),
            },
            params={"itemId": i.get('itemId'), "type": "BANK"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        accounts = data.get('results', [])

        bank_balance = sum(
            account.get('balance', 0) or 0
            for account in accounts
        )
        infos.append(bank_balance)

    return infos

def get_past_invoices(ids):
    invoices = []
    for i in ids.get('Accounts', []):
        response = requests.get(
            f"{PLUGGY_API_URL}/bills",
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": get_api_key(),
            },
            params={"accountId": i.get('id')},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        invoices.append(data.get('results', []))

    faturas = []
    for invoice_list in invoices:
        for invoice in invoice_list:
            faturas.append({
                "totalAmountCurrencyCode": invoice.get('totalAmountCurrencyCode'),
                "totalAmount": invoice.get('totalAmount'),
                "dueDate": invoice.get('dueDate')
            })
    return {"PastInvoices": faturas}