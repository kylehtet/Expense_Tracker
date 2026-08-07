from unittest.mock import MagicMock, patch

import anthropic

from app.parser import ParsedQuery, parse_user_query


def _mock_response(**fields):
    response = MagicMock()
    response.parsed_output = ParsedQuery(**fields)
    return response


class TestParseUserQuery:
    def test_all_fields_present(self):
        with patch("app.parser._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_response(
                income=90000,
                purchase_type="house",
                price=350000,
                location="Austin, TX",
                current_savings=40000,
            )
            result = parse_user_query(
                "I make $90k/yr, have $40k saved, can I afford a $350k house in Austin, TX?"
            )

        assert result["income"] == 90000
        assert result["purchase_type"] == "house"
        assert result["missing_fields"] == []
        assert result["error"] is None

    def test_missing_core_fields_are_flagged(self):
        with patch("app.parser._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_response(
                purchase_type="car"
            )
            result = parse_user_query("Can I afford a car?")

        assert result["missing_fields"] == ["income", "price"]
        assert result["purchase_type"] == "car"

    def test_no_fields_mentioned(self):
        with patch("app.parser._get_client") as get_client:
            get_client.return_value.messages.parse.return_value = _mock_response()
            result = parse_user_query("Can I afford it?")

        assert result["missing_fields"] == ["income", "purchase_type", "price"]
        assert result["location"] is None
        assert result["current_savings"] is None

    def test_api_error_returns_safe_default(self):
        with patch("app.parser._get_client") as get_client:
            get_client.return_value.messages.parse.side_effect = anthropic.APIConnectionError(
                request=MagicMock()
            )
            result = parse_user_query("I make $90k, can I afford a $300k house?")

        assert result["missing_fields"] == ["income", "purchase_type", "price"]
        assert result["error"] is not None
