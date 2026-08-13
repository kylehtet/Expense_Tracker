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

# Comma-separated list of extra frontend origins CORS should allow, beyond the
# localhost ports used in dev - the deployed frontend's real origin(s) go here.
# e.g. ALLOWED_ORIGINS=https://app.example.com,https://staging.example.com
_DEV_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
ALLOWED_ORIGINS = _DEV_ORIGINS + [
    origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()
]

# The frontend authenticates directly against Firebase (email/password) and
# sends the resulting ID token as a Bearer header on every request; this is
# the service account key that lets our backend verify those tokens. Path to
# the JSON key file downloaded from Firebase Console -> Project Settings ->
# Service Accounts -> Generate New Private Key. Never commit this file.
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json"
)

# Alternative to the path above for hosts with no writable filesystem to drop
# a key file on (e.g. serverless) - the whole service account JSON as one
# env var. Wins over the path if both are set.
FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

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
