from unittest.mock import MagicMock, patch

import anthropic

from app.explain import explain_verdict

FACTS = {
    "verdict": "tight",
    "category": "Entertainment",
    "price": 480.0,
    "timing": "one_time",
    "effective_amount": 480.0,
    "split_monthly": 160.0,
    "category_left_before": 98.0,
    "category_left_after": -382.0,
    "overall_left_before": 950.0,
    "overall_left_after": 470.0,
    "days_remaining": 25,
    "current_daily_pace": 459.14,
    "safe_to_spend_today": 38.0,
    "effect_on_pace_pct": 14.9,
}


def _mock_response(text):
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    response.usage = MagicMock(input_tokens=120, output_tokens=40)
    return response


class TestExplainVerdict:
    def test_returns_ai_explanation_on_success(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response(
                "This pushes Entertainment $382 over for August, but your overall budget still has room."
            )
            result = explain_verdict(FACTS)

        assert result["source"] == "ai"
        assert result["error"] is None
        assert "Entertainment" in result["explanation"]

    def test_prompt_includes_the_real_numbers_not_placeholders(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("ok")
            explain_verdict(FACTS)

        call_kwargs = get_client.return_value.messages.create.call_args.kwargs
        user_message = call_kwargs["messages"][0]["content"]
        assert "$480.00" in user_message
        assert "98.0" in user_message
        assert "-382.0" in user_message

    def test_falls_back_gracefully_on_api_error(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.side_effect = anthropic.APIConnectionError(
                request=MagicMock()
            )
            result = explain_verdict(FACTS)

        assert result["source"] == "fallback"
        assert result["error"] is not None
        assert "Entertainment" in result["explanation"]

    def test_falls_back_on_empty_response_text(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("")
            result = explain_verdict(FACTS)

        assert result["source"] == "fallback"

    def test_fallback_for_unbudgeted_category(self):
        facts = {**FACTS, "category_left_before": None, "category_left_after": None}
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.side_effect = RuntimeError("boom")
            result = explain_verdict(facts)

        assert "no budget set" not in result["explanation"] or "budget" in result["explanation"]
        assert result["source"] == "fallback"

    def test_fallback_for_comfortable_verdict(self):
        facts = {**FACTS, "verdict": "comfortable", "category_left_after": 20.0, "overall_left_after": 500.0}
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.side_effect = RuntimeError("boom")
            result = explain_verdict(facts)

        assert result["source"] == "fallback"
        assert "$20.00" in result["explanation"]

    def test_fallback_for_over_verdict(self):
        facts = {**FACTS, "verdict": "over", "overall_left_after": -50.0}
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.side_effect = RuntimeError("boom")
            result = explain_verdict(facts)

        assert result["source"] == "fallback"
        assert "$50.00" in result["explanation"]

    def test_identical_facts_hit_cache_instead_of_calling_api_again(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("Cached text.")
            first = explain_verdict(FACTS)
            second = explain_verdict(FACTS)

        assert get_client.return_value.messages.create.call_count == 1
        assert first == second

    def test_logs_real_token_usage_on_success(self):
        with patch("app.explain._get_client") as get_client, patch("app.explain.log_usage") as log_usage:
            get_client.return_value.messages.create.return_value = _mock_response("Some text.")
            explain_verdict(FACTS)

        log_usage.assert_called_once_with("explain_verdict", "claude-sonnet-5", 120, 40)

    def test_logs_cached_call_with_zero_tokens(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("Some text.")
            explain_verdict(FACTS)

        with patch("app.explain.log_usage") as log_usage:
            explain_verdict(FACTS)

        log_usage.assert_called_once_with("explain_verdict", "claude-sonnet-5", input_tokens=0, output_tokens=0, cached=True)

    def test_retrieved_facts_are_included_in_the_prompt(self):
        retrieved = [{"text": "The average 30 year mortgage rate is 6.8% as of 2026-08-01.", "category": "mortgage_rate", "source": "FRED", "stale": False}]
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("ok")
            explain_verdict(FACTS, retrieved_facts=retrieved)

        user_message = get_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "6.8%" in user_message

    def test_no_retrieved_facts_omits_the_reference_section(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.return_value = _mock_response("ok")
            explain_verdict(FACTS, retrieved_facts=None)

        user_message = get_client.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "Reference facts" not in user_message

    def test_different_retrieved_facts_are_not_cache_collisions(self):
        with patch("app.explain._get_client") as get_client:
            get_client.return_value.messages.create.side_effect = [
                _mock_response("Without facts."),
                _mock_response("With facts."),
            ]
            without = explain_verdict(FACTS, retrieved_facts=None)
            with_facts = explain_verdict(FACTS, retrieved_facts=[{"text": "x", "category": "mortgage_rate", "source": "FRED", "stale": False}])

        assert get_client.return_value.messages.create.call_count == 2
        assert without["explanation"] != with_facts["explanation"]
