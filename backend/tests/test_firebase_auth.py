from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.firebase_auth import require_firebase_auth

app = FastAPI()


@app.get("/protected")
def protected_route(decoded_token: dict = Depends(require_firebase_auth)) -> dict:
    return {"uid": decoded_token["uid"]}


client = TestClient(app)


class TestRequireFirebaseAuth:
    def test_401_when_no_authorization_header(self):
        response = client.get("/protected")
        assert response.status_code == 401

    def test_401_when_token_verification_fails(self):
        with patch("app.firebase_auth._get_firebase_app"), patch(
            "app.firebase_auth.firebase_auth_sdk.verify_id_token", side_effect=ValueError("bad token")
        ):
            response = client.get("/protected", headers={"Authorization": "Bearer garbage"})
        assert response.status_code == 401

    def test_401_when_firebase_app_is_unconfigured(self):
        with patch("app.firebase_auth._get_firebase_app", side_effect=FileNotFoundError("no credentials file")):
            response = client.get("/protected", headers={"Authorization": "Bearer whatever"})
        assert response.status_code == 401

    def test_returns_decoded_claims_on_success(self):
        with patch("app.firebase_auth._get_firebase_app"), patch(
            "app.firebase_auth.firebase_auth_sdk.verify_id_token", return_value={"uid": "abc123", "email": "x@y.com"}
        ):
            response = client.get("/protected", headers={"Authorization": "Bearer valid-token"})
        assert response.status_code == 200
        assert response.json() == {"uid": "abc123"}
