from datetime import date

import pytest

from app.affordability import check_purchase

STATUS = {
    "Entertainment": {"budget": 500.0, "actual": 402.0, "remaining": 98.0, "pct_used": 0.804, "status": "on_track"},
    "Housing": {"budget": 1500.0, "actual": 1450.0, "remaining": 50.0, "pct_used": 0.967, "status": "on_track"},
    "Food": {"budget": 700.0, "actual": 612.0, "remaining": 88.0, "pct_used": 0.874, "status": "on_track"},
    "Transport": {"budget": 400.0, "actual": 318.0, "remaining": 82.0, "pct_used": 0.795, "status": "on_track"},
    "Other": {"budget": 900.0, "actual": 268.0, "remaining": 632.0, "pct_used": 0.298, "status": "under"},
    "Subscriptions": {"budget": None, "actual": 164.0, "remaining": None, "pct_used": None, "status": "unbudgeted"},
}
TODAY = date(2026, 8, 7)


class TestCheckPurchase:
    def test_comfortable_when_both_category_and_overall_stay_positive(self):
        result = check_purchase(STATUS, 50, "Food", "one_time", today=TODAY)
        assert result["verdict"] == "comfortable"
        assert result["category_left_after"] == 38.0
        assert result["overall_left_after"] == 900.0

    def test_tight_when_category_goes_over_but_overall_stays_positive(self):
        result = check_purchase(STATUS, 480, "Entertainment", "one_time", today=TODAY)
        assert result["verdict"] == "tight"
        assert result["category_left_before"] == 98.0
        assert result["category_left_after"] == -382.0
        assert result["overall_left_after"] == 470.0

    def test_over_when_overall_also_goes_negative(self):
        result = check_purchase(STATUS, 2000, "Entertainment", "one_time", today=TODAY)
        assert result["verdict"] == "over"
        assert result["overall_left_after"] == -1050.0

    def test_split_3_divides_by_three_and_can_change_the_verdict(self):
        lump_sum = check_purchase(STATUS, 480, "Entertainment", "one_time", today=TODAY)
        split = check_purchase(STATUS, 480, "Entertainment", "split_3", today=TODAY)

        assert split["effective_amount"] == 160.0
        assert split["split_monthly"] == 160.0
        # Same $480 purchase: still tight split three ways (still over the
        # $98 left in Entertainment for one month), but far less over than lump sum.
        assert split["verdict"] == "tight"
        assert split["category_left_after"] == -62.0
        assert split["category_left_after"] > lump_sum["category_left_after"]

    def test_split_monthly_is_always_reported_regardless_of_chosen_timing(self):
        result = check_purchase(STATUS, 480, "Entertainment", "one_time", today=TODAY)
        assert result["split_monthly"] == 160.0

    def test_unbudgeted_category_falls_back_to_overall_only(self):
        result = check_purchase(STATUS, 50, "Subscriptions", "one_time", today=TODAY)
        assert result["category_left_before"] is None
        assert result["category_left_after"] is None
        assert result["verdict"] == "comfortable"

    def test_category_not_in_status_at_all_behaves_like_unbudgeted(self):
        result = check_purchase(STATUS, 50, "Vacation", "one_time", today=TODAY)
        assert result["category_left_before"] is None
        assert result["verdict"] == "comfortable"

    def test_no_budgets_anywhere_is_comfortable_not_over(self):
        # A brand-new user with zero budgets set has nothing to compare a
        # purchase against - that should not read as "over budget".
        empty_status: dict = {}
        result = check_purchase(empty_status, 50, "Food", "one_time", today=TODAY)
        assert result["verdict"] == "comfortable"
        assert result["overall_left_before"] == 0.0

    def test_unknown_timing_raises(self):
        with pytest.raises(ValueError):
            check_purchase(STATUS, 50, "Food", "yearly", today=TODAY)

    def test_days_remaining_counts_today(self):
        result = check_purchase(STATUS, 50, "Food", "one_time", today=date(2026, 8, 31))
        assert result["days_remaining"] == 1

    def test_safe_to_spend_today(self):
        result = check_purchase(STATUS, 50, "Food", "one_time", today=TODAY)
        assert result["safe_to_spend_today"] == 38.0

    def test_effect_on_pace_is_none_when_nothing_spent_yet(self):
        empty_status = {"Food": {"budget": 700.0, "actual": 0.0, "remaining": 700.0, "pct_used": 0.0, "status": "under"}}
        result = check_purchase(empty_status, 50, "Food", "one_time", today=TODAY)
        assert result["effect_on_pace_pct"] is None
