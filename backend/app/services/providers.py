"""LLM provider abstraction.

``LLMClient`` is the interface used by the summarizer and verifier. The only
shipped implementation is Groq; tests substitute a fake via
``set_llm_factory``.
"""
from __future__ import annotations

import time
from typing import Callable, Protocol

from app.core.config import Settings
from app.core.errors import AppError


class ProviderError(AppError):
    """Raised for provider/credential failures. ``status`` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message, status)


class LLMClient(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


class GroqClient:
    name = "groq"

    def __init__(self, api_key: str, model: str, timeout: float):
        self.model = model
        self._api_key = api_key
        self._timeout = timeout

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        import groq  # imported lazily so demo mode never needs it

        client = groq.Groq(api_key=self._api_key, timeout=self._timeout, max_retries=0)
        try:
            msg = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except groq.AuthenticationError:
            raise ProviderError("Groq rejected the API key (authentication failed).", 502)
        except groq.PermissionDeniedError as e:
            body = e.body if isinstance(e.body, dict) else {}
            error = body.get("error", body)
            error = error if isinstance(error, dict) else {}
            code = error.get("code")
            if code not in ("model_permission_blocked_org", "model_permission_blocked_project"):
                raise ProviderError(
                    "Groq denied API access from this server/network (HTTP 403). "
                    "Check the server's network/firewall or VPN settings and Groq account access. "
                    "Changing the frontend or model cannot resolve this access denial.", 502) from e
            raise ProviderError(
                f"Groq denied access to model '{self.model}'. Choose another model in Settings, "
                "or ask your Groq administrator to allow it in organization limits "
                "(https://console.groq.com/settings/limits) and project limits "
                "(https://console.groq.com/settings/project/limits). "
                "Frontend API access cannot override provider permissions.", 502)
        except groq.NotFoundError:
            raise ProviderError(f"Model '{self.model}' was not found for this API key.", 502)
        except groq.RateLimitError:
            raise ProviderError("Groq rate limit reached. Wait a moment and retry.", 429)
        except groq.APITimeoutError:
            raise ProviderError("The model request timed out.", 504)
        except groq.APIConnectionError:
            raise ProviderError("Could not reach the Groq API (check your internet connection).", 502)
        except groq.APIStatusError as e:
            raise ProviderError(f"Groq API error ({e.status_code}): {getattr(e, 'message', str(e))}", 502)
        text = (msg.choices[0].message.content or "").strip() if msg.choices else ""
        if not text:
            raise ProviderError("The model returned an empty response.", 502)
        return text


LLMFactory = Callable[[Settings, str], LLMClient]


def _default_factory(settings: Settings, model: str) -> LLMClient:
    if not settings.has_api_key:
        raise ProviderError("GROQ_API_KEY is not configured on the server.", 503)
    return GroqClient(settings.groq_api_key.strip(), model, settings.llm_timeout_seconds)


_factory: LLMFactory = _default_factory


def set_llm_factory(factory: LLMFactory | None) -> None:
    """Override how LLM clients are built (used by tests)."""
    global _factory
    _factory = factory or _default_factory


def build_llm(settings: Settings, model: str) -> LLMClient:
    return _factory(settings, model)


# --- connection verification state (in memory; never claims connectivity unless tested)
_connection: dict = {"verified": False, "verified_at": None, "model": None, "error": None}


def connection_state() -> dict:
    return dict(_connection)


def reset_connection() -> None:
    _connection.update(verified=False, verified_at=None, model=None, error=None)


def test_connection(settings: Settings, model: str) -> dict:
    t0 = time.perf_counter()
    try:
        client = build_llm(settings, model)
        reply = client.complete("Reply with the single word OK.", "ping", max_tokens=16)
    except ProviderError as e:
        _connection.update(verified=False, verified_at=None, model=model, error=e.message)
        raise
    ms = round((time.perf_counter() - t0) * 1000, 1)
    _connection.update(
        verified=True,
        verified_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        model=model,
        error=None,
    )
    return {"ok": True, "model": model, "latency_ms": ms, "reply_preview": reply[:40]}
