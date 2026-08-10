"""Firebase ID token verification. The frontend authenticates directly with
Firebase (email/password) - the backend is never involved in login/signup/
logout at all, unlike the Wristband setup this replaced. Every protected
request instead carries a Firebase ID token as `Authorization: Bearer
<token>`, which this module verifies; `decoded["uid"]` is the only source of
user identity anywhere in the app.
"""

from __future__ import annotations

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth_sdk
from firebase_admin import credentials

from app.config import FIREBASE_SERVICE_ACCOUNT_PATH

_bearer_scheme = HTTPBearer(auto_error=False)
_firebase_app: firebase_admin.App | None = None


def _get_firebase_app() -> firebase_admin.App:
    global _firebase_app
    if _firebase_app is None:
        cred = credentials.Certificate(FIREBASE_SERVICE_ACCOUNT_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


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
