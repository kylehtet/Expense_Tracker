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
