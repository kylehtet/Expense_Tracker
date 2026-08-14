import pytest

from app.categorize import categorize_transaction, categorize_with_llm


def _txn(name, primary=None, detailed=None, merchant_name=None):
    txn = {"name": name}
    if merchant_name is not None:
        txn["merchant_name"] = merchant_name
    if primary is not None:
        txn["personal_finance_category"] = {"primary": primary, "detailed": detailed or primary}
    return txn


class TestCategorizeTransaction:
    @pytest.mark.parametrize(
        "primary,expected",
        [
            ("RENT_AND_UTILITIES", "Housing"),
            ("HOME_IMPROVEMENT", "Housing"),
            ("FOOD_AND_DRINK", "Food"),
            ("TRANSPORTATION", "Transport"),
            ("TRAVEL", "Transport"),
            ("ENTERTAINMENT", "Entertainment"),
            ("GENERAL_MERCHANDISE", "Shopping"),
        ],
    )
    def test_maps_primary_category(self, primary, expected):
        txn = _txn("Some Merchant", primary=primary)
        assert categorize_transaction(txn) == expected

    @pytest.mark.parametrize(
        "primary",
        [
            "BANK_FEES",
            "MEDICAL",
            "INCOME",
            "GENERAL_SERVICES",
            "PERSONAL_CARE",
            "TRANSFER_IN",
            "OTHER",
        ],
    )
    def test_unmapped_categories_fall_back_to_other(self, primary):
        txn = _txn("Some Merchant", primary=primary)
        assert categorize_transaction(txn) == "Other"

    def test_missing_personal_finance_category_falls_back_to_other(self):
        assert categorize_transaction({"name": "Unknown Merchant"}) == "Other"

    def test_streaming_subscription_detected_by_merchant_name(self):
        txn = _txn("NETFLIX.COM", primary="ENTERTAINMENT", merchant_name="Netflix")
        assert categorize_transaction(txn) == "Subscriptions"

    def test_non_entertainment_subscription_detected_by_merchant_name(self):
        # Adobe falls under GENERAL_SERVICES in Plaid's taxonomy, not ENTERTAINMENT,
        # so category alone would mis-file it as "Other" without the name match.
        txn = _txn("ADOBE  CREATIVE CLOUD", primary="GENERAL_SERVICES", merchant_name="Adobe")
        assert categorize_transaction(txn) == "Subscriptions"

    def test_subscription_match_is_case_insensitive(self):
        txn = _txn("spotify usa", primary="ENTERTAINMENT")
        assert categorize_transaction(txn) == "Subscriptions"

    def test_prefers_merchant_name_over_raw_name_for_matching(self):
        txn = _txn("SQ *RANDOM DESC 4821", primary="FOOD_AND_DRINK", merchant_name="Netflix")
        assert categorize_transaction(txn) == "Subscriptions"

    def test_non_subscription_entertainment_stays_entertainment(self):
        txn = _txn("AMC Theatres", primary="ENTERTAINMENT")
        assert categorize_transaction(txn) == "Entertainment"

    @pytest.mark.parametrize("merchant", ["Walmart", "Amazon", "Amazon Prime", "eBay", "Best Buy"])
    def test_known_retailers_are_shopping(self, merchant):
        txn = _txn("Some Description", primary="GENERAL_SERVICES", merchant_name=merchant)
        assert categorize_transaction(txn) == "Shopping"

    def test_costco_and_target_are_not_keyword_matched(self):
        # Deliberately excluded - both sell enough groceries/gas under the same
        # name that a blanket "Shopping" match would be wrong as often as right.
        # They fall through to Plaid's own category instead (Food, Transport, etc).
        costco_gas = _txn("Costco Gas", primary="TRANSPORTATION", merchant_name="Costco")
        assert categorize_transaction(costco_gas) == "Transport"

    def test_shopping_match_is_case_insensitive(self):
        txn = _txn("WALMART SUPERCENTER", primary="GENERAL_SERVICES")
        assert categorize_transaction(txn) == "Shopping"

    def test_shopping_wins_over_general_merchandise_mapping_either_way(self):
        # Same outcome whether it's the keyword match or the primary-category
        # fallback that catches it - this just documents that both paths agree.
        txn = _txn("Amazon.com", primary="GENERAL_MERCHANDISE", merchant_name="Amazon")
        assert categorize_transaction(txn) == "Shopping"

    def test_subscription_keyword_still_wins_over_shopping_when_both_could_match(self):
        # Netflix isn't a shopping keyword, but this documents the precedence
        # order deliberately: subscriptions are checked before shopping.
        txn = _txn("NETFLIX.COM", primary="ENTERTAINMENT", merchant_name="Netflix")
        assert categorize_transaction(txn) == "Subscriptions"


class TestCategorizeWithLlm:
    def test_not_implemented(self):
        with pytest.raises(NotImplementedError):
            categorize_with_llm({"name": "Anything"})
