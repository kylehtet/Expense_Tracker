from datetime import date

from app.goal_tracker import (
    check_goal_health,
    compute_monthly_savings_capacity,
    compute_savings_plan,
    plan_from_affordability_check,
)

BUDGETS = {"Housing": 1500.0, "Food": 300.0, "Transport": 550.0, "Entertainment": 100.0}
TODAY = date(2026, 8, 7)


def _txn(date_, category, amount):
    return {"date": date_, "category": category, "amount": amount}


def _months(monthly_amounts: dict) -> list:
    """Builds 3 months (2026-05..07) of transactions from
    {category: amount_per_month}, one transaction per category per month."""
    txns = []
    for m in ["2026-05", "2026-06", "2026-07"]:
        for category, amount in monthly_amounts.items():
            txns.append(_txn(f"{m}-10", category, amount))
    return txns


ON_PACE_TXNS = _months({"Housing": 1500.0, "Food": 280.0, "Transport": 500.0, "Entertainment": 90.0})
ENTERTAINMENT_OVERSPEND_TXNS = _months({"Housing": 1500.0, "Food": 280.0, "Transport": 500.0, "Entertainment": 400.0})
GENERAL_OVERSPEND_TXNS = _months({"Housing": 1500.0, "Food": 400.0, "Transport": 700.0, "Entertainment": 90.0})
AHEAD_TXNS = _months({"Housing": 1400.0, "Food": 200.0, "Transport": 400.0, "Entertainment": 50.0})


class TestComputeMonthlySavingsCapacity:
    def test_matches_hand_computed_surplus(self):
        # Total budget 2450, actual spend/month 1500+280+500+90=2370 -> surplus 80.
        assert compute_monthly_savings_capacity(BUDGETS, ON_PACE_TXNS) == 80.0

    def test_negative_when_overspending(self):
        # Actual 1500+280+500+400=2680 vs budget 2450 -> deficit -230.
        assert compute_monthly_savings_capacity(BUDGETS, ENTERTAINMENT_OVERSPEND_TXNS) == -230.0

    def test_zero_with_no_budgets_set(self):
        assert compute_monthly_savings_capacity({}, ON_PACE_TXNS) == 0.0

    def test_zero_with_no_transaction_history(self):
        assert compute_monthly_savings_capacity(BUDGETS, []) == 0.0


class TestComputeSavingsPlan:
    def test_computes_gap_and_months_to_goal(self):
        plan = compute_savings_plan(target_amount=1000.0, current_saved=0.0, monthly_savings_capacity=80.0)
        assert plan == {"gap": 1000.0, "monthly_savings_capacity": 80.0, "months_to_goal": 12.5}

    def test_gap_never_goes_negative_if_already_saved_enough(self):
        plan = compute_savings_plan(target_amount=500.0, current_saved=600.0, monthly_savings_capacity=80.0)
        assert plan["gap"] == 0.0
        assert plan["months_to_goal"] == 0.0

    def test_months_to_goal_is_none_with_zero_or_negative_capacity(self):
        plan = compute_savings_plan(target_amount=1000.0, current_saved=0.0, monthly_savings_capacity=0.0)
        assert plan["months_to_goal"] is None
        plan_negative = compute_savings_plan(target_amount=1000.0, current_saved=0.0, monthly_savings_capacity=-50.0)
        assert plan_negative["months_to_goal"] is None


class TestPlanFromAffordabilityCheck:
    def test_reuses_the_same_capacity_math_as_a_fresh_goal(self):
        plan = plan_from_affordability_check(1200.0, BUDGETS, ON_PACE_TXNS)
        assert plan["monthly_savings_capacity"] == compute_monthly_savings_capacity(BUDGETS, ON_PACE_TXNS)
        assert plan == {"gap": 1200.0, "monthly_savings_capacity": 80.0, "months_to_goal": 15.0}


class TestCheckGoalHealth:
    def test_goal_already_achieved(self):
        goal = {
            "target_amount": 500.0,
            "current_saved": 500.0,
            "category": "Entertainment",
            "monthly_savings_capacity": 100.0,
            "target_date": None,
        }
        health = check_goal_health(goal, BUDGETS, ON_PACE_TXNS, today=TODAY)
        assert health["on_track"] is True
        assert health["reason"] == "goal_achieved"
        assert health["projected_shortfall"] == 0.0
        assert health["projected_completion_date"] is None

    def test_on_pace_when_actual_matches_plan(self):
        goal = {
            "target_amount": 1000.0,
            "current_saved": 200.0,
            "category": "Entertainment",
            "monthly_savings_capacity": 80.0,  # same fixture used to plan and to check
            "target_date": None,
        }
        health = check_goal_health(goal, BUDGETS, ON_PACE_TXNS, today=TODAY)
        assert health["on_track"] is True
        assert health["pace_status"] == "on_pace"
        assert health["reason"] == "on_pace"
        assert health["projected_shortfall"] == 0.0
        assert health["projected_completion_date"] == "2027-06-01"

    def test_behind_pace_names_the_overspending_category_when_concentrated_there(self):
        goal = {
            "target_amount": 1000.0,
            "current_saved": 200.0,
            "category": "Entertainment",
            "monthly_savings_capacity": 80.0,  # planned pace, from before the overspend started
            "target_date": None,
        }
        health = check_goal_health(goal, BUDGETS, ENTERTAINMENT_OVERSPEND_TXNS, today=TODAY)
        assert health["on_track"] is False
        assert health["pace_status"] == "behind"
        assert health["reason"] == "entertainment_overspend"
        assert health["projected_shortfall"] > 0
        # Negative current capacity means no forward progress - no ETA to report.
        assert health["projected_completion_date"] is None

    def test_behind_pace_is_general_when_overspend_is_not_in_the_goals_own_category(self):
        goal = {
            "target_amount": 1000.0,
            "current_saved": 200.0,
            "category": "Entertainment",  # this category is actually under budget here
            "monthly_savings_capacity": 80.0,
            "target_date": None,
        }
        health = check_goal_health(goal, BUDGETS, GENERAL_OVERSPEND_TXNS, today=TODAY)
        assert health["on_track"] is False
        assert health["pace_status"] == "behind"
        assert health["reason"] == "general_overspend"

    def test_ahead_of_pace_when_spending_well_under_budget(self):
        goal = {
            "target_amount": 1000.0,
            "current_saved": 200.0,
            "category": "Entertainment",
            "monthly_savings_capacity": 80.0,
            "target_date": None,
        }
        health = check_goal_health(goal, BUDGETS, AHEAD_TXNS, today=TODAY)
        assert health["on_track"] is True
        assert health["pace_status"] == "ahead"
        assert health["reason"] == "ahead_of_pace"
        assert health["projected_shortfall"] == 0.0

    def test_projected_shortfall_uses_target_date_when_given(self):
        goal = {
            "target_amount": 1000.0,
            "current_saved": 0.0,
            "category": "Entertainment",
            "monthly_savings_capacity": 80.0,
            "target_date": "2026-09-07",  # 1 month out from TODAY
        }
        health = check_goal_health(goal, BUDGETS, ENTERTAINMENT_OVERSPEND_TXNS, today=TODAY)
        # Current capacity is negative, so nothing gets saved by the target
        # date - the full $1000 gap is projected as a shortfall.
        assert health["projected_shortfall"] == 1000.0
