"""Thin wrapper around the Plaid API: link tokens, token exchange, transactions, balances."""

from __future__ import annotations

import plaid
from plaid.api import plaid_api
from plaid.model.accounts_balance_get_request import AccountsBalanceGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest

from app.config import IS_SANDBOX, PLAID_CLIENT_ID, PLAID_SECRET, get_plaid_host

CLIENT_NAME = "Expense Tracker"

_client: plaid_api.PlaidApi | None = None


def _get_client() -> plaid_api.PlaidApi:
    global _client
    if _client is None:
        configuration = plaid.Configuration(
            host=get_plaid_host(),
            api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
        )
        _client = plaid_api.PlaidApi(plaid.ApiClient(configuration))
    return _client


def create_link_token(user_id: str) -> str:
    request = LinkTokenCreateRequest(
        client_name=CLIENT_NAME,
        language="en",
        country_codes=[CountryCode("US")],
        products=[Products("transactions")],
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
    )
    response = _get_client().link_token_create(request)
    return response.link_token


def exchange_public_token(public_token: str) -> str:
    request = ItemPublicTokenExchangeRequest(public_token=public_token)
    response = _get_client().item_public_token_exchange(request)
    return response.access_token


def fetch_transactions(access_token: str, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
    """Pulls all transactions via the cursor-paginated sync endpoint. sync itself has
    no date-range parameter (it returns everything new since the cursor), so
    start_date/end_date filter the result client-side."""
    transactions = []
    cursor = None
    has_more = True
    while has_more:
        request = TransactionsSyncRequest(access_token=access_token, cursor=cursor)
        response = _get_client().transactions_sync(request)
        transactions.extend(t.to_dict() for t in response.added)
        cursor = response.next_cursor
        has_more = response.has_more

    if start_date or end_date:
        transactions = [
            t
            for t in transactions
            if (start_date is None or str(t["date"]) >= start_date)
            and (end_date is None or str(t["date"]) <= end_date)
        ]
    return transactions


def fetch_balances(access_token: str) -> dict:
    request = AccountsBalanceGetRequest(access_token=access_token)
    response = _get_client().accounts_balance_get(request)
    return {"accounts": [a.to_dict() for a in response.accounts]}


def create_sandbox_public_token(institution_id: str = "ins_109508") -> str:
    """Sandbox-only: mints a public_token for a fake institution/login without
    driving the Link UI, so the backend flow is testable end-to-end on its own.
    Default institution is Plaid's "First Platypus Bank" test institution."""
    if not IS_SANDBOX:
        raise RuntimeError("create_sandbox_public_token is only valid when PLAID_ENV=sandbox")
    request = SandboxPublicTokenCreateRequest(
        institution_id=institution_id,
        initial_products=[Products("transactions")],
    )
    response = _get_client().sandbox_public_token_create(request)
    return response.public_token
