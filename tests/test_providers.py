"""HTTP backends against httpx.MockTransport: request shape, usage parsing, error mapping."""

from __future__ import annotations

import json

import httpx
import pytest

from gatekeeper.config import Settings
from gatekeeper.llm import OllamaProvider, OpenAICompatibleProvider, ProviderError

SECRET = "sk-test-not-a-real-key"


def _transport(handler):
    return httpx.MockTransport(handler)


async def test_ollama_success() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"message": {"content": "{}"}, "prompt_eval_count": 50, "eval_count": 5}
        )

    provider = OllamaProvider("qwen", "http://ollama:11434", transport=_transport(handler))
    response = await provider.complete_extraction("doc")
    assert seen["path"] == "/api/chat"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["format"] == "json" and body["stream"] is False
    assert (response.text, response.prompt_tokens, response.completion_tokens) == ("{}", 50, 5)
    assert response.model == "ollama/qwen"


async def test_ollama_connection_error_is_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    provider = OllamaProvider("qwen", "http://ollama:11434", transport=_transport(handler))
    with pytest.raises(ProviderError) as info:
        await provider.complete_extraction("doc")
    assert info.value.kind == "ConnectError"


async def test_openai_compatible_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == f"Bearer {SECRET}"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 70, "completion_tokens": 9},
            },
        )

    provider = OpenAICompatibleProvider(
        "gpt-x", "https://api.example.com/v1", SECRET, transport=_transport(handler)
    )
    response = await provider.complete_extraction("doc")
    assert (response.prompt_tokens, response.completion_tokens) == (70, 9)


@pytest.mark.parametrize(
    ("status", "body", "kind"),
    [(500, {}, "HTTP500"), (429, {}, "HTTP429"), (200, {"choices": []}, "IndexError")],
)
async def test_openai_compatible_errors(status: int, body: dict, kind: str) -> None:
    provider = OpenAICompatibleProvider(
        "gpt-x",
        "https://api.example.com/v1",
        SECRET,
        transport=_transport(lambda request: httpx.Response(status, json=body)),
    )
    with pytest.raises(ProviderError) as info:
        await provider.complete_extraction("doc")
    assert info.value.kind == kind
    assert SECRET not in str(info.value)


def test_api_key_never_in_repr() -> None:
    provider = OpenAICompatibleProvider("gpt-x", "https://api.example.com/v1", SECRET)
    assert SECRET not in repr(provider)
    assert SECRET not in repr(Settings(cloud_api_key=SECRET))


def test_api_key_required() -> None:
    with pytest.raises(ValueError):
        OpenAICompatibleProvider("gpt-x", "https://api.example.com/v1", "")


def test_settings_from_env() -> None:
    settings = Settings.from_env({"GATEKEEPER_CLOUD_API_KEY": "  ", "GATEKEEPER_LOCAL_MODEL": "m"})
    assert settings.cloud_api_key is None
    assert settings.local_model == "m"
