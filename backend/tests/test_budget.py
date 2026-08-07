import pytest

from app.budget import budget_status, monthly_spend_by_category, spending_trend


class TestMonthlySpendByCategory:
    def test_may_totals(self, sandbox_transactions_by_month):
        result = monthly_spend_by_category(sandbox_transactions_by_month["2026-05"])
        assert result == {
            "Housing": 1620.0,
            "Food": 147.7,
            "Transport": 67.15,
            "Subscriptions": 26.48,
            "Entertainment": 32.0,
            "Other": -3000.0,
        }

    def test_july_totals_include_negative_transport_from_refund(self, sandbox_transactions_by_month):
        result = monthly_spend_by_category(sandbox_transactions_by_month["2026-07"])
        assert result["Transport"] == -91.5
        assert result["Subscriptions"] == 70.48

    def test_empty_transactions(self):
        assert monthly_spend_by_category([]) == {}


class TestBudgetStatus:
    def test_over_budget(self):
        result = budget_status({"Food": 100.0}, {"Food": 150.0})
        assert result["Food"]["status"] == "over"
        assert result["Food"]["remaining"] == -50.0

    def test_on_track_when_near_but_under_budget(self):
        result = budget_status({"Food": 100.0}, {"Food": 95.0})
        assert result["Food"]["status"] == "on_track"
        assert result["Food"]["pct_used"] == pytest.approx(0.95)

    def test_under_budget(self):
        result = budget_status({"Food": 100.0}, {"Food": 50.0})
        assert result["Food"]["status"] == "under"
        assert result["Food"]["pct_used"] == pytest.approx(0.5)

    def test_borderline_at_on_track_threshold(self):
        result = budget_status({"Food": 100.0}, {"Food": 90.0})
        assert result["Food"]["status"] == "on_track"

    def test_unbudgeted_category_is_flagged_not_dropped(self):
        result = budget_status({"Food": 100.0}, {"Food": 50.0, "Entertainment": 40.0})
        assert result["Entertainment"]["status"] == "unbudgeted"
        assert result["Entertainment"]["budget"] is None
        assert result["Entertainment"]["actual"] == 40.0

    def test_budgeted_category_with_no_spend_yet(self):
        result = budget_status({"Food": 100.0}, {})
        assert result["Food"] == {
            "budget": 100.0,
            "actual": 0.0,
            "remaining": 100.0,
            "pct_used": 0.0,
            "status": "under",
        }

    def test_multiple_categories_from_fixture(self, sandbox_transactions_by_month):
        actual = monthly_spend_by_category(sandbox_transactions_by_month["2026-05"])
        budgets = {"Housing": 1600.0, "Food": 200.0, "Transport": 100.0}
        result = budget_status(budgets, actual)

        assert result["Housing"]["status"] == "over"  # 1620 > 1600
        assert result["Food"]["status"] == "under"  # 147.70 / 200 = 0.74
        assert result["Transport"]["status"] == "under"  # 67.15 / 100 = 0.67


class TestSpendingTrend:
    def test_months_are_sorted_and_limited(self, sandbox_transactions):
        result = spending_trend(sandbox_transactions, months=2)
        assert result["months"] == ["2026-06", "2026-07"]

    def test_all_three_months_present(self, sandbox_transactions):
        result = spending_trend(sandbox_transactions, months=3)
        assert result["months"] == ["2026-05", "2026-06", "2026-07"]

    def test_by_category_series_matches_monthly_totals(self, sandbox_transactions):
        result = spending_trend(sandbox_transactions, months=3)
        assert result["by_category"]["Housing"] == {
            "2026-05": 1620.0,
            "2026-06": 1635.0,
            "2026-07": 1500.0,
        }
        assert result["by_category"]["Subscriptions"] == {
            "2026-05": 26.48,
            "2026-06": 26.48,
            "2026-07": 70.48,
        }

    def test_change_from_previous_month(self, sandbox_transactions):
        result = spending_trend(sandbox_transactions, months=3)
        change = result["change_from_previous_month"]

        assert change["Housing"] == {
            "previous": 1635.0,
            "current": 1500.0,
            "change": -135.0,
            "change_pct": -8.26,
        }
        assert change["Subscriptions"] == {
            "previous": 26.48,
            "current": 70.48,
            "change": 44.0,
            "change_pct": 166.16,
        }
        assert change["Transport"]["change"] == -169.5

    def test_single_month_has_no_change(self, sandbox_transactions_by_month):
        result = spending_trend(sandbox_transactions_by_month["2026-05"], months=3)
        assert result["months"] == ["2026-05"]
        assert result["change_from_previous_month"] == {}

    def test_no_transactions(self):
        result = spending_trend([], months=3)
        assert result == {"months": [], "by_category": {}, "change_from_previous_month": {}}
