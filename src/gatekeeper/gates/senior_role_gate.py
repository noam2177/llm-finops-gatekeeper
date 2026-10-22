"""CPU gate: drop Senior+ roles and obvious non-job scrapes before any LLM call."""

from __future__ import annotations

import re
from dataclasses import dataclass

ELIGIBLE_FAMILY = "eligible_posting"
SENIOR_FAMILY = "senior_role"
NOISE_FAMILY = "scraped_noise"

_SENIOR_RE = re.compile(
    r"(?i)"
    r"(\bsenior\b|\bsr\.?\b|\bstaff\s+engineer\b|\bprincipal\b|"
    r"\bdistinguished\b|\bhead\s+of\b|\bvp\s+of\b|\b10\+\s*years\b|\b15\+\s*years\b)"
)
_JOB_SIGNALS = (
    "job posting",
    "we are hiring",
    "about the role",
    "responsibilities",
    "requirements",
    "tech stack",
    "apply now",
    "what you will do",
    "what we're looking for",
    "role:",
    "title:",
)
_ROLE_TITLES = (
    "developer",
    "engineer",
    "analyst",
    "scientist",
    "intern",
    "associate",
)


@dataclass(frozen=True, slots=True)
class GateDecision:
    relevant: bool
    family_id: str
    matched: tuple[str, ...]
    reason: str


def _normalize(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def senior_role_gate(text: str) -> GateDecision:
    """Return ``relevant=True`` only for junior/mid-style postings worth an LLM extract."""
    blob = _normalize(text)
    senior_hits = tuple(m.group(0).lower() for m in _SENIOR_RE.finditer(blob))
    if senior_hits:
        return GateDecision(
            relevant=False,
            family_id=SENIOR_FAMILY,
            matched=tuple(dict.fromkeys(senior_hits)),
            reason="senior_role_cues",
        )

    job_hits = tuple(s for s in _JOB_SIGNALS if s in blob)
    title_hit = any(t in blob for t in _ROLE_TITLES)
    looks_like_job = bool(job_hits) or title_hit

    if not looks_like_job:
        return GateDecision(
            relevant=False,
            family_id=NOISE_FAMILY,
            matched=(),
            reason="no_job_posting_anchors",
        )

    matched = job_hits if job_hits else (next(t for t in _ROLE_TITLES if t in blob),)
    return GateDecision(
        relevant=True,
        family_id=ELIGIBLE_FAMILY,
        matched=tuple(dict.fromkeys(matched)),
        reason="eligible_posting",
    )
