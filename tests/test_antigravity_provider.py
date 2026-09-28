"""Regression tests for the local Google Antigravity subscription provider."""

from __future__ import annotations

import base64
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from coworker.providers import antigravity_auth
from coworker.providers.antigravity_auth import AntigravityTokenStore
from coworker.providers.antigravity_provider import AntigravityProvider
from coworker.providers.registry import build_provider_client, get_descriptor


def _jwt(claims: dict) -> str:
    def encode(value: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    return f"{encode({'alg': 'none'})}.{encode(claims)}.sig"


def test_pkce_authorize_url_is_bound_to_local_callback():
    verifier, challenge = antigravity_auth.create_pkce()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected

    query = parse_qs(urlsplit(antigravity_auth.build_authorize_url("state", challenge)).query)
    assert query["client_id"][0] == antigravity_auth.CLIENT_ID
    assert query["redirect_uri"][0] == antigravity_auth.REDIRECT_URI
    assert query["state"][0] == "state"
    assert query["scope"][0].split() == list(antigravity_auth.SCOPES)


def test_token_store_preserves_refresh_token_and_account(tmp_path):
    from coworker.secrets import SecretStore

    secrets = SecretStore(tmp_path / "secrets.json")
    store = AntigravityTokenStore(secrets)
    store.save(
        {
            "access_token": "access-1",
            "refresh_token": "refresh-1",
            "id_token": _jwt({"email": "user@example.com"}),
            "expires_in": 3600,
        }
    )
    store.save({"access_token": "access-2"})

    profile = secrets.get(antigravity_auth.PROFILE)
    assert profile["tokens"] == {
        "access_token": "access-2",
        "refresh_token": "refresh-1",
        "id_token": profile["tokens"]["id_token"],
    }
    assert store.signed_in()
    assert store.account_label() == "user@example.com"
    assert store.access_token() == "access-2"


def test_registry_builds_antigravity_without_an_api_key(tmp_path):
    from coworker.secrets import SecretStore

    descriptor = get_descriptor("antigravity")
    assert descriptor is not None
    assert descriptor.auth == "oauth"
    assert descriptor.needs_key is False
    client = build_provider_client("antigravity", {}, SecretStore(tmp_path / "secrets.json"))
    assert isinstance(client, AntigravityProvider)


def test_request_uses_cloud_code_envelope_and_gemini_content(tmp_path):
    from coworker.secrets import SecretStore

    secrets = SecretStore(tmp_path / "secrets.json")
    secrets.put(
        antigravity_auth.PROFILE,
        {"tokens": {"access_token": "access", "refresh_token": "refresh"}, "project_id": "project-1"},
    )
    provider = AntigravityProvider(secrets=secrets)
    body = provider._body(
        "gemini-3.8-flash",
        [{"role": "user", "content": "hello"}],
        None,
        {"max_tokens": 123, "temperature": 0.2},
    )
    assert body["project"] == "project-1"
    assert body["model"] == "gemini-3.8-flash"
    assert body["requestType"] == "agent"
    assert body["request"]["generationConfig"]["maxOutputTokens"] == 123
    assert body["request"]["contents"][0]["parts"][0]["text"] == "hello"


def test_discovery_uses_antigravity_metadata_and_project(tmp_path, monkeypatch):
    from coworker.secrets import SecretStore

    secrets = SecretStore(tmp_path / "secrets.json")
    secrets.put(antigravity_auth.PROFILE, {"tokens": {"access_token": "access", "refresh_token": "refresh"}})
    requests: list[tuple[str, dict]] = []

    def fake_post(url, token, body, timeout):
        requests.append((url, body))
        if url.endswith("loadCodeAssist"):
            return SimpleNamespace(status_code=200, content=b"{}", json=lambda: {"cloudaicompanionProject": "project-1"})
        return SimpleNamespace(
            status_code=200,
            content=b"{}",
            json=lambda: {"models": {"gemini-3.8-flash": {"quotaInfo": {"remainingFraction": 1}}}},
        )

    monkeypatch.setattr(antigravity_auth, "_json_post", fake_post)
    result = antigravity_auth.discover_context(AntigravityTokenStore(secrets))
    assert result["project_id"] == "project-1"
    assert requests[0][1] == {"metadata": {"ideType": "ANTIGRAVITY"}}
    assert requests[1][1] == {"project": "project-1"}
    assert result["models"] == ["gemini-3.8-flash"]


def test_complete_parses_text_tool_call_and_usage(monkeypatch, tmp_path):
    import httpx
    from coworker.secrets import SecretStore

    secrets = SecretStore(tmp_path / "secrets.json")
    secrets.put(antigravity_auth.PROFILE, {"tokens": {"access_token": "access", "refresh_token": "refresh"}})
    response = SimpleNamespace(
        status_code=200,
        text="",
        json=lambda: {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "hi"},
                            {"functionCall": {"name": "lookup", "args": {"q": "x"}}},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 10, "cachedContentTokenCount": 2, "candidatesTokenCount": 4},
        },
    )
    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: response)

    turn = AntigravityProvider(secrets=secrets).complete(
        model="gemini-3.8-flash", messages=[{"role": "user", "content": "hello"}]
    )
    assert turn.text == "hi"
    assert turn.tool_calls[0].name == "lookup"
    assert turn.finish_reason == "tool_calls"
    assert turn.usage is not None
    assert turn.usage.input == 8
