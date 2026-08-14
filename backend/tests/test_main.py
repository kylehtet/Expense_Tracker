from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.firebase_auth import require_firebase_auth
from app.goal_tracker import compute_monthly_savings_capacity
from app.main import (
    SYNC_COOLDOWN_SECONDS,
    _last_affordability_check_at,
    _last_auto_budget_at,
    _last_interest_signup_at,
    _last_recommend_at,
    _last_sync_at,
    app,
)

# StaticPool pins the pool to a single connection - without it, each pooled
# connection to sqlite:///:memory: gets its own separate, empty database.
test_engine = create_engine(
    "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

DEFAULT_USER_ID = "user-1"


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


def _authenticate_as(user_id: str) -> None:
    """Overrides the real Firebase token-verification dependency with a fake
    decoded token for the given uid - the only way to test user-scoped
    behavior without a live Firebase ID token. See TestAuthProtection for a
    test against the *real*, unmocked dependency."""
    app.dependency_overrides[require_firebase_auth] = lambda: {"uid": user_id}


@pytest.fixture(autouse=True)
def _fresh_db_and_rate_limits():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    _last_sync_at.clear()
    _last_affordability_check_at.clear()
    _last_recommend_at.clear()
    _last_auto_budget_at.clear()
    _last_interest_signup_at.clear()
    _authenticate_as(DEFAULT_USER_ID)
    yield
    app.dependency_overrides.pop(require_firebase_auth, None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_as():
    """Switches the fake authenticated session to a different user_id -
    for tests that need to prove two identities are kept separate."""
    return _authenticate_as


def _link_and_exchange(client, access_token="access-sandbox-abc123"):
    with patch("app.main.exchange_public_token", return_value=access_token):
        response = client.post("/link/exchange", json={"public_token": "public-token"})
    assert response.status_code == 200
    return response


class TestConfig:
    def test_returns_plaid_env(self, client):
        response = client.get("/config")
        assert response.status_code == 200
        body = response.json()
        assert "plaid_env" in body
        assert "is_sandbox" in body

    def test_includes_production_connection_counter(self, client):
        response = client.get("/config")
        body = response.json()
        assert body["production_connections_used"] == 0
        assert body["production_connections_limit"] == 10

    def test_does_not_require_authentication(self, client):
        app.dependency_overrides.pop(require_firebase_auth, None)
        try:
            response = client.get("/config")
        finally:
            _authenticate_as(DEFAULT_USER_ID)
        assert response.status_code == 200


class TestInterestSignup:
    def test_does_not_require_authentication(self, client):
        app.dependency_overrides.pop(require_firebase_auth, None)
        try:
            response = client.post("/interest", json={"email": "interested@example.com"})
        finally:
            _authenticate_as(DEFAULT_USER_ID)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_rejects_malformed_email(self, client):
        response = client.post("/interest", json={"email": "not-an-email"})
        assert response.status_code == 422

    def test_resubmitting_the_same_email_is_still_ok(self, client):
        first = client.post("/interest", json={"email": "twice@example.com"})
        _last_interest_signup_at.clear()  # bypass the per-IP cooldown, not what this test covers
        second = client.post("/interest", json={"email": "twice@example.com"})
        assert first.status_code == 200
        assert second.status_code == 200

    def test_second_request_within_cooldown_is_rate_limited(self, client):
        first = client.post("/interest", json={"email": "a@example.com"})
        second = client.post("/interest", json={"email": "b@example.com"})
        assert first.status_code == 200
        assert second.status_code == 429


class TestMe:
    def test_reports_no_linked_bank_for_a_fresh_user(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json() == {"uid": DEFAULT_USER_ID, "has_linked_bank": False}

    def test_reports_linked_bank_after_exchange(self, client):
        _link_and_exchange(client)
        response = client.get("/auth/me")
        assert response.json()["has_linked_bank"] is True

    def test_reflects_whichever_uid_is_authenticated(self, client, auth_as):
        auth_as("someone-else")
        assert client.get("/auth/me").json()["uid"] == "someone-else"


class TestAuthProtection:
    """Tests against the real, unmocked require_firebase_auth dependency -
    every other class in this file overrides it with a fake decoded token so
    it can test user-scoped behavior without a live Firebase ID token. This
    class is what actually proves the protection is real."""

    def test_protected_endpoint_401s_without_a_session(self, client):
        app.dependency_overrides.pop(require_firebase_auth, None)
        try:
            response = client.get("/transactions")
        finally:
            _authenticate_as(DEFAULT_USER_ID)
        assert response.status_code == 401

    def test_protected_post_endpoint_401s_without_a_session(self, client):
        app.dependency_overrides.pop(require_firebase_auth, None)
        try:
            response = client.post("/budget", json={"category": "Food", "amount": 100.0})
        finally:
            _authenticate_as(DEFAULT_USER_ID)
        assert response.status_code == 401


class TestLinkToken:
    def test_returns_link_token(self, client):
        with patch("app.main.create_link_token", return_value="link-sandbox-abc123") as mock_create:
            response = client.post("/link/token")

        assert response.status_code == 200
        assert response.json() == {"link_token": "link-sandbox-abc123"}
        mock_create.assert_called_once_with(user_id=DEFAULT_USER_ID)


class TestLinkExchange:
    def test_stores_access_token_and_never_returns_it(self, client):
        response = _link_and_exchange(client)
        assert response.json() == {"status": "ok"}
        assert "access_token" not in response.text

    def test_sandbox_exchange_does_not_count_against_production_limit(self, client):
        with patch("app.main.IS_SANDBOX", True):
            _link_and_exchange(client)
        assert client.get("/config").json()["production_connections_used"] == 0

    def test_production_exchange_increments_the_counter(self, client, auth_as):
        auth_as("user-prod")
        with patch("app.main.IS_SANDBOX", False):
            _link_and_exchange(client)
        assert client.get("/config").json()["production_connections_used"] == 1

    def test_counter_never_decreases_after_disconnect(self, client, auth_as):
        auth_as("user-prod")
        with patch("app.main.IS_SANDBOX", False):
            _link_and_exchange(client)
            with patch("app.main.remove_item"):
                client.post("/link/disconnect")
        assert client.get("/config").json()["production_connections_used"] == 1

    def test_same_account_relinking_does_not_double_count(self, client, auth_as):
        """A single account disconnecting and relinking (or just calling
        /link/exchange twice) must not burn two slots against the limit -
        only distinct accounts should count."""
        auth_as("user-prod")
        with patch("app.main.IS_SANDBOX", False):
            _link_and_exchange(client)
            with patch("app.main.remove_item"):
                client.post("/link/disconnect")
            _link_and_exchange(client)
            _link_and_exchange(client)
        assert client.get("/config").json()["production_connections_used"] == 1

    def test_different_accounts_each_count_once(self, client, auth_as):
        with patch("app.main.IS_SANDBOX", False):
            auth_as("user-prod-a")
            _link_and_exchange(client)
            auth_as("user-prod-b")
            _link_and_exchange(client)
        assert client.get("/config").json()["production_connections_used"] == 2


class TestDisconnect:
    def test_removes_item_and_calls_plaid_remove(self, client):
        _link_and_exchange(client, access_token="access-sandbox-xyz")
        with patch("app.main.remove_item") as mock_remove:
            response = client.post("/link/disconnect")

        assert response.status_code == 200
        mock_remove.assert_called_once_with("access-sandbox-xyz")
        # Item is gone locally - syncing again should 404 like a never-linked user.
        assert client.post("/sync").status_code == 404

    def test_clears_stored_transactions(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-01",
                "name": "Coffee",
                "amount": 5.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        assert len(client.get("/transactions").json()) == 1

        with patch("app.main.remove_item"):
            client.post("/link/disconnect")

        # Re-link so /transactions doesn't 404-equivalent on an unlinked user,
        # then confirm the old transactions didn't survive the disconnect.
        _link_and_exchange(client)
        assert client.get("/transactions").json() == []

    def test_404_when_nothing_linked(self, client):
        response = client.post("/link/disconnect")
        assert response.status_code == 404

    def test_local_cleanup_succeeds_even_if_plaid_remove_call_fails(self, client):
        _link_and_exchange(client)
        with patch("app.main.remove_item", side_effect=RuntimeError("plaid unavailable")):
            response = client.post("/link/disconnect")

        assert response.status_code == 200
        assert client.post("/sync").status_code == 404


class TestSync:
    def test_404_without_a_linked_item(self, client):
        response = client.post("/sync")
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
        with patch("app.main.fetch_transactions", return_value={"added": raw_transactions, "modified": [], "removed": []}):
            response = client.post("/sync")

        assert response.status_code == 200
        assert response.json() == {"synced_count": 2}

        transactions = client.get("/transactions").json()
        categories = {t["transaction_id"]: t["category"] for t in transactions}
        assert categories == {"tx1": "Housing", "tx2": "Subscriptions"}

    def test_modified_transaction_updates_the_existing_record(self, client):
        """A pending charge settling (amount/date changing on an already-synced
        transaction_id) comes back from Plaid as "modified", not a new "added" -
        the sync endpoint must still pick it up."""
        _link_and_exchange(client)
        pending = {
            "transaction_id": "tx1",
            "date": "2026-07-01",
            "name": "Restaurant",
            "amount": 0.0,
            "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
        }
        with patch("app.main.fetch_transactions", return_value={"added": [pending], "modified": [], "removed": []}):
            client.post("/sync")

        _last_sync_at.clear()
        settled = {**pending, "amount": 42.5}
        with patch("app.main.fetch_transactions", return_value={"added": [], "modified": [settled], "removed": []}):
            response = client.post("/sync")

        assert response.status_code == 200
        assert response.json() == {"synced_count": 1}
        transactions = client.get("/transactions").json()
        assert len(transactions) == 1
        assert transactions[0]["amount"] == 42.5

    def test_removed_transaction_is_deleted(self, client):
        """A reversed/cancelled transaction comes back from Plaid as "removed" (just
        an id) - it should disappear locally too, not linger after the bank retracts it."""
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-01",
                "name": "Restaurant",
                "amount": 42.5,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")

        _last_sync_at.clear()
        with patch("app.main.fetch_transactions", return_value={"added": [], "modified": [], "removed": ["tx1"]}):
            response = client.post("/sync")

        assert response.status_code == 200
        assert response.json() == {"synced_count": 0}
        assert client.get("/transactions").json() == []

    def test_second_sync_within_cooldown_is_rate_limited(self, client):
        _link_and_exchange(client)
        with patch("app.main.fetch_transactions", return_value={"added": [], "modified": [], "removed": []}):
            first = client.post("/sync")
            second = client.post("/sync")

        assert first.status_code == 200
        assert second.status_code == 429

    def test_different_users_have_independent_rate_limits(self, client, auth_as):
        auth_as("user-1")
        _link_and_exchange(client)
        with patch("app.main.fetch_transactions", return_value={"added": [], "modified": [], "removed": []}):
            first = client.post("/sync")

        auth_as("user-2")
        _link_and_exchange(client)
        with patch("app.main.fetch_transactions", return_value={"added": [], "modified": [], "removed": []}):
            second = client.post("/sync")

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
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")

    def test_filters_by_category(self, client):
        self._sync_sample(client)
        response = client.get("/transactions", params={"category": "Food"})
        body = response.json()
        assert len(body) == 1
        assert body[0]["transaction_id"] == "tx2"

    def test_filters_by_date_range(self, client):
        self._sync_sample(client)
        response = client.get(
            "/transactions",
            params={"start_date": "2026-07-01", "end_date": "2026-07-31"},
        )
        ids = {t["transaction_id"] for t in response.json()}
        assert ids == {"tx1", "tx2"}

    def test_different_users_see_only_their_own_transactions(self, client, auth_as):
        auth_as("user-1")
        self._sync_sample(client)

        auth_as("user-2")
        assert client.get("/transactions").json() == []


class TestBudget:
    def test_set_and_read_back_budget(self, client):
        response = client.post("/budget", json={"category": "Food", "amount": 300.0})
        assert response.status_code == 200
        assert response.json() == {"category": "Food", "amount": 300.0}

    def test_updating_budget_overwrites_not_duplicates(self, client):
        client.post("/budget", json={"category": "Food", "amount": 300.0})
        client.post("/budget", json={"category": "Food", "amount": 250.0})

        response = client.get("/budget/status", params={"start_date": "2020-01-01", "end_date": "2030-01-01"})
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
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")

        client.post("/budget", json={"category": "Housing", "amount": 1500.0})
        client.post("/budget", json={"category": "Food", "amount": 200.0})

        response = client.get("/budget/status", params={"start_date": "2026-07-01", "end_date": "2026-07-31"})
        body = response.json()
        assert body["Housing"]["status"] == "over"
        assert body["Food"]["status"] == "under"

    def test_defaults_to_current_month_when_no_dates_given(self, client):
        response = client.get("/budget/status")
        assert response.status_code == 200

    def test_different_users_have_independent_budgets(self, client, auth_as):
        auth_as("user-1")
        client.post("/budget", json={"category": "Food", "amount": 300.0})

        auth_as("user-2")
        assert client.get("/budget/status").json() == {}


class TestAffordabilityCheck:
    def _seed_current_month(self, client):
        _link_and_exchange(client)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        raw = [
            {
                "transaction_id": "tx1",
                "date": today,
                "name": "AMC Theatres",
                "amount": 402.0,
                "personal_finance_category": {"primary": "ENTERTAINMENT"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        client.post("/budget", json={"category": "Entertainment", "amount": 500.0})

    def test_returns_verdict_and_math(self, client):
        self._seed_current_month(client)
        with patch(
            "app.main.explain_verdict",
            return_value={"explanation": "Tight but it fits.", "source": "ai", "error": None},
        ):
            response = client.post(
                "/affordability/check",
                json={"price": 480.0, "category": "Entertainment", "timing": "one_time"},
            )

        assert response.status_code == 200
        body = response.json()
        # Only Entertainment is budgeted here, so the $480 purchase exceeds
        # both the category and the entire (small, single-category) budget pool.
        assert body["verdict"] == "over"
        assert body["explanation"] == "Tight but it fits."
        assert body["explanation_source"] == "ai"
        assert body["math"]["category_left_before"] == 98.0

    def test_rejects_non_positive_price(self, client):
        self._seed_current_month(client)
        response = client.post(
            "/affordability/check",
            json={"price": 0, "category": "Entertainment", "timing": "one_time"},
        )
        assert response.status_code == 400

    def test_rejects_unknown_timing(self, client):
        self._seed_current_month(client)
        response = client.post(
            "/affordability/check",
            json={"price": 50, "category": "Entertainment", "timing": "yearly"},
        )
        assert response.status_code == 400

    def test_works_for_a_user_with_no_budgets_or_transactions_yet(self, client):
        response = client.post(
            "/affordability/check",
            json={"price": 50, "category": "Food", "timing": "one_time"},
        )
        assert response.status_code == 200
        # Nothing budgeted anywhere yet - nothing to be "over", so this
        # shouldn't read as a rejection.
        assert response.json()["verdict"] == "comfortable"

    def test_second_check_within_cooldown_is_rate_limited(self, client):
        self._seed_current_month(client)
        with patch("app.main.explain_verdict", return_value={"explanation": "x", "source": "ai", "error": None}):
            first = client.post(
                "/affordability/check",
                json={"price": 50, "category": "Entertainment", "timing": "one_time"},
            )
            second = client.post(
                "/affordability/check",
                json={"price": 50, "category": "Entertainment", "timing": "one_time"},
            )
        assert first.status_code == 200
        assert second.status_code == 429

    def test_housing_category_includes_retrieved_facts_and_passes_location(self, client):
        self._seed_current_month(client)
        client.post("/budget", json={"category": "Housing", "amount": 2000.0})
        facts = [{"text": "The average 30 year mortgage rate is 6.8%.", "category": "mortgage_rate", "source": "FRED", "stale": False}]
        with patch("app.main.explain_verdict", return_value={"explanation": "x", "source": "ai", "error": None}), patch(
            "app.main.retrieve_housing_context", return_value=facts
        ) as retrieve_housing_context:
            response = client.post(
                "/affordability/check",
                json={
                    "price": 500.0,
                    "category": "Housing",
                    "timing": "one_time",
                    "location": "Austin, TX",
                },
            )

        assert response.status_code == 200
        retrieve_housing_context.assert_called_once_with("Austin, TX")
        assert response.json()["retrieved_facts"] == facts

    def test_non_housing_category_never_calls_retrieval(self, client):
        self._seed_current_month(client)
        with patch("app.main.explain_verdict", return_value={"explanation": "x", "source": "ai", "error": None}), patch(
            "app.main.retrieve_housing_context"
        ) as retrieve_housing_context:
            response = client.post(
                "/affordability/check",
                json={"price": 50, "category": "Entertainment", "timing": "one_time"},
            )

        assert response.status_code == 200
        retrieve_housing_context.assert_not_called()
        assert response.json()["retrieved_facts"] == []

    def test_retrieval_failure_degrades_to_empty_facts_not_an_error(self, client):
        self._seed_current_month(client)
        client.post("/budget", json={"category": "Housing", "amount": 2000.0})
        with patch("app.main.explain_verdict", return_value={"explanation": "x", "source": "ai", "error": None}), patch(
            "app.main.retrieve_housing_context", side_effect=RuntimeError("chroma unavailable")
        ):
            response = client.post(
                "/affordability/check",
                json={"price": 500.0, "category": "Housing", "timing": "one_time"},
            )

        assert response.status_code == 200
        assert response.json()["retrieved_facts"] == []

    def test_includes_savings_plan_when_not_comfortable(self, client):
        self._seed_current_month(client)
        with patch("app.main.explain_verdict", return_value={"explanation": "x", "source": "ai", "error": None}):
            response = client.post(
                "/affordability/check",
                json={"price": 480.0, "category": "Entertainment", "timing": "one_time"},
            )

        body = response.json()
        assert body["verdict"] != "comfortable"
        assert body["savings_plan"] is not None
        assert body["savings_plan"]["gap"] == 480.0
        assert set(body["savings_plan"].keys()) == {"gap", "monthly_savings_capacity", "months_to_goal"}

    def test_savings_plan_is_none_when_comfortable(self, client):
        response = client.post(
            "/affordability/check",
            json={"price": 50, "category": "Food", "timing": "one_time"},
        )
        assert response.json()["verdict"] == "comfortable"
        assert response.json()["savings_plan"] is None


class TestGoals:
    def _seed(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-05-15",
                "name": "Whole Foods",
                "amount": 100.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-06-15",
                "name": "Whole Foods",
                "amount": 100.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
            {
                "transaction_id": "tx3",
                "date": "2026-07-20",
                "name": "Whole Foods",
                "amount": 50.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        client.post("/budget", json={"category": "Food", "amount": 300.0})

    def _expected_capacity(self):
        budgets = {"Food": 300.0}
        transactions = [
            {"date": "2026-05-15", "amount": 100.0, "category": "Food"},
            {"date": "2026-06-15", "amount": 100.0, "category": "Food"},
            {"date": "2026-07-20", "amount": 50.0, "category": "Food"},
        ]
        return compute_monthly_savings_capacity(budgets, transactions)

    def _create(self, client, **overrides):
        payload = {"name": "PS5", "target_amount": 500.0, "category": "Food"}
        payload.update(overrides)
        return client.post("/goals", json=payload)

    def test_create_goal_computes_capacity_from_real_history(self, client):
        self._seed(client)
        response = self._create(client)
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "PS5"
        assert body["status"] == "active"
        assert body["monthly_savings_capacity"] == self._expected_capacity()
        assert "health" in body

    def test_rejects_non_positive_target_amount(self, client):
        response = self._create(client, target_amount=0)
        assert response.status_code == 400

    def test_list_goals_defaults_to_active_only(self, client):
        self._seed(client)
        created = self._create(client).json()
        client.delete(f"/goals/{created['id']}")

        assert client.get("/goals").json() == []

        abandoned = client.get("/goals", params={"status": "abandoned"}).json()
        assert len(abandoned) == 1
        assert abandoned[0]["status"] == "abandoned"

    def test_patch_updates_current_saved_without_changing_capacity(self, client):
        self._seed(client)
        created = self._create(client).json()

        response = client.patch(f"/goals/{created['id']}", json={"current_saved": 100.0})
        assert response.status_code == 200
        body = response.json()
        assert body["current_saved"] == 100.0
        assert body["monthly_savings_capacity"] == created["monthly_savings_capacity"]

    def test_patch_404s_for_unknown_goal(self, client):
        response = client.patch("/goals/999", json={"current_saved": 10.0})
        assert response.status_code == 404

    def test_patch_rejects_non_positive_target_amount(self, client):
        self._seed(client)
        created = self._create(client).json()
        response = client.patch(f"/goals/{created['id']}", json={"target_amount": -5.0})
        assert response.status_code == 400

    def test_delete_abandons_goal(self, client):
        self._seed(client)
        created = self._create(client).json()

        response = client.delete(f"/goals/{created['id']}")
        assert response.status_code == 200
        assert response.json() == {"status": "abandoned"}

    def test_delete_404s_for_unknown_goal(self, client):
        response = client.delete("/goals/999")
        assert response.status_code == 404

    def test_health_endpoint_matches_embedded_health(self, client):
        self._seed(client)
        created = self._create(client).json()

        response = client.get(f"/goals/{created['id']}/health")
        assert response.status_code == 200
        assert response.json() == created["health"]

    def test_health_404s_for_unknown_goal(self, client):
        response = client.get("/goals/999/health")
        assert response.status_code == 404

    def test_different_users_have_independent_goals(self, client, auth_as):
        auth_as("user-1")
        self._seed(client)
        self._create(client)

        auth_as("user-2")
        assert client.get("/goals").json() == []


class TestAutoBudget:
    def _seed_and_create_goal(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-05-15",
                "name": "Whole Foods",
                "amount": 100.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-06-15",
                "name": "Whole Foods",
                "amount": 100.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
            {
                "transaction_id": "tx3",
                "date": "2026-07-20",
                "name": "Whole Foods",
                "amount": 50.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        client.post("/budget", json={"category": "Food", "amount": 300.0})
        goal = client.post("/goals", json={"name": "Vacation", "target_amount": 500.0, "category": "Food"}).json()

        # More spend after the goal was created, so current capacity (150)
        # drops below the frozen planned capacity (216.67) - required_cut > 0.
        # Bypass the sync cooldown for this second, same-test sync call - a
        # real user would just wait, but nothing here is testing the cooldown.
        _last_sync_at.clear()
        raw_more = raw + [
            {
                "transaction_id": "tx4",
                "date": "2026-07-25",
                "name": "Whole Foods",
                "amount": 200.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw_more, "modified": [], "removed": []}):
            client.post("/sync")

        return goal

    def test_not_needed_when_goal_is_on_pace(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-05-15",
                "name": "Whole Foods",
                "amount": 100.0,
                "personal_finance_category": {"primary": "FOOD_AND_DRINK"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        client.post("/budget", json={"category": "Food", "amount": 300.0})
        goal = client.post("/goals", json={"name": "Vacation", "target_amount": 500.0, "category": "Food"}).json()

        response = client.get(f"/goals/{goal['id']}/auto-budget")
        assert response.status_code == 200
        body = response.json()
        assert body["required_cut"] == 0.0
        assert body["suggestions"] == []
        assert body["source"] == "not_needed"

    def test_returns_suggestions_scaled_to_the_required_cut(self, client):
        goal = self._seed_and_create_goal(client)

        with patch(
            "app.main.recommend_budget_for_goal",
            return_value={
                "suggestions": [{"category": "Food", "suggested_budget": 200.0, "rationale": "Trim toward your goal."}],
                "summary": "Cutting Food gets you there.",
                "source": "ai",
                "error": None,
            },
        ) as mock_recommend:
            response = client.get(f"/goals/{goal['id']}/auto-budget")

        assert response.status_code == 200
        body = response.json()
        assert body["required_cut"] == 66.67
        assert body["suggestions"] == [{"category": "Food", "suggested_budget": 200.0, "rationale": "Trim toward your goal."}]
        assert body["source"] == "ai"
        # required_cut passed through to the allocator, not recomputed there.
        assert mock_recommend.call_args[0][1] == 66.67

    def test_404s_for_unknown_goal(self, client):
        response = client.get("/goals/999/auto-budget")
        assert response.status_code == 404

    def test_different_users_have_independent_auto_budgets(self, client, auth_as):
        auth_as("user-1")
        goal = self._seed_and_create_goal(client)

        auth_as("user-2")
        response = client.get(f"/goals/{goal['id']}/auto-budget")
        assert response.status_code == 404

    def test_second_call_within_cooldown_is_rate_limited(self, client):
        goal = self._seed_and_create_goal(client)
        with patch(
            "app.main.recommend_budget_for_goal",
            return_value={"suggestions": [], "summary": "x", "source": "none", "error": None},
        ):
            first = client.get(f"/goals/{goal['id']}/auto-budget")
            second = client.get(f"/goals/{goal['id']}/auto-budget")
        assert first.status_code == 200
        assert second.status_code == 429

    def test_housing_facts_only_fetched_when_housing_has_spend_history(self, client):
        goal = self._seed_and_create_goal(client)  # only Food has history here

        with patch("app.main.retrieve_housing_context") as retrieve_housing_context, patch(
            "app.main.recommend_budget_for_goal",
            return_value={"suggestions": [], "summary": "x", "source": "ai", "error": None},
        ):
            client.get(f"/goals/{goal['id']}/auto-budget")

        retrieve_housing_context.assert_not_called()

    def test_location_query_param_is_passed_through_to_housing_facts(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-15",
                "name": "Tectra Inc",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        goal = client.post("/goals", json={"name": "New home", "target_amount": 1000.0, "category": "Housing"}).json()

        with patch("app.main.retrieve_housing_context", return_value=[]) as retrieve_housing_context, patch(
            "app.main.recommend_budget_for_goal",
            return_value={"suggestions": [], "summary": "x", "source": "not_needed", "error": None},
        ):
            client.get(f"/goals/{goal['id']}/auto-budget", params={"location": "Austin, TX"})

        retrieve_housing_context.assert_called_once_with("Austin, TX")

    def test_no_location_param_still_fetches_national_facts(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-07-15",
                "name": "Tectra Inc",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            }
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")
        goal = client.post("/goals", json={"name": "New home", "target_amount": 1000.0, "category": "Housing"}).json()

        with patch("app.main.retrieve_housing_context", return_value=[]) as retrieve_housing_context, patch(
            "app.main.recommend_budget_for_goal",
            return_value={"suggestions": [], "summary": "x", "source": "not_needed", "error": None},
        ):
            client.get(f"/goals/{goal['id']}/auto-budget")

        retrieve_housing_context.assert_called_once_with("")


class TestBudgetRecommend:
    def test_no_history_returns_empty_recommendations(self, client):
        response = client.post("/budget/recommend", json={})
        assert response.status_code == 200
        body = response.json()
        assert body["recommendations"] == []
        assert body["source"] == "none"

    def test_returns_recommendations_from_history(self, client):
        _link_and_exchange(client)
        raw = [
            {
                "transaction_id": "tx1",
                "date": "2026-06-01",
                "name": "Rent",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            },
            {
                "transaction_id": "tx2",
                "date": "2026-07-01",
                "name": "Rent",
                "amount": 1500.0,
                "personal_finance_category": {"primary": "RENT_AND_UTILITIES"},
            },
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")

        with patch(
            "app.main.recommend_budgets",
            return_value={
                "recommendations": [
                    {"category": "Housing", "recommended_budget": 1500.0, "rationale": "Matches your last two months."}
                ],
                "summary": "One category with enough history to recommend.",
                "source": "ai",
                "error": None,
            },
        ) as mock_recommend:
            response = client.post("/budget/recommend", json={"months": 6})

        assert response.status_code == 200
        body = response.json()
        assert body["source"] == "ai"
        assert body["recommendations"][0]["category"] == "Housing"
        # The transactions passed in should carry the pre-computed category,
        # not force recommend_budgets to re-derive one from raw Plaid fields.
        passed_transactions = mock_recommend.call_args[0][0]
        assert all("category" in t for t in passed_transactions)

    def test_second_call_within_cooldown_is_rate_limited(self, client):
        with patch(
            "app.main.recommend_budgets",
            return_value={"recommendations": [], "summary": "x", "source": "none", "error": None},
        ):
            first = client.post("/budget/recommend", json={})
            second = client.post("/budget/recommend", json={})
        assert first.status_code == 200
        assert second.status_code == 429


class TestRecurring:
    def _seed_recurring(self, client, days_ago_list, amount=15.99, name="NETFLIX.COM", merchant_name="Netflix"):
        _link_and_exchange(client)
        today = datetime.now(timezone.utc).date()
        raw = [
            {
                "transaction_id": f"recurring-{i}",
                "date": (today - timedelta(days=d)).isoformat(),
                "name": name,
                "merchant_name": merchant_name,
                "amount": amount,
                "personal_finance_category": {"primary": "GENERAL_SERVICES"},
            }
            for i, d in enumerate(days_ago_list)
        ]
        with patch("app.main.fetch_transactions", return_value={"added": raw, "modified": [], "removed": []}):
            client.post("/sync")

    def test_detects_recurring_charge_from_synced_transactions(self, client):
        self._seed_recurring(client, [62, 32, 2])  # three ~30-day-apart charges
        response = client.get("/recurring")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["merchant"] == "Netflix"
        assert body[0]["average_amount"] == 15.99
        assert body[0]["occurrences"] == 3
        assert body[0]["impact_on_goals"] is None

    def test_verdict_is_comfortable_with_no_budget_set(self, client):
        self._seed_recurring(client, [62, 32, 2])
        assert client.get("/recurring").json()[0]["verdict"] == "comfortable"

    def test_verdict_is_comfortable_with_generous_budget(self, client):
        self._seed_recurring(client, [62, 32, 2])
        client.post("/budget", json={"category": "Subscriptions", "amount": 100.0})
        assert client.get("/recurring").json()[0]["verdict"] == "comfortable"

    def test_verdict_is_over_when_the_charge_alone_exceeds_its_budget(self, client):
        self._seed_recurring(client, [62, 32, 2])
        client.post("/budget", json={"category": "Subscriptions", "amount": 10.0})
        assert client.get("/recurring").json()[0]["verdict"] == "over"

    def test_verdict_is_tight_when_over_its_own_category_but_the_overall_budget_has_room(self, client):
        self._seed_recurring(client, [62, 32, 2])
        client.post("/budget", json={"category": "Subscriptions", "amount": 10.0})
        client.post("/budget", json={"category": "Food", "amount": 1000.0})
        assert client.get("/recurring").json()[0]["verdict"] == "tight"

    def test_no_recurring_charges_returns_empty_list(self, client):
        _link_and_exchange(client)
        response = client.get("/recurring")
        assert response.status_code == 200
        assert response.json() == []

    def test_a_single_charge_is_not_flagged_as_recurring(self, client):
        self._seed_recurring(client, [2])
        assert client.get("/recurring").json() == []

    def test_impact_on_goals_omitted_without_active_goals(self, client):
        self._seed_recurring(client, [62, 32, 2])
        assert client.get("/recurring").json()[0]["impact_on_goals"] is None

    def test_impact_on_goals_computed_for_an_active_goal(self, client):
        # Housing budget 30/mo with no Housing spend -> capacity 30/mo.
        # Redirecting a $20/mo charge -> capacity 50/mo. Goal gap 100 ->
        # 3.3 months at current pace, 2.0 months redirected -> 1.3 sooner.
        self._seed_recurring(client, [62, 32, 2], amount=20.0)
        client.post("/budget", json={"category": "Housing", "amount": 30.0})
        goal = client.post("/goals", json={"name": "Vacation", "target_amount": 100.0, "category": "Housing"}).json()

        response = client.get("/recurring")
        body = response.json()
        assert body[0]["impact_on_goals"] == [
            {
                "goal_id": goal["id"],
                "goal_name": "Vacation",
                "months_sooner": 1.3,
                "newly_reachable": False,
                "hypothetical_months_to_goal": 2.0,
            }
        ]

    def test_different_users_have_independent_recurring_charges(self, client, auth_as):
        auth_as("user-1")
        self._seed_recurring(client, [62, 32, 2])

        auth_as("user-2")
        assert client.get("/recurring").json() == []
