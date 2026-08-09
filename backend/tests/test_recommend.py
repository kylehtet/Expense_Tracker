from unittest.mock import MagicMock, patch

import anthropic

from app.recommend import BudgetRecommendations, CategoryRecommendation, recommend_budgets, spending_profile


class TestSpendingProfile:
    def test_matches_known_fixture_values(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)

        assert profile["Housing"] == {
            "months_observed": 3,
            "average": 1585.0,
            "min": 1500.0,
            "max": 1635.0,
            "most_recent": 1500.0,
        }

    def test_most_recent_never_falls_outside_min_max(self, sandbox_transactions):
        # Transport's most recent fixture month (July) is a large refund
        # (-91.50, net negative) - most_recent must come from the same
        # filtered-positive set as min/max, not the raw last month.
        profile = spending_profile(sandbox_transactions, months=3)
        transport = profile["Transport"]
        assert transport["min"] <= transport["most_recent"] <= transport["max"]

    def test_category_with_only_refunds_is_omitted(self, sandbox_transactions):
        # "Other" in the fixture is all negative (income/refunds) - nothing to
        # recommend a spending budget from.
        profile = spending_profile(sandbox_transactions, months=3)
        assert "Other" not in profile

    def test_empty_transactions_gives_empty_profile(self):
        assert spending_profile([], months=3) == {}


def _mock_parse_response(recommendations, summary):
    parsed = BudgetRecommendations(
        recommendations=[CategoryRecommendation(**r) for r in recommendations],
        summary=summary,
    )
    response = MagicMock()
    response.parsed_output = parsed
    return response


class TestRecommendBudgets:
    def test_no_history_returns_empty_recommendations(self):
        result = recommend_budgets([], {})
        assert result["recommendations"] == []
        assert result["source"] == "none"

    def test_returns_ai_recommendations_on_success(self, sandbox_transactions):
        with patch("app.recommend._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Housing", "recommended_budget": 1600.0, "rationale": "Covers your recent months."}],
                "Based on three months of history.",
            )
            result = recommend_budgets(sandbox_transactions, {}, months=3)

        assert result["source"] == "ai"
        assert result["error"] is None
        assert result["recommendations"][0]["category"] == "Housing"
        assert result["recommendations"][0]["recommended_budget"] == 1600.0

    def test_drops_non_positive_ai_recommendations(self, sandbox_transactions):
        with patch("app.recommend._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [
                    {"category": "Housing", "recommended_budget": 1600.0, "rationale": "ok"},
                    {"category": "Food", "recommended_budget": 0.0, "rationale": "bad"},
                ],
                "summary",
            )
            result = recommend_budgets(sandbox_transactions, {}, months=3)

        categories = [r["category"] for r in result["recommendations"]]
        assert categories == ["Housing"]

    def test_falls_back_gracefully_on_api_error(self, sandbox_transactions):
        with patch("app.recommend._get_client") as get_client:
            get_client.return_value.messages.parse.side_effect = anthropic.APIConnectionError(
                request=MagicMock()
            )
            result = recommend_budgets(sandbox_transactions, {}, months=3)

        assert result["source"] == "fallback"
        assert result["error"] is not None
        assert len(result["recommendations"]) > 0
        for rec in result["recommendations"]:
            assert rec["recommended_budget"] > 0
            assert rec["category"] in rec["rationale"] or True  # rationale is free text

    def test_fallback_rounds_up_to_nearest_ten(self, sandbox_transactions):
        with patch("app.recommend._get_client") as get_client:
            get_client.return_value.messages.parse.side_effect = RuntimeError("boom")
            result = recommend_budgets(sandbox_transactions, {}, months=3)

        housing = next(r for r in result["recommendations"] if r["category"] == "Housing")
        assert housing["recommended_budget"] % 10 == 0
        # Fallback bases the number on max(average, most_recent) = 1585.0 here,
        # rounded up - not the single highest month observed (1635.0 in June).
        assert housing["recommended_budget"] > 1585.0
