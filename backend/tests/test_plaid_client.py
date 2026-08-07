from unittest.mock import MagicMock, patch

import pytest

from app.plaid_client import (
    create_link_token,
    create_sandbox_public_token,
    exchange_public_token,
    fetch_balances,
    fetch_transactions,
)


def _mock_txn(txn_id, date, name, amount):
    txn = MagicMock()
    txn.to_dict.return_value = {"transaction_id": txn_id, "date": date, "name": name, "amount": amount}
    return txn


def _mock_account(account_id, name, available, current):
    acct = MagicMock()
    acct.to_dict.return_value = {
        "account_id": account_id,
        "name": name,
        "type": "depository",
        "balances": {"available": available, "current": current},
    }
    return acct


class TestCreateLinkToken:
    def test_returns_link_token(self):
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.link_token_create.return_value = MagicMock(
                link_token="link-sandbox-abc123"
            )
            token = create_link_token(user_id="user-1")

        assert token == "link-sandbox-abc123"


class TestExchangePublicToken:
    def test_returns_access_token(self):
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.item_public_token_exchange.return_value = MagicMock(
                access_token="access-sandbox-xyz789"
            )
            token = exchange_public_token("public-sandbox-abc123")

        assert token == "access-sandbox-xyz789"


class TestFetchTransactions:
    def test_single_page(self):
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.transactions_sync.return_value = MagicMock(
                added=[_mock_txn("t1", "2026-07-01", "Starbucks", 4.5)],
                next_cursor="cursor-1",
                has_more=False,
            )
            result = fetch_transactions("access-token")

        assert len(result) == 1
        assert result[0]["name"] == "Starbucks"

    def test_paginates_until_has_more_is_false(self):
        page_1 = MagicMock(
            added=[_mock_txn("t1", "2026-07-01", "Starbucks", 4.5)],
            next_cursor="cursor-1",
            has_more=True,
        )
        page_2 = MagicMock(
            added=[_mock_txn("t2", "2026-07-02", "Uber", 12.0)],
            next_cursor="cursor-2",
            has_more=False,
        )
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.transactions_sync.side_effect = [page_1, page_2]
            result = fetch_transactions("access-token")

        assert [t["name"] for t in result] == ["Starbucks", "Uber"]
        assert get_client.return_value.transactions_sync.call_count == 2

    def test_first_request_omits_cursor_field(self):
        """Regression test: TransactionsSyncRequest rejects cursor=None outright,
        so the first sync call must omit the field rather than pass None."""
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.transactions_sync.return_value = MagicMock(
                added=[], next_cursor="cursor-1", has_more=False
            )
            fetch_transactions("access-token")

        sent_request = get_client.return_value.transactions_sync.call_args[0][0]
        assert "cursor" not in sent_request.to_dict()

    def test_filters_by_date_range(self):
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.transactions_sync.return_value = MagicMock(
                added=[
                    _mock_txn("t1", "2026-06-01", "Old", 10.0),
                    _mock_txn("t2", "2026-07-15", "InRange", 20.0),
                    _mock_txn("t3", "2026-08-01", "TooNew", 30.0),
                ],
                next_cursor="cursor-1",
                has_more=False,
            )
            result = fetch_transactions("access-token", start_date="2026-07-01", end_date="2026-07-31")

        assert [t["name"] for t in result] == ["InRange"]


class TestFetchBalances:
    def test_returns_accounts(self):
        with patch("app.plaid_client._get_client") as get_client:
            get_client.return_value.accounts_balance_get.return_value = MagicMock(
                accounts=[_mock_account("a1", "Plaid Checking", 100.0, 110.0)]
            )
            result = fetch_balances("access-token")

        assert result["accounts"][0]["name"] == "Plaid Checking"
        assert result["accounts"][0]["balances"]["current"] == 110.0


class TestCreateSandboxPublicToken:
    def test_returns_public_token_in_sandbox(self):
        with patch("app.plaid_client._get_client") as get_client, patch(
            "app.plaid_client.IS_SANDBOX", True
        ):
            get_client.return_value.sandbox_public_token_create.return_value = MagicMock(
                public_token="public-sandbox-abc123"
            )
            token = create_sandbox_public_token()

        assert token == "public-sandbox-abc123"

    def test_raises_outside_sandbox(self):
        with patch("app.plaid_client.IS_SANDBOX", False):
            with pytest.raises(RuntimeError):
                create_sandbox_public_token()
