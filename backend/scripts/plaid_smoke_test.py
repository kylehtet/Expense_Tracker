"""Live end-to-end check against Plaid Sandbox: link -> exchange -> transactions -> balances.

Requires PLAID_CLIENT_ID / PLAID_SECRET (Sandbox keys) in backend/.env. Run from
the backend/ directory with the venv active:

    python3 scripts/plaid_smoke_test.py

Sandbox transaction data populates asynchronously after the Item is created,
so this retries fetch_transactions for up to ~30s before giving up.
"""

import time

from app.plaid_client import (
    create_link_token,
    create_sandbox_public_token,
    exchange_public_token,
    fetch_balances,
    fetch_transactions,
)


def mask(token: str) -> str:
    return f"{token[:12]}...{token[-4:]} ({len(token)} chars)"


def main() -> None:
    print("1. create_link_token")
    link_token = create_link_token(user_id="smoke-test-user")
    print("   ", mask(link_token))

    print("2. create_sandbox_public_token (First Platypus Bank)")
    public_token = create_sandbox_public_token()
    print("   ", mask(public_token))

    print("3. exchange_public_token")
    access_token = exchange_public_token(public_token)
    print("    access_token acquired:", mask(access_token))

    print("4. fetch_transactions (retrying while Sandbox populates data)")
    transactions = []
    for attempt in range(6):
        transactions = fetch_transactions(access_token)
        if transactions:
            break
        time.sleep(5)
    print(f"    got {len(transactions)} transactions")
    for t in transactions[:5]:
        print(f"    - {t['date']}  {t['name']:<35} ${t['amount']:>8.2f}")

    print("5. fetch_balances")
    balances = fetch_balances(access_token)
    for acct in balances["accounts"]:
        bal = acct["balances"]
        print(f"    - {acct['name']:<25} {acct['type']:<12} available={bal['available']}  current={bal['current']}")

    assert transactions, "No transactions appeared after 30s - Sandbox may be slow or misconfigured"
    print("\nALL STEPS OK")


if __name__ == "__main__":
    main()
