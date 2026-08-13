from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import app.firebase_auth as firebase_auth_module
from app.firebase_auth import _get_firebase_app, require_firebase_auth

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


class TestGetFirebaseApp:
    def setup_method(self):
        firebase_auth_module._firebase_app = None

    def teardown_method(self):
        firebase_auth_module._firebase_app = None

    def test_prefers_json_env_var_over_path_when_both_set(self):
        service_account = {"type": "service_account", "project_id": "demo"}
        with patch("app.firebase_auth.FIREBASE_SERVICE_ACCOUNT_JSON", '{"type": "service_account", "project_id": "demo"}'), \
             patch("app.firebase_auth.FIREBASE_SERVICE_ACCOUNT_PATH", "./should-not-be-used.json"), \
             patch("app.firebase_auth.credentials.Certificate") as certificate, \
             patch("app.firebase_auth.firebase_admin.initialize_app"):
            _get_firebase_app()
        certificate.assert_called_once_with(service_account)

    def test_falls_back_to_path_when_json_env_var_unset(self):
        with patch("app.firebase_auth.FIREBASE_SERVICE_ACCOUNT_JSON", None), \
             patch("app.firebase_auth.FIREBASE_SERVICE_ACCOUNT_PATH", "./firebase-service-account.json"), \
             patch("app.firebase_auth.credentials.Certificate") as certificate, \
             patch("app.firebase_auth.firebase_admin.initialize_app"):
            _get_firebase_app()
        certificate.assert_called_once_with("./firebase-service-account.json")
