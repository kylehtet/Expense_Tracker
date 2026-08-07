"""Deterministic affordability rules engine. No LLM calls in this module."""

from __future__ import annotations

import math
from datetime import date

FRONT_END_LIMIT = 0.28   # housing / gross income (28/36 rule)
BACK_END_LIMIT = 0.36    # total debt / gross income (28/36 rule)
RENT_LIMIT = 0.30        # rent / gross income
CAR_MAX_LIMIT = 0.15     # car payment / take-home pay, upper bound of 10-15% rule
CAR_COMFORT_LIMIT = 0.10 # car payment / take-home pay, lower bound of 10-15% rule
EMERGENCY_FUND_MONTHS = 3


def _monthly_payment(loan_amount: float, annual_rate: float, term_months: int) -> float:
    if loan_amount <= 0 or term_months <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return loan_amount / term_months
    factor = (1 + monthly_rate) ** term_months
    return loan_amount * monthly_rate * factor / (factor - 1)


def _loan_amount_for_payment(payment: float, annual_rate: float, term_months: int) -> float:
    if payment <= 0 or term_months <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    if monthly_rate == 0:
        return payment * term_months
    factor = (1 + monthly_rate) ** term_months
    return payment * (factor - 1) / (monthly_rate * factor)


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, 28)
    return date(year, month, day)


def housing_affordability(
    income: float,
    price: float,
    down_payment: float,
    interest_rate: float,
    property_tax_rate: float,
    insurance_estimate: float,
    loan_term_months: int = 360,
    other_monthly_debts: float = 0.0,
) -> dict:
    """income: annual gross income. interest_rate/property_tax_rate: annual decimals
    (0.065 = 6.5%). insurance_estimate: annual dollar cost."""
    monthly_income = income / 12
    loan_amount = max(price - down_payment, 0.0)

    monthly_principal_interest = _monthly_payment(loan_amount, interest_rate, loan_term_months)
    monthly_property_tax = price * property_tax_rate / 12
    monthly_insurance = insurance_estimate / 12
    monthly_payment_estimate = (
        monthly_principal_interest + monthly_property_tax + monthly_insurance
    )

    front_end_ratio = monthly_payment_estimate / monthly_income
    dti_ratio = (monthly_payment_estimate + other_monthly_debts) / monthly_income
    affordable = front_end_ratio <= FRONT_END_LIMIT and dti_ratio <= BACK_END_LIMIT

    # Insurance is given as a fixed dollar estimate for the requested price, but to
    # solve for a *different* max price we need a rate, so we scale it proportionally.
    insurance_rate = insurance_estimate / price if price > 0 else 0.0
    housing_budget = max(monthly_income * FRONT_END_LIMIT, 0.0)
    debt_budget = max(monthly_income * BACK_END_LIMIT - other_monthly_debts, 0.0)
    max_monthly_housing_payment = min(housing_budget, debt_budget)

    monthly_rate = interest_rate / 12
    if monthly_rate == 0:
        pi_coefficient = 1 / loan_term_months
    else:
        factor = (1 + monthly_rate) ** loan_term_months
        pi_coefficient = monthly_rate * factor / (factor - 1)
    tax_insurance_coefficient = (property_tax_rate + insurance_rate) / 12
    denominator = tax_insurance_coefficient + pi_coefficient
    max_affordable_price = (
        (max_monthly_housing_payment + down_payment * pi_coefficient) / denominator
        if denominator > 0
        else 0.0
    )
    max_affordable_price = max(max_affordable_price, 0.0)

    return {
        "affordable": affordable,
        "max_affordable_price": round(max_affordable_price, 2),
        "monthly_payment_estimate": round(monthly_payment_estimate, 2),
        "monthly_principal_interest": round(monthly_principal_interest, 2),
        "monthly_property_tax": round(monthly_property_tax, 2),
        "monthly_insurance": round(monthly_insurance, 2),
        "monthly_income": round(monthly_income, 2),
        "front_end_ratio": round(front_end_ratio, 4),
        "dti_ratio": round(dti_ratio, 4),
        "front_end_limit": FRONT_END_LIMIT,
        "back_end_limit": BACK_END_LIMIT,
    }


def rent_affordability(income: float, monthly_rent: float) -> dict:
    monthly_income = income / 12
    ratio = monthly_rent / monthly_income
    max_affordable_rent = monthly_income * RENT_LIMIT
    affordable = ratio <= RENT_LIMIT

    return {
        "affordable": affordable,
        "ratio": round(ratio, 4),
        "max_affordable_rent": round(max_affordable_rent, 2),
        "monthly_income": round(monthly_income, 2),
        "limit": RENT_LIMIT,
    }


def car_affordability(
    income: float,
    price: float,
    down_payment: float,
    interest_rate: float,
    loan_term_months: int,
    take_home_multiplier: float = 0.75,
) -> dict:
    """income: annual gross income. take_home_multiplier estimates take-home pay
    as a fraction of gross when actual take-home isn't provided."""
    monthly_take_home = income * take_home_multiplier / 12
    loan_amount = max(price - down_payment, 0.0)
    monthly_payment_estimate = _monthly_payment(loan_amount, interest_rate, loan_term_months)

    ratio = monthly_payment_estimate / monthly_take_home
    affordable = ratio <= CAR_MAX_LIMIT
    comfortable = ratio <= CAR_COMFORT_LIMIT

    max_monthly_payment = monthly_take_home * CAR_MAX_LIMIT
    max_loan_amount = _loan_amount_for_payment(max_monthly_payment, interest_rate, loan_term_months)
    max_affordable_price = max_loan_amount + down_payment

    return {
        "affordable": affordable,
        "comfortable": comfortable,
        "max_affordable_price": round(max_affordable_price, 2),
        "monthly_payment_estimate": round(monthly_payment_estimate, 2),
        "monthly_take_home": round(monthly_take_home, 2),
        "ratio": round(ratio, 4),
        "max_ratio_limit": CAR_MAX_LIMIT,
        "comfort_ratio_limit": CAR_COMFORT_LIMIT,
    }


def general_purchase_affordability(
    income: float,
    savings: float,
    monthly_expenses: float,
    price: float,
) -> dict:
    emergency_fund_threshold = monthly_expenses * EMERGENCY_FUND_MONTHS
    remaining_savings_after_purchase = savings - price
    affordable = remaining_savings_after_purchase >= emergency_fund_threshold
    shortfall = max(emergency_fund_threshold - remaining_savings_after_purchase, 0.0)
    months_of_expenses_remaining = (
        remaining_savings_after_purchase / monthly_expenses
        if monthly_expenses > 0
        else float("inf")
    )
    price_to_income_ratio = price / income if income > 0 else float("inf")

    return {
        "affordable": affordable,
        "remaining_savings_after_purchase": round(remaining_savings_after_purchase, 2),
        "emergency_fund_threshold": round(emergency_fund_threshold, 2),
        "emergency_fund_shortfall": round(shortfall, 2),
        "months_of_expenses_remaining": round(months_of_expenses_remaining, 2),
        "price_to_income_ratio": round(price_to_income_ratio, 4),
    }


def savings_goal_plan(
    target_price: float,
    current_savings: float,
    monthly_income: float,
    savings_rate: float = 0.20,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    gap = max(target_price - current_savings, 0.0)
    monthly_savings_capacity = monthly_income * savings_rate

    if gap <= 0:
        months_to_goal = 0
        target_date = today
    elif monthly_savings_capacity <= 0:
        months_to_goal = None
        target_date = None
    else:
        months_to_goal = math.ceil(gap / monthly_savings_capacity)
        target_date = _add_months(today, months_to_goal)

    return {
        "already_affordable": gap <= 0,
        "gap": round(gap, 2),
        "monthly_savings_capacity": round(monthly_savings_capacity, 2),
        "months_to_goal": months_to_goal,
        "target_date": target_date.isoformat() if target_date else None,
    }
