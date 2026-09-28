"""Google Antigravity subscription provider over the Cloud Code wire."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from .antigravity_auth import (
    ANTIGRAVITY_VERSION,
    BASE_URLS,
    PLAN_LIMIT_ERROR,
    AntigravityAuthError,
    AntigravitySignInRequired,
    AntigravityTokenStore,
)
from .base import (
    AssistantTurn,
    ModelCapabilities,
    ProviderClient,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from .capabilities import capabilities_for
from .gemini_provider import _signature_extras, convert_messages, convert_tools


def _camelize(value: Any) -> Any:
    if isinstance(value, list):
        return [_camelize(item) for item in value]
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key, item in value.items():
        parts = key.split("_")
        out[parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])] = _camelize(item)
    return out


def _usage(data: dict[str, Any]) -> Optional[TokenUsage]:
    raw = data.get("usageMetadata") or data.get("usage_metadata") or {}
    if not raw:
        return None
    prompt = int(raw.get("promptTokenCount") or raw.get("prompt_token_count") or 0)
    cached = int(raw.get("cachedContentTokenCount") or raw.get("cached_content_token_count") or 0)
    output = int(raw.get("candidatesTokenCount") or raw.get("candidates_token_count") or 0)
    output += int(raw.get("thoughtsTokenCount") or raw.get("thoughts_token_count") or 0)
    return TokenUsage(input=max(prompt - cached, 0), output=output, cache_read=cached)


def _response_body(data: dict[str, Any]) -> dict[str, Any]:
    wrapped = data.get("response")
    return wrapped if isinstance(wrapped, dict) else data


def _parts(
    data: dict[str, Any],
) -> tuple[list[str], list[ToolCall], list[str], Optional[str], Optional[str], list[Optional[str]]]:
    texts: list[str] = []
    calls: list[ToolCall] = []
    thoughts: list[str] = []
    finish: Optional[str] = None
    text_sig: Optional[str] = None
    call_sigs: list[Optional[str]] = []
    for candidate in data.get("candidates") or []:
        finish = candidate.get("finishReason") or candidate.get("finish_reason") or finish
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            sig = part.get("thoughtSignature") or part.get("thought_signature")
            call = part.get("functionCall") or part.get("function_call")
            if call:
                calls.append(
                    ToolCall(
                        id=f"call_{len(calls)}",
                        name=str(call.get("name") or ""),
                        arguments=dict(call.get("args") or {}),
                    )
                )
                call_sigs.append(str(sig) if sig else None)
                continue
            text = part.get("text")
            if text:
                if part.get("thought"):
                    thoughts.append(str(text))
                else:
                    texts.append(str(text))
                    if sig:
                        text_sig = str(sig)
    return texts, calls, thoughts, finish, text_sig, call_sigs


def _wire_part(part: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in part.items():
        if k == "function_call":
            out["functionCall"] = v
        elif k == "function_response":
            out["functionResponse"] = v
        elif k == "thought_signature":
            out["thoughtSignature"] = v
        elif k == "inline_data":
            out["inlineData"] = v
        else:
            out[k] = v
    return out


def _wire_contents(contents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "role": m.get("role"),
            "parts": [
                _wire_part(p) if isinstance(p, dict) else p
                for p in m.get("parts", [])
            ],
        }
        for m in contents
    ]


class AntigravityProvider(ProviderClient):
    def __init__(self, *, secrets: Any = None, default_model: str = "gemini-3.8-flash") -> None:
        self._secrets = secrets
        self.default_model = default_model

    def _store(self) -> AntigravityTokenStore:
        return AntigravityTokenStore(self._secrets)

    def _resolve_model(self, model: str) -> str:
        clean = model.split(":", 1)[-1] if ":" in model else model
        available = self._store()._data().get("available_models") or []
        if clean in available:
            return clean
        mapping = {
            "gemini-3.8-flash": "gemini-3.8-flash-tiered",
            "gemini-3.7-flash": "gemini-3.7-flash-tiered",
            "gemini-3.6-flash": "gemini-3.6-flash-tiered",
        }
        mapped = mapping.get(clean, clean)
        if mapped in available:
            return mapped
        for candidate in available:
            if candidate.startswith(clean):
                return candidate
        return mapped

    def _body(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]],
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        system, contents = convert_messages(messages)
        request: dict[str, Any] = {"contents": _wire_contents(contents)}
        if system:
            request["systemInstruction"] = {"parts": [{"text": system}]}
        generation = {
            key: value
            for key, value in settings.items()
            if key in {"temperature", "top_p", "top_k", "max_output_tokens", "stop_sequences"}
        }
        if "max_tokens" in settings and "max_output_tokens" not in generation:
            generation["max_output_tokens"] = settings["max_tokens"]
        if generation:
            request["generationConfig"] = _camelize(generation)
        converted = convert_tools(tools)
        if converted:
            request["tools"] = [
                {"functionDeclarations": t.get("function_declarations", [])}
                for t in converted
            ]
        return {
            "project": str((self._store()._data().get("project_id") or "")),
            "model": self._resolve_model(model),
            "request": request,
            "requestType": "agent",
            "userAgent": "antigravity",
            "requestId": f"agent-{uuid.uuid4().hex[:12]}",
        }

    def _post(self, action: str, body: dict[str, Any], timeout: float = 180.0):
        import httpx

        token = self._store().access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if action.startswith("streamGenerateContent") else "application/json",
            "User-Agent": f"antigravity/{ANTIGRAVITY_VERSION}",
            "Client-Metadata": "ideType=IDE_UNSPECIFIED,platform=PLATFORM_UNSPECIFIED,pluginType=GEMINI",
        }
        last: Optional[Exception] = None
        for base in BASE_URLS:
            try:
                response = httpx.post(
                    f"{base}/v1internal:{action}",
                    headers=headers,
                    json=body,
                    timeout=timeout,
                )
                if response.status_code == 401:
                    self._store().refresh()
                    headers["Authorization"] = f"Bearer {self._store().access_token()}"
                    response = httpx.post(
                        f"{base}/v1internal:{action}",
                        headers=headers,
                        json=body,
                        timeout=timeout,
                    )
                if response.status_code < 300:
                    return response
                if response.status_code in (429, 500, 502, 503, 504) and base != BASE_URLS[-1]:
                    continue
                if response.status_code == 429:
                    raise RuntimeError(PLAN_LIMIT_ERROR)
                detail = response.text[:300].strip()
                raise RuntimeError(f"Antigravity returned HTTP {response.status_code}: {detail}")
            except (AntigravitySignInRequired, RuntimeError):
                raise
            except Exception as exc:
                last = exc
        raise RuntimeError(f"Couldn't reach Antigravity ({last.__class__.__name__ if last else 'unknown'}).")

    def complete(self, *, model: str, messages: list[dict[str, Any]], tools=None, **settings: Any) -> AssistantTurn:
        response = self._post("generateContent", self._body(model, messages, tools, settings))
        data = response.json()
        parsed = _response_body(data)
        texts, calls, thoughts, finish, text_sig, call_sigs = _parts(parsed)
        return AssistantTurn(
            text="".join(texts) or None,
            tool_calls=calls,
            finish_reason="tool_calls" if calls else (str(finish).lower() if finish else None),
            raw=data,
            reasoning="".join(thoughts) or None,
            extras=_signature_extras(text_sig, call_sigs),
            usage=_usage(parsed),
        )

    def stream(self, *, model: str, messages: list[dict[str, Any]], tools=None, **settings: Any):
        response = self._post("streamGenerateContent?alt=sse", self._body(model, messages, tools, settings))
        texts: list[str] = []
        thoughts: list[str] = []
        calls: list[ToolCall] = []
        call_sigs: list[Optional[str]] = []
        text_sig: Optional[str] = None
        finish: Optional[str] = None
        usage: Optional[TokenUsage] = None
        for line in response.text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw or raw == "[DONE]":
                continue
            data = _response_body(json.loads(raw))
            (
                chunk_text,
                chunk_calls,
                chunk_thoughts,
                chunk_finish,
                chunk_text_sig,
                chunk_call_sigs,
            ) = _parts(data)
            for text in chunk_text:
                texts.append(text)
                yield StreamChunk(text_delta=text)
            for thought in chunk_thoughts:
                thoughts.append(thought)
                yield StreamChunk(reasoning_delta=thought)
            calls.extend(chunk_calls)
            call_sigs.extend(chunk_call_sigs)
            if chunk_text_sig:
                text_sig = chunk_text_sig
            finish = chunk_finish or finish
            usage = _usage(data) or usage
        yield StreamChunk(
            turn=AssistantTurn(
                text="".join(texts) or None,
                tool_calls=calls,
                finish_reason="tool_calls" if calls else (str(finish).lower() if finish else None),
                reasoning="".join(thoughts) or None,
                extras=_signature_extras(text_sig, call_sigs),
                usage=usage,
            )
        )

    def capabilities(self, model: str) -> ModelCapabilities:
        return capabilities_for(model)
