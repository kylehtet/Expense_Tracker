from unittest.mock import MagicMock, patch

import anthropic

from app.auto_budget import AutoBudgetSuggestions, CategoryBudgetSuggestion, recommend_budget_for_goal
from app.recommend import spending_profile


def _mock_parse_response(suggestions, summary):
    parsed = AutoBudgetSuggestions(
        suggestions=[CategoryBudgetSuggestion(**s) for s in suggestions],
        summary=summary,
    )
    response = MagicMock()
    response.parsed_output = parsed
    response.usage = MagicMock(input_tokens=180, output_tokens=140)
    return response


class TestRecommendBudgetForGoal:
    def test_not_needed_when_required_cut_is_zero(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        result = recommend_budget_for_goal("Vacation", 0.0, profile, {})
        assert result == {"suggestions": [], "summary": "You're already on pace for this goal.", "source": "not_needed", "error": None}

    def test_none_when_no_spending_history(self):
        result = recommend_budget_for_goal("Vacation", 100.0, {}, {})
        assert result["suggestions"] == []
        assert result["source"] == "none"

    def test_returns_ai_suggestions_on_success(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": 250.0, "rationale": "Below your average, still workable."}],
                "Cutting Food gets you there.",
            )
            result = recommend_budget_for_goal("Vacation", 50.0, profile, {}, housing_facts=None)

        assert result["source"] == "ai"
        assert result["error"] is None
        assert result["suggestions"][0]["category"] == "Food"

    def test_requests_enough_tokens_for_multiple_categories(self, sandbox_transactions):
        # A real run with 4 budgeted categories truncated mid-JSON at the
        # old max_tokens=800 (matching recommend_budgets), producing a
        # parse failure and an unnecessary fallback - this locks in the fix.
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": 250.0, "rationale": "ok"}], "summary"
            )
            recommend_budget_for_goal("Vacation", 50.0, profile, {}, housing_facts=None)

        _, kwargs = get_client.return_value.messages.parse.call_args
        assert kwargs["max_tokens"] >= 1500

    def test_rescales_up_when_the_ai_total_cut_falls_short(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        food_avg = profile["Food"]["average"]
        # Model proposes only a $5 cut, but the goal needs $50 freed up.
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": food_avg - 5.0, "rationale": "small trim"}],
                "summary",
            )
            result = recommend_budget_for_goal("Vacation", 50.0, profile, {})

        actual_cut = food_avg - result["suggestions"][0]["suggested_budget"]
        assert round(actual_cut, 2) == 50.0

    def test_leaves_ai_suggestions_alone_when_they_already_meet_the_target(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        food_avg = profile["Food"]["average"]
        # Model proposes a modest $20 cut against a $10 requirement - already
        # sufficient, and well above the half-average floor, so unchanged.
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": food_avg - 20.0, "rationale": "modest trim"}],
                "summary",
            )
            result = recommend_budget_for_goal("Vacation", 10.0, profile, {})

        assert result["suggestions"][0]["suggested_budget"] == round(food_avg - 20.0, 2)

    def test_ai_suggestion_below_the_floor_is_clamped_even_when_cut_is_already_sufficient(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        food_avg = profile["Food"]["average"]
        # Model proposes an unrealistic $200 cut (more than half of average)
        # against only a $50 requirement - the floor still applies.
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": food_avg - 200.0, "rationale": "big trim"}],
                "summary",
            )
            result = recommend_budget_for_goal("Vacation", 50.0, profile, {})

        assert result["suggestions"][0]["suggested_budget"] == round(food_avg * 0.5, 2)

    def test_falls_back_gracefully_on_api_error(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.side_effect = anthropic.APIConnectionError(request=MagicMock())
            result = recommend_budget_for_goal("Vacation", 100.0, profile, {})

        assert result["source"] == "fallback"
        assert result["error"] is not None
        assert len(result["suggestions"]) > 0

    def test_fallback_never_cuts_below_half_of_average(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.side_effect = RuntimeError("boom")
            # Ask for an enormous cut - the fallback should still never propose
            # less than half of any category's real average.
            result = recommend_budget_for_goal("Vacation", 100000.0, profile, {})

        for s in result["suggestions"]:
            avg = profile[s["category"]]["average"]
            assert s["suggested_budget"] >= round(avg * 0.5, 2) - 0.01

    def test_identical_input_hits_cache_instead_of_calling_api_again(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": 250.0, "rationale": "ok"}], "summary"
            )
            first = recommend_budget_for_goal("Vacation", 50.0, profile, {})
            second = recommend_budget_for_goal("Vacation", 50.0, profile, {})

        assert get_client.return_value.messages.parse.call_count == 1
        assert first == second

    def test_logs_real_token_usage_on_success(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        with patch("app.auto_budget._get_client") as get_client, patch("app.auto_budget.log_usage") as log_usage:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": 250.0, "rationale": "ok"}], "summary"
            )
            recommend_budget_for_goal("Vacation", 50.0, profile, {})

        log_usage.assert_called_once_with("auto_budget", "claude-sonnet-5", 180, 140)

    def test_housing_facts_only_affect_the_cache_key_not_the_math(self, sandbox_transactions):
        profile = spending_profile(sandbox_transactions, months=3)
        facts = [{"text": "Average local rent is $1800/mo.", "category": "cost_of_living", "source": "test", "stale": False}]
        with patch("app.auto_budget._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_parse_response(
                [{"category": "Food", "suggested_budget": 250.0, "rationale": "ok"}], "summary"
            )
            without_facts = recommend_budget_for_goal("Vacation", 50.0, profile, {}, housing_facts=None)
            with_facts = recommend_budget_for_goal("Vacation", 50.0, profile, {}, housing_facts=facts)

        # Different cache keys -> the client gets called twice, not once.
        assert get_client.return_value.messages.parse.call_count == 2
        assert without_facts["suggestions"] == with_facts["suggestions"]
