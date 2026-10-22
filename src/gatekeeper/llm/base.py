"""Provider contract shared by mock, local and cloud backends."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class ProviderError(Exception):
    """Transport-level failure (connection, timeout, HTTP status). Carries no payload content."""

    def __init__(self, kind: str, model: str) -> None:
        super().__init__(f"{kind} from {model}")
        self.kind = kind
        self.model = model


@runtime_checkable
class LLMProvider(Protocol):
    """Anything that turns document text into a raw (untrusted) model completion."""

    @property
    def model(self) -> str: ...

    async def complete_extraction(self, document_text: str) -> LLMResponse: ...
