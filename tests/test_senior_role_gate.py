from __future__ import annotations

import pytest

from gatekeeper.gates import senior_role_gate
from gatekeeper.gates.senior_role_gate import ELIGIBLE_FAMILY, NOISE_FAMILY, SENIOR_FAMILY


def test_eligible_junior_posting_passes() -> None:
    text = """JOB_POSTING_SCRAPE
Title: Junior AI Developer
Seniority: junior
About the role — we are hiring.
Tech stack: Python
Requirements:
- Python
"""
    decision = senior_role_gate(text)
    assert decision.relevant is True
    assert decision.family_id == ELIGIBLE_FAMILY


@pytest.mark.parametrize(
    "snippet",
    [
        "Senior Software Engineer",
        "Sr. Data Scientist",
        "Staff Engineer platform team",
        "Principal AI Architect",
        "10+ years in production ML",
    ],
)
def test_senior_cues_blocked(snippet: str) -> None:
    decision = senior_role_gate(f"Title: Dev\nWe are hiring.\n{snippet}")
    assert decision.relevant is False
    assert decision.family_id == SENIOR_FAMILY
    assert decision.reason == "senior_role_cues"


def test_newsletter_scrape_blocked() -> None:
    decision = senior_role_gate("Weekly digest — unsubscribe here")
    assert decision.relevant is False
    assert decision.family_id == NOISE_FAMILY


def test_mid_developer_without_senior_word_passes() -> None:
    text = "Mid-level developer role. Requirements: Python. Tech stack: FastAPI"
    assert senior_role_gate(text).relevant is True
