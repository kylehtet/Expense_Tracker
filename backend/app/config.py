"""Environment configuration, centered on the sandbox/development/production switch."""

import os

import plaid
from dotenv import load_dotenv

load_dotenv()

PLAID_ENV = os.environ.get("PLAID_ENV", "sandbox")
PLAID_CLIENT_ID = os.environ.get("PLAID_CLIENT_ID")
PLAID_SECRET = os.environ.get("PLAID_SECRET")

ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./expense_tracker.db")

# Plaid retired the standalone "Development" host; real-bank access below full
# Production Access review now happens over the Production host itself
# ("Limited Production", capped at a small free call volume). We keep our own
# three-way PLAID_ENV switch anyway because sandbox / limited-real-data /
# full-production are meaningfully different operating modes for this app,
# even though "development" and "production" both resolve to the same host.
_PLAID_HOSTS = {
    "sandbox": plaid.Environment.Sandbox,
    "development": plaid.Environment.Production,
    "production": plaid.Environment.Production,
}


def get_plaid_host() -> str:
    try:
        return _PLAID_HOSTS[PLAID_ENV]
    except KeyError:
        raise ValueError(
            f"Unknown PLAID_ENV '{PLAID_ENV}'; expected one of {sorted(_PLAID_HOSTS)}"
        )


IS_SANDBOX = PLAID_ENV == "sandbox"
