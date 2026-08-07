from datetime import date

import pytest

from app.rules import (
    FRONT_END_LIMIT,
    car_affordability,
    general_purchase_affordability,
    housing_affordability,
    rent_affordability,
    savings_goal_plan,
)


class TestHousingAffordability:
    def test_affordable(self):
        result = housing_affordability(120000, 300000, 60000, 0.065, 0.012, 1500)
        assert result["affordable"] is True
        assert result["front_end_ratio"] == pytest.approx(0.1942, abs=0.001)
        assert result["monthly_payment_estimate"] == pytest.approx(1941.96, abs=0.5)

    def test_borderline_just_under_threshold(self):
        result = housing_affordability(90000, 288000, 20000, 0.065, 0.012, 1400)
        assert result["front_end_ratio"] == pytest.approx(0.28, abs=0.005)
        assert result["affordable"] is True

    def test_borderline_just_over_threshold(self):
        result = housing_affordability(90000, 290000, 20000, 0.065, 0.012, 1400)
        assert result["front_end_ratio"] == pytest.approx(0.28, abs=0.005)
        assert result["affordable"] is False

    def test_not_affordable(self):
        result = housing_affordability(60000, 500000, 20000, 0.07, 0.012, 1800)
        assert result["affordable"] is False
        assert result["front_end_ratio"] > FRONT_END_LIMIT

    def test_max_affordable_price_is_self_consistent(self):
        result = housing_affordability(90000, 300000, 20000, 0.065, 0.012, 1400)
        check = housing_affordability(
            90000, result["max_affordable_price"], 20000, 0.065, 0.012, 1400
        )
        assert check["front_end_ratio"] == pytest.approx(0.28, abs=0.005)

    def test_dti_includes_other_debts(self):
        no_debt = housing_affordability(90000, 200000, 40000, 0.06, 0.01, 1200)
        with_debt = housing_affordability(
            90000, 200000, 40000, 0.06, 0.01, 1200, other_monthly_debts=1000
        )
        assert with_debt["dti_ratio"] > no_debt["dti_ratio"]
        assert with_debt["front_end_ratio"] == no_debt["front_end_ratio"]


class TestRentAffordability:
    def test_affordable(self):
        result = rent_affordability(60000, 1200)
        assert result["affordable"] is True
        assert result["ratio"] == pytest.approx(0.24)

    def test_borderline_at_threshold(self):
        result = rent_affordability(48000, 1200)
        assert result["ratio"] == pytest.approx(0.30)
        assert result["affordable"] is True

    def test_not_affordable(self):
        result = rent_affordability(36000, 1500)
        assert result["affordable"] is False
        assert result["ratio"] == pytest.approx(0.5)

    def test_max_affordable_rent_matches_limit(self):
        result = rent_affordability(60000, 1200)
        assert result["max_affordable_rent"] == pytest.approx(1500.0)


class TestCarAffordability:
    def test_affordable(self):
        result = car_affordability(60000, 25000, 5000, 0.06, 60)
        assert result["affordable"] is True
        assert result["ratio"] == pytest.approx(0.1031, abs=0.001)

    def test_borderline(self):
        result = car_affordability(45000, 25000, 2000, 0.07, 60)
        assert result["ratio"] == pytest.approx(0.1619, abs=0.001)
        assert result["affordable"] is False
        assert result["comfortable"] is False

    def test_not_affordable(self):
        result = car_affordability(30000, 35000, 1000, 0.08, 60)
        assert result["affordable"] is False
        assert result["ratio"] == pytest.approx(0.3677, abs=0.001)

    def test_comfortable_flag_stricter_than_affordable(self):
        very_cheap = car_affordability(80000, 12000, 6000, 0.05, 48)
        assert very_cheap["comfortable"] is True
        assert very_cheap["affordable"] is True

    def test_max_affordable_price_is_self_consistent(self):
        result = car_affordability(60000, 25000, 5000, 0.06, 60)
        check = car_affordability(60000, result["max_affordable_price"], 5000, 0.06, 60)
        assert check["ratio"] == pytest.approx(0.15, abs=0.001)


class TestGeneralPurchaseAffordability:
    def test_affordable(self):
        result = general_purchase_affordability(80000, 20000, 3000, 3000)
        assert result["affordable"] is True
        assert result["emergency_fund_shortfall"] == 0.0

    def test_borderline_exact_three_months_remaining(self):
        result = general_purchase_affordability(80000, 12000, 3000, 3000)
        assert result["remaining_savings_after_purchase"] == pytest.approx(9000)
        assert result["emergency_fund_threshold"] == pytest.approx(9000)
        assert result["affordable"] is True

    def test_not_affordable(self):
        result = general_purchase_affordability(80000, 10000, 3000, 5000)
        assert result["affordable"] is False
        assert result["emergency_fund_shortfall"] == pytest.approx(4000)

    def test_zero_expenses_does_not_divide_by_zero(self):
        result = general_purchase_affordability(80000, 10000, 0, 5000)
        assert result["months_of_expenses_remaining"] == float("inf")


class TestSavingsGoalPlan:
    def test_already_affordable(self):
        result = savings_goal_plan(10000, 12000, 5000)
        assert result["already_affordable"] is True
        assert result["gap"] == 0.0
        assert result["months_to_goal"] == 0

    def test_borderline_reaches_goal_in_one_month(self):
        result = savings_goal_plan(11000, 10000, 5000, savings_rate=0.20, today=date(2026, 1, 15))
        assert result["gap"] == pytest.approx(1000.0)
        assert result["months_to_goal"] == 1
        assert result["target_date"] == "2026-02-15"

    def test_not_affordable_needs_multiple_months(self):
        result = savings_goal_plan(
            30000, 5000, 6000, savings_rate=0.20, today=date(2026, 1, 15)
        )
        assert result["gap"] == pytest.approx(25000)
        assert result["months_to_goal"] == 21
        assert result["target_date"] == "2027-10-15"

    def test_zero_savings_capacity_returns_none(self):
        result = savings_goal_plan(30000, 5000, 0, savings_rate=0.20)
        assert result["months_to_goal"] is None
        assert result["target_date"] is None

    def test_custom_savings_rate_changes_capacity(self):
        low_rate = savings_goal_plan(30000, 5000, 6000, savings_rate=0.10)
        high_rate = savings_goal_plan(30000, 5000, 6000, savings_rate=0.30)
        assert low_rate["monthly_savings_capacity"] < high_rate["monthly_savings_capacity"]
        assert low_rate["months_to_goal"] > high_rate["months_to_goal"]
