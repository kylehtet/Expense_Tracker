import json
import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


def pytest_configure(config):
    """Runs before any test module is imported, so app.config's module-level
    constants (read once from os.environ at import time) see a valid test
    ENCRYPTION_KEY regardless of which test file happens to import it first."""
    os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
    os.environ.setdefault("PLAID_CLIENT_ID", "test-client-id")
    os.environ.setdefault("PLAID_SECRET", "test-secret")


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
