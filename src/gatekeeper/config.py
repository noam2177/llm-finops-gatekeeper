"""Runtime settings, read from the environment only. No secrets live in code."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Settings:
    local_model: str = "qwen2.5:7b-instruct"
    ollama_base_url: str = "http://localhost:11434"
    cloud_model: str = "gpt-4o-mini"
    cloud_base_url: str = "https://api.openai.com/v1"
    cloud_api_key: str | None = field(default=None, repr=False)
    request_timeout_s: float = 60.0

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        defaults = cls()

        def read(name: str, default: str) -> str:
            return source.get(name, "").strip() or default

        return cls(
            local_model=read("GATEKEEPER_LOCAL_MODEL", defaults.local_model),
            ollama_base_url=read("OLLAMA_BASE_URL", defaults.ollama_base_url),
            cloud_model=read("GATEKEEPER_CLOUD_MODEL", defaults.cloud_model),
            cloud_base_url=read("GATEKEEPER_CLOUD_BASE_URL", defaults.cloud_base_url),
            cloud_api_key=source.get("GATEKEEPER_CLOUD_API_KEY", "").strip() or None,
            request_timeout_s=float(
                read("GATEKEEPER_REQUEST_TIMEOUT_S", str(defaults.request_timeout_s))
            ),
        )
