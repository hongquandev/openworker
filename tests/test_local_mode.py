"""Tests for GastroWorker 100% Local / Standalone Mode.

Verifies that the system operates fully offline and self-contained:
- Local identity and status without Auth0.
- Telemetry disabled / zero-out.
- Local persona gallery loading from built-in manifests.
- Custom OAuth refresh (Microsoft / Google).
- GitHub polling adapter in standalone mode.
"""

from __future__ import annotations

import asyncio
import pytest

from coworker import cloud
from coworker.config import Config
from coworker.connectors.adapters import GitHubPollingAdapter, make_adapter
from coworker.secrets import SecretStore


@pytest.fixture
def secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("COWORKER_STATE_DIR", str(tmp_path / "state"))
    return SecretStore(path=tmp_path / "state" / "secrets.json")


@pytest.fixture
def local_config():
    return Config(
        local_mode=True,
        local_user_name="Dev Operator",
        local_user_email="dev@local.box",
        port=8765,
    )


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {}

    def json(self):
        return self._body


# --- local status & identity --------------------------------------------------


def test_local_mode_status_returns_local_identity(secrets, local_config):
    st = cloud.status(secrets, local_config)
    assert st["signed_in"] is True
    assert st["account"] == "dev@local.box"
    assert st["user_id"] == "usr_local_owner"
    assert st["local_mode"] is True


def test_standard_mode_without_login_is_signed_out(secrets):
    st = cloud.status(secrets)
    assert st["signed_in"] is False
    assert st["account"] == ""


# --- telemetry bypass in local mode -------------------------------------------


def test_local_mode_bypasses_telemetry_emission(secrets, local_config, monkeypatch):
    called = []

    def fake_post(*a, **k):
        called.append(a)
        return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(cloud.httpx, "post", fake_post)

    ok = cloud.emit_session_created(
        secrets,
        local_config,
        session_id="sess_1",
        persona_id="swe-worker",
        persona_family="worker",
        workspace_kind="deliverable",
    )
    assert ok is False
    assert len(called) == 0  # no network call made


# --- local persona gallery ----------------------------------------------------


def test_local_gallery_list_returns_builtins(secrets, local_config):
    res = cloud.gallery_list(secrets, local_config)
    assert res is not None
    assert "personas" in res
    slugs = [p["slug"] for p in res["personas"]]
    assert "swe-worker" in slugs
    assert "cloud-posture" in slugs


def test_local_gallery_manifest_loads_builtin_markdown(secrets, local_config):
    manifest = cloud.gallery_manifest(secrets, local_config, "swe-worker")
    assert manifest is not None
    assert "manifest_markdown" in manifest
    assert "SWE Worker" in manifest["manifest_markdown"]
    assert manifest.get("manifest_hash", "").startswith("sha256:")


def test_local_gallery_detail_derives_capabilities_locally(secrets, local_config):
    detail = cloud.gallery_detail(secrets, local_config, "swe-worker")
    assert detail is not None
    assert detail.get("ok") is True
    card = detail.get("card", {})
    assert card.get("slug") == "swe-worker"
    assert card.get("name") == "SWE Worker"
    assert "tools" in detail.get("capabilities", {})


# --- custom OAuth refresh -----------------------------------------------------


def test_refresh_custom_microsoft_token(secrets, monkeypatch):
    profile_key = "outlook:default"
    secrets.put(
        profile_key,
        {
            "custom_oauth": True,
            "client_id": "ms-client-123",
            "client_secret": "ms-secret-456",
            "refresh_token": "ms-refresh-token",
            "access_token": "old-token",
            "expires": 0,
        },
    )

    def fake_post(url, **kwargs):
        assert "login.microsoftonline.com" in url
        assert kwargs["data"]["grant_type"] == "refresh_token"
        assert kwargs["data"]["client_id"] == "ms-client-123"
        return FakeResponse(
            200,
            {
                "access_token": "fresh-ms-access-token",
                "refresh_token": "fresh-ms-refresh-token",
                "expires_in": 3600,
            },
        )

    monkeypatch.setattr(cloud.httpx, "post", fake_post)

    updated = cloud.refresh_custom_microsoft_token(secrets, profile_key)
    assert updated is not None
    assert updated["access_token"] == "fresh-ms-access-token"
    assert updated["refresh_token"] == "fresh-ms-refresh-token"

    stored = secrets.get(profile_key)
    assert stored["access_token"] == "fresh-ms-access-token"


# --- github standalone polling adapter ----------------------------------------


def test_make_adapter_returns_polling_adapter_for_pat(secrets):
    profile = {"token": "ghp_testpersonalaccesstoken123"}
    adapter = make_adapter("github", profile, secrets=secrets)
    assert adapter is not None
    assert isinstance(adapter, GitHubPollingAdapter)
    assert adapter._token == "ghp_testpersonalaccesstoken123"


@pytest.mark.asyncio
async def test_github_polling_adapter_lifecycle():
    adapter = GitHubPollingAdapter("ghp_testtoken", interval=60.0)
    connected = await adapter.connect()
    assert connected is True
    assert adapter._running is True
    await adapter.disconnect()
    assert adapter._running is False
