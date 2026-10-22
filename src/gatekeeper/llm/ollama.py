"""Tier 1 backend: a local model served by Ollama's /api/chat endpoint."""

from __future__ import annotations

import httpx

from gatekeeper.llm.base import LLMResponse, ProviderError
from gatekeeper.llm.prompts import build_messages, estimate_tokens


class OllamaProvider:
    def __init__(
        self,
        model: str,
        base_url: str,
        *,
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._transport = transport

    @property
    def model(self) -> str:
        return f"ollama/{self._model}"

    async def complete_extraction(self, document_text: str) -> LLMResponse:
        body = {
            "model": self._model,
            "messages": build_messages(document_text),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout_s, transport=self._transport
            ) as client:
                response = await client.post("/api/chat", json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise ProviderError("Timeout", self.model) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"HTTP{exc.response.status_code}", self.model) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(type(exc).__name__, self.model) from exc

        text = str((data.get("message") or {}).get("content") or "")
        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=int(data.get("prompt_eval_count") or estimate_tokens(document_text)),
            completion_tokens=int(data.get("eval_count") or estimate_tokens(text)),
        )
