"""Tier 2 backend: any OpenAI-compatible /chat/completions API."""

from __future__ import annotations

import httpx

from gatekeeper.llm.base import LLMResponse, ProviderError
from gatekeeper.llm.prompts import build_messages, estimate_tokens


class OpenAICompatibleProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        api_key: str,
        *,
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for the cloud provider")
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    def __repr__(self) -> str:
        return f"OpenAICompatibleProvider(model={self._model!r}, base_url={self._base_url!r})"

    async def complete_extraction(self, document_text: str) -> LLMResponse:
        body = {
            "model": self._model,
            "messages": build_messages(document_text),
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_s, transport=self._transport
            ) as client:
                response = await client.post("/chat/completions", json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
            text = str(data["choices"][0]["message"]["content"] or "")
        except httpx.TimeoutException as exc:
            raise ProviderError("Timeout", self.model) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"HTTP{exc.response.status_code}", self.model) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(type(exc).__name__, self.model) from exc

        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=int(usage.get("prompt_tokens") or estimate_tokens(document_text)),
            completion_tokens=int(usage.get("completion_tokens") or estimate_tokens(text)),
        )
