"""Firebase ID token verification. The frontend authenticates directly with
Firebase (email/password) - the backend is never involved in login/signup/
logout at all, unlike the Wristband setup this replaced. Every protected
request instead carries a Firebase ID token as `Authorization: Bearer
<token>`, which this module verifies; `decoded["uid"]` is the only source of
user identity anywhere in the app.
"""

from __future__ import annotations

import json

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth_sdk
from firebase_admin import credentials

from app.config import FIREBASE_SERVICE_ACCOUNT_JSON, FIREBASE_SERVICE_ACCOUNT_PATH

_bearer_scheme = HTTPBearer(auto_error=False)
_firebase_app: firebase_admin.App | None = None


def _get_firebase_app() -> firebase_admin.App:
    global _firebase_app
    if _firebase_app is None:
        cred = (
            credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
            if FIREBASE_SERVICE_ACCOUNT_JSON
            else credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        )
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def init_firebase_app() -> None:
    """Called once from main.py's lifespan startup, before the server accepts
    any requests. Without this, _get_firebase_app()'s lazy check-then-set
    races: require_firebase_auth is a sync dependency, which FastAPI runs in
    a threadpool, so two requests landing close together (e.g. the several
    API calls a fresh page load fires at once) can both see _firebase_app is
    None and both call firebase_admin.initialize_app() - the loser raises
    ValueError('The default Firebase app already exists'), which the except
    below turns into a misleading 401 for what looks like a perfectly valid
    token. Initializing here, single-threaded, before Uvicorn starts serving,
    makes every later read of _firebase_app just see it already set.

    If this fails (e.g. bad/missing service account file), it's swallowed
    here rather than crashing startup - _firebase_app stays None and
    require_firebase_auth falls back to its existing lazy path, so behavior
    for a misconfigured deployment is unchanged (protected routes 401,
    everything else still runs)."""
    try:
        _get_firebase_app()
    except Exception:
        pass


def require_firebase_auth(
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """FastAPI dependency: verifies the ID token and returns Firebase's
    decoded claims (uid, email, etc). Raises 401 for anything missing,
    malformed, expired, or revoked - never silently falls through."""
    if bearer is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    try:
        _get_firebase_app()
        return firebase_auth_sdk.verify_id_token(bearer.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
