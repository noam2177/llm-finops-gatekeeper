"""Deterministic mock LLM for job-posting extraction (no keys, no network).

Local tier failure modes (cloud repairs unless tagged otherwise):
* ``[mock:tech_string]`` — emits ``tech_stack`` as a JSON object (schema violation).
* ``[mock:truncated]`` — cuts JSON in half (invalid JSON).
* ``[mock:empty_requirements]`` — local returns ``requirements: []``.
* default local — correct JSON.

Abstain tags:
* ``[mock:unrecoverable]`` — cloud also returns invalid JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from gatekeeper.llm.base import LLMResponse
from gatekeeper.llm.prompts import SYSTEM_PROMPT, estimate_tokens

MockTier = Literal["local", "cloud"]

_TITLE = re.compile(r"^Title:\s*(?P<v>.+)$", re.I | re.M)
_SENIORITY = re.compile(r"^Seniority:\s*(?P<v>.+)$", re.I | re.M)
_REMOTE = re.compile(r"^Remote:\s*(?P<v>.+)$", re.I | re.M)
_TECH = re.compile(r"^Tech(?:\s*stack)?:\s*(?P<v>.+)$", re.I | re.M)
_REQ_LINE = re.compile(r"^-\s+(?P<v>.+)$", re.M)
_TAG = re.compile(r"\[mock:(?P<tag>[a-z_]+)\]", re.I)


class MockLLMProvider:
    def __init__(self, tier: MockTier) -> None:
        self._tier = tier

    @property
    def model(self) -> str:
        return f"mock-{self._tier}"

    async def complete_extraction(self, document_text: str) -> LLMResponse:
        parsed = _parse_posting(document_text)
        tags = {m.group("tag").lower() for m in _TAG.finditer(document_text)}
        payload = _build_payload(parsed)

        if self._tier == "local":
            if "tech_string" in tags:
                payload["tech_stack"] = {
                    "primary": parsed["tech_stack"][0] if parsed["tech_stack"] else "?"
                }
            if "empty_requirements" in tags:
                payload["requirements"] = []
            text = json.dumps(payload, ensure_ascii=False)
            if "truncated" in tags:
                text = text[: len(text) // 2]
        else:
            if "unrecoverable" in tags:
                text = '{"job_title": '
            else:
                text = f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

        return LLMResponse(
            text=text,
            model=self.model,
            prompt_tokens=estimate_tokens(SYSTEM_PROMPT + document_text),
            completion_tokens=estimate_tokens(text),
        )


def _parse_posting(text: str) -> dict[str, Any]:
    title = _TITLE.search(text)
    seniority = _SENIORITY.search(text)
    remote = _REMOTE.search(text)
    tech = _TECH.search(text)
    requirements = [m.group("v").strip() for m in _REQ_LINE.finditer(text)]
    tech_stack = []
    if tech:
        tech_stack = [p.strip() for p in re.split(r"[|,]", tech.group("v")) if p.strip()]
    level = (seniority.group("v").strip() if seniority else "unspecified").casefold()
    if level not in {"junior", "mid", "intern", "associate", "unspecified"}:
        level = "unspecified"
    remote_raw = remote.group("v").strip().casefold() if remote else "no"
    return {
        "job_title": title.group("v").strip() if title else "Unknown Role",
        "seniority_level": level,
        "tech_stack": tech_stack,
        "requirements": requirements,
        "remote_ok": remote_raw in {"yes", "true", "remote", "hybrid"},
    }


def _build_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "job_title": parsed["job_title"],
        "seniority_level": parsed["seniority_level"],
        "tech_stack": parsed["tech_stack"],
        "requirements": parsed["requirements"],
        "remote_ok": parsed["remote_ok"],
    }
