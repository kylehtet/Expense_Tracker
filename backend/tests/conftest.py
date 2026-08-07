import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sandbox_transactions() -> list[dict]:
    with open(FIXTURES_DIR / "sandbox_transactions.json") as f:
        return json.load(f)


@pytest.fixture
def sandbox_transactions_by_month(sandbox_transactions) -> dict[str, list[dict]]:
    by_month: dict[str, list[dict]] = {}
    for txn in sandbox_transactions:
        by_month.setdefault(txn["date"][:7], []).append(txn)
    return by_month
