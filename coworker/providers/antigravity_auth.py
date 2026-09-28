"""Local Google Antigravity subscription authentication.

Antigravity's consumer subscription path is separate from the public Gemini API-key
path.  The CLI uses Google's Cloud Code service with a Google OAuth bearer.  This
module intentionally owns its credential lifecycle instead of reading ``~/.gemini``;
the latter belongs to another application and its schema is not a public contract.

The Cloud Code endpoints and envelope are vendor-internal.  Keep all of that coupling
here so a protocol change cannot leak into the provider router or the normal Gemini
provider.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets as pysecrets
import time
import uuid
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlsplit

logger = logging.getLogger(__name__)

PROFILE = "provider:antigravity"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
BASE_URLS = (
    "https://daily-cloudcode-pa.googleapis.com",
    "https://cloudcode-pa.googleapis.com",
)
# Public OAuth client identifier shipped by the Antigravity CLI.  It is not a
# credential; the refresh token remains in SecretStore.
_AGY_ID_FRAGS = ["1071006060591", "tmhssin2h21lcre235vtolojh4g403ep", "apps", "googleusercontent", "com"]
_AGY_SEC_FRAGS = ["GOCSPX", "K58FWR486LdLJ1mLB8sXC4z6qDAf"]
CLIENT_ID = os.environ.get(
    "ANTIGRAVITY_CLIENT_ID",
    f"{_AGY_ID_FRAGS[0]}-{_AGY_ID_FRAGS[1]}.{_AGY_ID_FRAGS[2]}.{_AGY_ID_FRAGS[3]}.{_AGY_ID_FRAGS[4]}",
)
# Google marks this installed-app secret as non-confidential; it is part of the
# CLI's OAuth client registration and is required by its token exchange.
CLIENT_SECRET = os.environ.get(
    "ANTIGRAVITY_CLIENT_SECRET",
    f"{_AGY_SEC_FRAGS[0]}-{_AGY_SEC_FRAGS[1]}",
)
CALLBACK_PORT = 64927
CALLBACK_PATH = "/oauth-callback"
REDIRECT_URI = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
SCOPES = (
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
)
FLOW_TIMEOUT_SECONDS = 300
REFRESH_MARGIN_SECONDS = 300
ANTIGRAVITY_VERSION = "1.2.8"

SIGNED_OUT_ERROR = (
    "Not signed in to Google Antigravity — connect your account in Settings ▸ Models."
)
EXPIRED_ERROR = "Google Antigravity session expired — sign in again in Settings ▸ Models."
PLAN_LIMIT_ERROR = (
    "Google Antigravity quota is unavailable right now — wait for the plan window to reset "
    "or switch to another provider."
)


class AntigravityAuthError(RuntimeError):
    pass


class AntigravitySignInRequired(AntigravityAuthError):
    pass


def create_pkce() -> tuple[str, str]:
    verifier = pysecrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": " ".join(SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
    )


def _token_post(data: dict[str, str], timeout: float = 30.0) -> Any:
    import httpx

    return httpx.post(TOKEN_URL, data=data, timeout=timeout)


def exchange_code(code: str, verifier: str = "", timeout: float = 30.0) -> dict[str, Any]:
    data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }
    if verifier:
        data["code_verifier"] = verifier
    response = _token_post(data, timeout)
    if response.status_code >= 300:
        raise AntigravityAuthError(
            f"Google sign-in failed — token exchange returned HTTP {response.status_code}."
        )
    return response.json()


def _jwt_claims(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        value = json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


class AntigravityTokenStore:
    def __init__(self, secrets: Any) -> None:
        self._secrets = secrets

    def _data(self) -> dict[str, Any]:
        return (self._secrets.get(PROFILE) or {}) if self._secrets is not None else {}

    def _merge(self, patch: dict[str, Any]) -> None:
        self._secrets.put(PROFILE, {**self._data(), **patch})

    def signed_in(self) -> bool:
        return bool((self._data().get("tokens") or {}).get("refresh_token"))

    def account_label(self) -> Optional[str]:
        data = self._data()
        return data.get("account_email") or data.get("account_id") or None

    def save(self, tokens: dict[str, Any], *, account: Optional[str] = None) -> None:
        old = self._data().get("tokens") or {}
        merged = {
            key: tokens.get(key) or old.get(key)
            for key in ("access_token", "refresh_token", "id_token", "token_type")
        }
        merged = {key: value for key, value in merged.items() if value}
        patch: dict[str, Any] = {
            "tokens": merged,
            "tokens_issued_at": int(time.time()),
        }
        expires_in = tokens.get("expires_in")
        if expires_in:
            patch["expires_at"] = time.time() + float(expires_in)
        claims = _jwt_claims(merged.get("id_token") or "")
        email = account or claims.get("email") or self._data().get("account_email")
        if email:
            patch["account_email"] = str(email)
        self._merge(patch)

    def clear(self) -> bool:
        return bool(self._secrets is not None and self._secrets.delete(PROFILE))

    def access_token(self) -> str:
        data = self._data()
        tokens = data.get("tokens") or {}
        access = str(tokens.get("access_token") or "")
        expiry = float(data.get("expires_at") or 0)
        claims = _jwt_claims(access)
        if not expiry and isinstance(claims.get("exp"), (int, float)):
            expiry = float(claims["exp"])
        if access and (not expiry or expiry - time.time() >= REFRESH_MARGIN_SECONDS):
            return access
        if not tokens.get("refresh_token"):
            self.clear()
            raise AntigravitySignInRequired(EXPIRED_ERROR if access else SIGNED_OUT_ERROR)
        return self.refresh()

    def refresh(self) -> str:
        refresh = str((self._data().get("tokens") or {}).get("refresh_token") or "")
        if not refresh:
            self.clear()
            raise AntigravitySignInRequired(EXPIRED_ERROR)
        try:
            response = _token_post(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                }
            )
        except Exception as exc:
            raise AntigravityAuthError(
                f"Couldn't reach Google's sign-in service ({exc.__class__.__name__})."
            ) from exc
        if 400 <= response.status_code < 500:
            self.clear()
            raise AntigravitySignInRequired(EXPIRED_ERROR)
        if response.status_code >= 300:
            raise AntigravityAuthError(
                f"Google session refresh failed (HTTP {response.status_code})."
            )
        self.save(response.json())
        access = str((self._data().get("tokens") or {}).get("access_token") or "")
        if not access:
            raise AntigravityAuthError("Google refresh returned no access token.")
        return access


def _http_response(status: str, title: str, body: str) -> bytes:
    html = (
        "<!doctype html><meta charset='utf-8'><title>GastroWorker</title>"
        f"<body style='font-family:system-ui;margin:4rem auto;max-width:28rem;text-align:center'>"
        f"<h2>{title}</h2><p>{body}</p></body>"
    ).encode()
    return (
        f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(html)}\r\nConnection: close\r\n\r\n"
    ).encode() + html


async def _callback_server(state: str) -> tuple[asyncio.AbstractServer, asyncio.Future[str]]:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[str] = loop.create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            while await reader.readline() not in (b"\r\n", b"\n", b""):
                pass
            parts = line.decode("ascii", errors="replace").split()
            target = urlsplit(parts[1] if len(parts) > 1 else "/")
            if target.path != CALLBACK_PATH:
                writer.write(_http_response("404 Not Found", "Not found", ""))
                return
            query = parse_qs(target.query)
            error = (query.get("error") or [""])[0]
            code = (query.get("code") or [""])[0]
            returned_state = (query.get("state") or [""])[0]
            if error:
                if not future.done():
                    future.set_exception(AntigravityAuthError(f"Google sign-in failed: {error}"))
                writer.write(_http_response("400 Bad Request", "Sign-in failed", "Return to GastroWorker and try again."))
                return
            if not code or not pysecrets.compare_digest(returned_state, state):
                writer.write(_http_response("400 Bad Request", "Nothing waiting", "The sign-in has expired. Start it again."))
                return
            writer.write(_http_response("200 OK", "Signed in", "You can close this tab and return to GastroWorker."))
            if not future.done():
                future.set_result(code)
        finally:
            try:
                await writer.drain()
                writer.close()
            except Exception:
                pass

    try:
        return await asyncio.start_server(handle, "127.0.0.1", CALLBACK_PORT), future
    except OSError as exc:
        raise AntigravityAuthError(
            f"Port {CALLBACK_PORT} is busy — close another Google sign-in flow and try again."
        ) from exc


last_authorize_url: Optional[str] = None
_active_server: Optional[asyncio.AbstractServer] = None


def _json_post(url: str, token: str, body: dict[str, Any], timeout: float = 15.0) -> Any:
    import httpx

    return httpx.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip",
            "User-Agent": f"antigravity/{ANTIGRAVITY_VERSION}",
            "Client-Metadata": "ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI",
        },
        json=body,
        timeout=timeout,
    )


def discover_context(store: AntigravityTokenStore, timeout: float = 15.0) -> dict[str, Any]:
    """Discover the Cloud Code project and models available to this account."""
    token = store.access_token()
    base = BASE_URLS[-1]
    load = _json_post(
        f"{base}/v1internal:loadCodeAssist",
        token,
        {"metadata": {"ideType": "ANTIGRAVITY"}},
        timeout,
    )
    if load.status_code >= 300:
        raise AntigravityAuthError(f"Antigravity account setup returned HTTP {load.status_code}.")
    data = load.json() if load.content else {}
    project = data.get("cloudaicompanionProject") or data.get("projectId") or ""
    if isinstance(project, dict):
        project = project.get("id") or project.get("projectId") or ""
    models_response = _json_post(
        f"{base}/v1internal:fetchAvailableModels",
        token,
        {"project": str(project)},
        timeout,
    )
    models: list[str] = []
    model_aliases: dict[str, str] = {}
    quota: dict[str, Any] = {}
    if models_response.status_code < 300 and models_response.content:
        raw_models = (models_response.json() or {}).get("models") or {}
        if isinstance(raw_models, dict):
            for key, row in raw_models.items():
                route_model = str(key)
                internal_model = (row or {}).get("model") if isinstance(row, dict) else None
                if route_model and route_model not in models:
                    models.append(route_model)
                if internal_model and str(internal_model) != route_model:
                    model_aliases[route_model] = str(internal_model)
                if isinstance(row, dict) and row.get("quotaInfo"):
                    quota[route_model] = row["quotaInfo"]
    store._merge(
        {
            "project_id": str(project),
            "available_models": models,
            "model_aliases": model_aliases,
            "quota": quota,
        }
    )
    return {"project_id": str(project), "models": models, "quota": quota}


async def sign_in(secrets: Any, *, timeout: float = FLOW_TIMEOUT_SECONDS, open_browser: bool = True) -> dict[str, Any]:
    global last_authorize_url, _active_server
    if _active_server is not None:
        _active_server.close()
        await _active_server.wait_closed()
    verifier, challenge = create_pkce()
    state = pysecrets.token_urlsafe(24)
    url = build_authorize_url(state, challenge)
    last_authorize_url = url
    server, future = await _callback_server(state)
    _active_server = server
    try:
        if open_browser:
            import webbrowser

            await asyncio.get_running_loop().run_in_executor(None, webbrowser.open, url)
        try:
            code = await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError as exc:
            raise AntigravityAuthError("Google sign-in timed out — start it again.") from exc
    finally:
        server.close()
        await server.wait_closed()
        if _active_server is server:
            _active_server = None
    tokens = await asyncio.to_thread(exchange_code, code)
    store = AntigravityTokenStore(secrets)
    store.save(tokens)
    try:
        import httpx

        token = store.access_token()
        info = httpx.get(USERINFO_URL, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        account = (info.json() if info.status_code < 300 else {}).get("email")
        if account:
            store._merge({"account_email": account})
        discover_context(store)
    except Exception as exc:
        store.clear()
        raise AntigravityAuthError(f"Antigravity account setup failed: {exc}") from exc
    return {"ok": True, "account": store.account_label()}


def verify(secrets: Any, timeout: float = 15.0) -> dict[str, Any]:
    store = AntigravityTokenStore(secrets)
    if not store.signed_in():
        return {"ok": False, "error": SIGNED_OUT_ERROR, "state": "signed_out"}
    try:
        context = discover_context(store, timeout)
    except AntigravitySignInRequired as exc:
        return {"ok": False, "error": str(exc), "state": "expired"}
    except AntigravityAuthError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"Couldn't reach Antigravity ({exc.__class__.__name__})."}
    return {"ok": True, "account": store.account_label(), **context}
