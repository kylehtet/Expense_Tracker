from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import SYNC_COOLDOWN_SECONDS, _last_sync_at, app

# StaticPool pins the pool to a single connection - without it, each pooled
# connection to sqlite:///:memory: gets its own separate, empty database.
test_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _fresh_db_and_rate_limits():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    _last_sync_at.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def _link_and_exchange(client, user_id="user-1", access_token="access-sandbox-abc123"):
    with patch("app.main.exchange_public_token", return_value=access_token):
        response = client.post("/link/exchange", json={"user_id": user_id, "public_token": "public-token"})
    assert response.status_code == 200
    return response


class TestConfig:
    def test_returns_plaid_env(self, client):
        response = client.get("/config")
        assert response.status_code == 200
        body = response.json()
        assert "plaid_env" in body
        assert "is_sandbox" in body


class TestLinkToken:
    def test_returns_link_token(self, client):
        with patch("app.main.create_link_token", return_value="link-sandbox-abc123") as mock_create:
            response = client.post("/link/token", json={"user_id": "user-1"})

        assert response.status_code == 200
        assert response.json() == {"link_token": "link-sandbox-abc123"}
        mock_create.assert_called_once_with(user_id="user-1")


class TestLinkExchange:
    def test_stores_access_token_and_never_returns_it(self, client):
        response = _link_and_exchange(client)
        assert response.json() == {"status": "ok"}
        assert "access_token" not in response.text


class TestSync:
    def test_404_without_a_linked_item(self, client):
        response = client.post("/sync", json={"user_id": "nobody"})
        assert response.status_code == 404

    def test_syncs_and_categorizes_transactions(self, client):
        _link_and_exchange(client)
        raw_transactions = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-01",
                "name": "Landlord Properties LLC",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES", "detailed": "RENT_AND_UTILITIES_RENT"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-07-06",
                "name": "NETFLIX.COM",
                "merchant_name": "Netflix",
                "amount": 15.49,
                "personal_finance_category": {"primary": "ENTERTAINMENT", "detailed": "ENTERTAINMENT_TV_AND_MOVIES"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value=raw_transactions):
            response = client.post("/sync", json={"user_id": "user-1"})

        assert response.status_code == 200
        assert response.json() == {"synced_count": 2}

        transactions = client.get("/transactions", params={"user_id": "user-1"}).json()
        categories = {t["transaction_id"]: t["category"] for t in transactions}
        assert categories == {"tx1": "Housing", "tx2": "Subscriptions"}

    def test_second_sync_within_cooldown_is_rate_limited(self, client):
        _link_and_exchange(client)
        with patch("app.main.fetch_transactions", return_value=[]):
            first = client.post("/sync", json={"user_id": "user-1"})
            second = client.post("/sync", json={"user_id": "user-1"})

        assert first.status_code == 200
        assert second.status_code == 429

    def test_different_users_have_independent_rate_limits(self, client):
        _link_and_exchange(client, user_id="user-1")
        _link_and_exchange(client, user_id="user-2")
        with patch("app.main.fetch_transactions", return_value=[]):
            first = client.post("/sync", json={"user_id": "user-1"})
            second = client.post("/sync", json={"user_id": "user-2"})

        assert first.status_code == 200
        assert second.status_code == 200

    def test_cooldown_constant_is_positive(self):
        assert SYNC_COOLDOWN_SECONDS > 0


class TestTransactions:
    def _sync_sample(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-01",
                "name": "Rent",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-07-15",
                "name": "Whole Foods",
                "amount": 80.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
            {
                "transaction_id": "tx3",
                "date": "2026-08-01",
                "name": "Rent",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value=raw):
            client.post("/sync", json={"user_id": "user-1"})

    def test_filters_by_category(self, client):
        self._sync_sample(client)
        response = client.get("/transactions", params={"user_id": "user-1", "category": "Food"})
        body = response.json()
        assert len(body) == 1
        assert body[0]["transaction_id"] == "tx2"

    def test_filters_by_date_range(self, client):
        self._sync_sample(client)
        response = client.get(
            "/transactions",
            params={"user_id": "user-1", "start_date": "2026-07-01", "end_date": "2026-07-31"},
        )
        ids = {t["transaction_id"] for t in response.json()}
        assert ids == {"tx1", "tx2"}


class TestBudget:
    def test_set_and_read_back_budget(self, client):
        response = client.post("/budget", json={"user_id": "user-1", "category": "Food", "amount": 300.0})
        assert response.status_code == 200
        assert response.json() == {"category": "Food", "amount": 300.0}

    def test_updating_budget_overwrites_not_duplicates(self, client):
        client.post("/budget", json={"user_id": "user-1", "category": "Food", "amount": 300.0})
        client.post("/budget", json={"user_id": "user-1", "category": "Food", "amount": 250.0})

        response = client.get(
            "/budget/status", params={"user_id": "user-1", "start_date": "2020-01-01", "end_date": "2030-01-01"}
        )
        assert response.json()["Food"]["budget"] == 250.0

    def test_budget_status_over_under_and_unbudgeted(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-01",
                "name": "Rent",
                "amount": 1700.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-07-15",
                "name": "Whole Foods",
                "amount": 80.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value=raw):
            client.post("/sync", json={"user_id": "user-1"})

        client.post("/budget", json={"user_id": "user-1", "category": "Housing", "amount": 1500.0})
        client.post("/budget", json={"user_id": "user-1", "category": "Food", "amount": 200.0})

        response = client.get(
            "/budget/status", params={"user_id": "user-1", "start_date": "2026-07-01", "end_date": "2026-07-31"}
        )
        body = response.json()
        assert body["Housing"]["status"] == "over"
        assert body["Food"]["status"] == "under"

    def test_defaults_to_current_month_when_no_dates_given(self, client):
        response = client.get("/budget/status", params={"user_id": "user-1"})
        assert response.status_code == 200
