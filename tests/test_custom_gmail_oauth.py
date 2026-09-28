from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from coworker.server.app import create_app, _custom_google_states
from coworker.server.manager import SessionManager


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("COWORKER_PORT", "8765")
    manager = SessionManager(workspace=tmp_path)
    app = create_app(manager)
    return TestClient(app)


def test_custom_gmail_oauth_flow(client, monkeypatch):
    # 1. Check initial config (has env defaults)
    res = client.get("/v1/connectors/gmail/custom-auth-config")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "88973466463" in data["client_id"]
    assert data["has_secret"] is True
    assert "8765/v1/connectors/gmail/oauth/callback" in data["redirect_uri"]

    # 2. Request custom auth URL
    res = client.post(
        "/v1/connectors/gmail/custom-auth-url",
        json={
            "client_id": "test-client-id.apps.googleusercontent.com",
            "client_secret": "test-client-secret-123",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "accounts.google.com/o/oauth2/v2/auth" in data["authorize_url"]
    assert "client_id=test-client-id" in data["authorize_url"]

    # Find the state generated
    state = next(iter(_custom_google_states.keys()))
    assert _custom_google_states[state]["client_id"] == "test-client-id.apps.googleusercontent.com"

    # 3. Simulate Google callback
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data=None, **kwargs):
            class TokenResp:
                status_code = 200

                def json(self):
                    return {
                        "access_token": "google-custom-access-tok",
                        "refresh_token": "google-custom-refresh-tok",
                        "expires_in": 3600,
                    }

            return TokenResp()

        async def get(self, url, headers=None, **kwargs):
            class ProfileResp:
                status_code = 200

                def json(self):
                    return {"emailAddress": "mycustom@gmail.com"}

            return ProfileResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    callback_res = client.get(
        f"/v1/connectors/gmail/oauth/callback?code=google-auth-code&state={state}"
    )
    assert callback_res.status_code == 200
    assert "mycustom@gmail.com" in callback_res.text
    assert "Gmail connected" in callback_res.text

    # Verify account is saved in SecretStore
    status_res = client.get("/v1/connectors").json()
    gmail_conn = next(c for c in status_res["connectors"] if c["name"] == "gmail")
    assert gmail_conn["connected"] is True
    assert len(gmail_conn["accounts"]) == 1
    assert gmail_conn["accounts"][0]["email"] == "mycustom@gmail.com"


def test_custom_connect_manual(client):
    res = client.post(
        "/v1/connectors/gmail/custom-connect",
        json={
            "email": "manual@gmail.com",
            "access_token": "ya29.manual",
            "client_id": "my-id",
            "client_secret": "my-secret",
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    status_res = client.get("/v1/connectors").json()
    gmail_conn = next(c for c in status_res["connectors"] if c["name"] == "gmail")
    assert gmail_conn["connected"] is True
    emails = [a["email"] for a in gmail_conn["accounts"]]
    assert "manual@gmail.com" in emails
