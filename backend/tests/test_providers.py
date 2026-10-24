"""Exercise the Groq SDK boundary without sending network requests."""
from types import SimpleNamespace
from unittest.mock import Mock

import groq
import httpx
import pytest

from app.services.providers import GroqClient, ProviderError


def test_groq_completion(monkeypatch):
    sdk = Mock()
    sdk.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  Summary  "))]
    )
    constructor = Mock(return_value=sdk)
    monkeypatch.setattr(groq, "Groq", constructor)
    client = GroqClient("test-key", "llama-3.3-70b-versatile", 90)
    assert client.complete("Instructions", "Source", 512) == "Summary"
    constructor.assert_called_once_with(api_key="test-key", timeout=90, max_retries=0)
    sdk.chat.completions.create.assert_called_once_with(
        model="llama-3.3-70b-versatile", max_tokens=512,
        messages=[{"role": "system", "content": "Instructions"}, {"role": "user", "content": "Source"}],
    )


def test_groq_authentication_failure(monkeypatch):
    sdk = Mock()
    sdk.chat.completions.create.side_effect = groq.AuthenticationError(
        "Invalid key", response=httpx.Response(401, request=httpx.Request("POST", "https://api.groq.com")), body=None
    )
    monkeypatch.setattr(groq, "Groq", Mock(return_value=sdk))
    with pytest.raises(ProviderError, match="Groq rejected the API key"):
        GroqClient("invalid", "model", 90).complete("system", "user")


@pytest.mark.parametrize("choices", [[], [SimpleNamespace(message=SimpleNamespace(content=None))]])
def test_groq_empty_response(monkeypatch, choices):
    sdk = Mock()
    sdk.chat.completions.create.return_value = SimpleNamespace(choices=choices)
    monkeypatch.setattr(groq, "Groq", Mock(return_value=sdk))
    with pytest.raises(ProviderError, match="empty response"):
        GroqClient("key", "model", 90).complete("system", "user")


def test_groq_permission_failure_has_recovery_steps(monkeypatch):
    sdk = Mock()
    sdk.chat.completions.create.side_effect = groq.PermissionDeniedError(
        "Blocked", response=httpx.Response(403, request=httpx.Request("POST", "https://api.groq.com")),
        body={"error": {"code": "model_permission_blocked_org"}}
    )
    monkeypatch.setattr(groq, "Groq", Mock(return_value=sdk))
    with pytest.raises(ProviderError) as caught:
        GroqClient("secret-key", "blocked-model", 90).complete("system", "user")
    assert "blocked-model" in caught.value.message
    assert "https://console.groq.com/settings/limits" in caught.value.message
    assert "https://console.groq.com/settings/project/limits" in caught.value.message
    assert "secret-key" not in caught.value.message


def test_groq_network_denial_is_not_model_permission_failure(monkeypatch):
    sdk = Mock()
    sdk.chat.completions.create.side_effect = groq.PermissionDeniedError(
        "Access denied", response=httpx.Response(403, request=httpx.Request("POST", "https://api.groq.com")),
        body={"error": {"message": "Access denied. Please check your network settings."}}
    )
    monkeypatch.setattr(groq, "Groq", Mock(return_value=sdk))
    with pytest.raises(ProviderError, match="server/network") as caught:
        GroqClient("secret-key", "model", 90).complete("system", "user")
    assert "organization limits" not in caught.value.message
    assert "secret-key" not in caught.value.message
