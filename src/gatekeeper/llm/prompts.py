"""Prompt shared by every provider so tiers differ only in model capability."""

from __future__ import annotations

SYSTEM_PROMPT = """You extract structured data from scraped job postings for an AI job filter.
Return ONLY one JSON object, no prose, with exactly this shape:
{
  "job_title": string,
  "seniority_level": "junior"|"mid"|"intern"|"associate"|"unspecified",
  "tech_stack": [string, ...],
  "requirements": [string, ...],
  "remote_ok": boolean
}
Rules:
- Copy technologies exactly as written; normalize seniority to the enum (never "senior").
- tech_stack and requirements must each have at least one non-empty string.
- Never invent technologies or requirements that are not in the scrape.
"""


def build_messages(document_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Scraped job text:\n<<<\n{document_text}\n>>>"},
    ]


def estimate_tokens(text: str) -> int:
    return max(len(text) // 4, 1)
