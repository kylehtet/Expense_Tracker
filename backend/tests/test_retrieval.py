from unittest.mock import patch

from app.retrieval import retrieve_housing_context

MORTGAGE_RATES = [
    {"label": "30_year_fixed", "rate_percent": 6.8, "as_of_date": "2026-08-01", "source": "FRED", "stale": False},
    {"label": "15_year_fixed", "rate_percent": 6.1, "as_of_date": "2026-08-01", "source": "FRED", "stale": False},
]


class TestRetrieveHousingContext:
    def test_always_includes_mortgage_rates_even_without_location(self):
        with patch("app.retrieval.fetch_mortgage_rates", return_value=MORTGAGE_RATES):
            facts = retrieve_housing_context()

        assert len(facts) == 2
        assert all(f["category"] == "mortgage_rate" for f in facts)
        assert "6.8%" in facts[0]["text"]

    def test_adds_local_facts_when_location_given(self):
        local_result = [
            {
                "id": "tax_insurance::TX",
                "text": "In Texas (TX), the average effective property tax rate is 1.68%.",
                "category": "property_tax_insurance",
                "location": "TX",
                "last_updated": "2026-01-01",
                "source": "Tax Foundation",
                "stale": False,
                "facts": {},
                "distance": 0.1,
            }
        ]
        with patch("app.retrieval.fetch_mortgage_rates", return_value=MORTGAGE_RATES), patch(
            "app.retrieval.retrieve_context", return_value=local_result
        ) as retrieve_context:
            facts = retrieve_housing_context(location="Austin, TX", k=3)

        retrieve_context.assert_called_once_with("property tax insurance cost of living", location="Austin, TX", k=3)
        categories = [f["category"] for f in facts]
        assert categories == ["mortgage_rate", "mortgage_rate", "property_tax_insurance"]

    def test_does_not_call_retrieve_context_without_location(self):
        with patch("app.retrieval.fetch_mortgage_rates", return_value=MORTGAGE_RATES), patch(
            "app.retrieval.retrieve_context"
        ) as retrieve_context:
            retrieve_housing_context()

        retrieve_context.assert_not_called()

    def test_drops_duplicate_mortgage_rate_docs_from_local_results(self):
        local_result = [
            {
                "id": "mortgage_rate::30_year_fixed",
                "text": "duplicate",
                "category": "mortgage_rate",
                "location": "national",
                "last_updated": "2026-08-01",
                "source": "FRED",
                "stale": False,
                "facts": {},
                "distance": 0.05,
            }
        ]
        with patch("app.retrieval.fetch_mortgage_rates", return_value=MORTGAGE_RATES), patch(
            "app.retrieval.retrieve_context", return_value=local_result
        ):
            facts = retrieve_housing_context(location="Austin, TX")

        assert len(facts) == 2  # only the two direct mortgage_rate entries, duplicate from search dropped
