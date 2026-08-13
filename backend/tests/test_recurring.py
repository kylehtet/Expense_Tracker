from datetime import date

from app.recurring import detect_recurring_charges

TODAY = date(2026, 8, 11)


class TestDetectRecurringCharges:
    def test_detects_a_clear_monthly_subscription(self):
        txns = [
            {"date": "2026-05-05", "amount": 15.99, "category": "Subscriptions", "name": "NETFLIX.COM", "merchant_name": "Netflix"},
            {"date": "2026-06-04", "amount": 15.99, "category": "Subscriptions", "name": "NETFLIX.COM", "merchant_name": "Netflix"},
            {"date": "2026-07-05", "amount": 15.99, "category": "Subscriptions", "name": "NETFLIX.COM", "merchant_name": "Netflix"},
        ]
        result = detect_recurring_charges(txns, today=TODAY)
        assert len(result) == 1
        assert result[0] == {
            "merchant": "Netflix",
            "average_amount": 15.99,
            "category": "Subscriptions",
            "occurrences": 3,
            "first_seen": "2026-05-05",
            "last_charged": "2026-07-05",
            "next_charge_estimate": "2026-08-04",
        }

    def test_a_single_one_off_purchase_does_not_match(self):
        txns = [
            {"date": "2026-06-15", "amount": 250.0, "category": "Other", "name": "BEST BUY", "merchant_name": "Best Buy"},
        ]
        assert detect_recurring_charges(txns, today=TODAY) == []

    def test_matches_a_slowly_drifting_amount_within_tolerance(self):
        # A utility bill that creeps up each month should still chain, since
        # tolerance is checked against the chain's running average, not a
        # fixed first-charge amount.
        txns = [
            {"date": "2026-05-10", "amount": 82.0, "category": "Housing", "name": "CITY POWER", "merchant_name": "City Power & Light"},
            {"date": "2026-06-09", "amount": 84.0, "category": "Housing", "name": "CITY POWER", "merchant_name": "City Power & Light"},
            {"date": "2026-07-11", "amount": 86.0, "category": "Housing", "name": "CITY POWER", "merchant_name": "City Power & Light"},
        ]
        result = detect_recurring_charges(txns, today=TODAY)
        assert len(result) == 1
        assert result[0]["occurrences"] == 3
        assert result[0]["average_amount"] == 84.0
        assert result[0]["next_charge_estimate"] == "2026-08-11"

    def test_weekly_cadence_does_not_match_monthly_pattern(self):
        txns = [
            {"date": "2026-06-01", "amount": 20.0, "category": "Food", "name": "COFFEE SHOP"},
            {"date": "2026-06-08", "amount": 20.0, "category": "Food", "name": "COFFEE SHOP"},
            {"date": "2026-06-15", "amount": 20.0, "category": "Food", "name": "COFFEE SHOP"},
        ]
        assert detect_recurring_charges(txns, today=TODAY) == []

    def test_amount_drift_beyond_tolerance_breaks_the_chain(self):
        txns = [
            {"date": "2026-05-05", "amount": 10.0, "category": "Other", "name": "SHOP"},
            {"date": "2026-06-05", "amount": 20.0, "category": "Other", "name": "SHOP"},
        ]
        assert detect_recurring_charges(txns, today=TODAY) == []

    def test_merchant_name_normalization_merges_case_and_whitespace_variants(self):
        txns = [
            {"date": "2026-05-05", "amount": 9.99, "category": "Subscriptions", "name": "spotify  usa"},
            {"date": "2026-06-05", "amount": 9.99, "category": "Subscriptions", "name": "  Spotify USA"},
        ]
        result = detect_recurring_charges(txns, today=TODAY)
        assert len(result) == 1
        assert result[0]["merchant"] == "Spotify USA"
        assert result[0]["occurrences"] == 2

    def test_charges_outside_the_lookback_window_are_ignored(self):
        txns = [
            {"date": "2025-10-01", "amount": 12.0, "category": "Subscriptions", "name": "OLD SVC"},
            {"date": "2025-11-01", "amount": 12.0, "category": "Subscriptions", "name": "OLD SVC"},
        ]
        assert detect_recurring_charges(txns, months=6, today=TODAY) == []

    def test_refunds_do_not_count_as_charges(self):
        txns = [
            {"date": "2026-06-01", "amount": 30.0, "category": "Other", "name": "STORE"},
            {"date": "2026-07-01", "amount": -30.0, "category": "Other", "name": "STORE"},
        ]
        assert detect_recurring_charges(txns, today=TODAY) == []

    def test_falls_back_to_name_when_merchant_name_is_missing(self):
        txns = [
            {"date": "2026-05-05", "amount": 5.0, "category": "Other", "name": "Generic Store", "merchant_name": None},
            {"date": "2026-06-05", "amount": 5.0, "category": "Other", "name": "Generic Store", "merchant_name": None},
        ]
        result = detect_recurring_charges(txns, today=TODAY)
        assert len(result) == 1
        assert result[0]["merchant"] == "Generic Store"

    def test_results_sorted_by_most_recently_charged_first(self):
        txns = [
            {"date": "2026-04-01", "amount": 10.0, "category": "Other", "name": "OLDER SUB"},
            {"date": "2026-05-01", "amount": 10.0, "category": "Other", "name": "OLDER SUB"},
            {"date": "2026-07-01", "amount": 20.0, "category": "Other", "name": "NEWER SUB"},
            {"date": "2026-08-01", "amount": 20.0, "category": "Other", "name": "NEWER SUB"},
        ]
        result = detect_recurring_charges(txns, today=TODAY)
        assert [r["merchant"] for r in result] == ["NEWER SUB", "OLDER SUB"]

    def test_no_transactions_returns_empty_list(self):
        assert detect_recurring_charges([], today=TODAY) == []
