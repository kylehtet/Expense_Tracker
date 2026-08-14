from datetime import date

from app.income import detect_recurring_income, estimate_annual_income

TODAY = date(2026, 8, 11)


class TestDetectRecurringIncome:
    def test_detects_a_biweekly_paycheck(self):
        txns = [
            {"date": "2026-06-05", "amount": -2307.50, "category": "Other", "name": "ACME CORP PAYROLL", "merchant_name": "Acme Corp"},
            {"date": "2026-06-19", "amount": -2307.50, "category": "Other", "name": "ACME CORP PAYROLL", "merchant_name": "Acme Corp"},
            {"date": "2026-07-03", "amount": -2307.50, "category": "Other", "name": "ACME CORP PAYROLL", "merchant_name": "Acme Corp"},
        ]
        result = detect_recurring_income(txns, today=TODAY)
        assert len(result) == 1
        assert result[0] == {
            "source": "Acme Corp",
            "average_amount": 2307.50,
            "average_interval_days": 14,
            "occurrences": 3,
            "last_received": "2026-07-03",
        }

    def test_ignores_expenses_and_a_single_deposit(self):
        txns = [
            {"date": "2026-06-15", "amount": 45.0, "category": "Food", "name": "WHOLE FOODS", "merchant_name": "Whole Foods"},
            {"date": "2026-06-01", "amount": -500.0, "category": "Other", "name": "VENMO", "merchant_name": "Venmo"},
        ]
        assert detect_recurring_income(txns, today=TODAY) == []

    def test_two_separate_income_streams_both_detected(self):
        txns = [
            {"date": "2026-05-01", "amount": -3000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job LLC"},
            {"date": "2026-06-01", "amount": -3000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job LLC"},
            {"date": "2026-07-01", "amount": -3000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job LLC"},
            {"date": "2026-06-08", "amount": -400.0, "category": "Other", "name": "SIDE GIG", "merchant_name": "Side Gig Inc"},
            {"date": "2026-07-06", "amount": -400.0, "category": "Other", "name": "SIDE GIG", "merchant_name": "Side Gig Inc"},
        ]
        result = detect_recurring_income(txns, today=TODAY)
        sources = {r["source"] for r in result}
        assert sources == {"Main Job LLC", "Side Gig Inc"}


class TestEstimateAnnualIncome:
    def test_biweekly_paycheck_annualizes_at_26_periods(self):
        txns = [
            {"date": "2026-06-05", "amount": -2000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-06-19", "amount": -2000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-07-03", "amount": -2000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
        ]
        result = estimate_annual_income(txns, today=TODAY)
        assert result["estimated_annual_income"] == 52000.0
        assert result["income_sources"][0]["periods_per_year"] == 26
        assert result["income_sources"][0]["estimated_annual"] == 52000.0

    def test_weekly_paycheck_annualizes_at_52_periods(self):
        txns = [
            {"date": "2026-06-05", "amount": -1000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-06-12", "amount": -1000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-06-19", "amount": -1000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
        ]
        result = estimate_annual_income(txns, today=TODAY)
        assert result["income_sources"][0]["periods_per_year"] == 52
        assert result["estimated_annual_income"] == 52000.0

    def test_monthly_paycheck_annualizes_at_12_periods(self):
        txns = [
            {"date": "2026-05-01", "amount": -5000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-06-01", "amount": -5000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
            {"date": "2026-07-01", "amount": -5000.0, "category": "Other", "name": "PAYROLL", "merchant_name": "Employer"},
        ]
        result = estimate_annual_income(txns, today=TODAY)
        assert result["income_sources"][0]["periods_per_year"] == 12
        assert result["estimated_annual_income"] == 60000.0

    def test_multiple_streams_are_summed(self):
        txns = [
            {"date": "2026-05-01", "amount": -4000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job"},
            {"date": "2026-06-01", "amount": -4000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job"},
            {"date": "2026-07-01", "amount": -4000.0, "category": "Other", "name": "MAIN JOB", "merchant_name": "Main Job"},
            {"date": "2026-06-08", "amount": -500.0, "category": "Other", "name": "SIDE GIG", "merchant_name": "Side Gig"},
            {"date": "2026-07-06", "amount": -500.0, "category": "Other", "name": "SIDE GIG", "merchant_name": "Side Gig"},
        ]
        result = estimate_annual_income(txns, today=TODAY)
        assert result["estimated_annual_income"] == 48000.0 + 6000.0

    def test_no_income_history_returns_zero(self):
        result = estimate_annual_income([], today=TODAY)
        assert result == {"estimated_annual_income": 0.0, "income_sources": []}
