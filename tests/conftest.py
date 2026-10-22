from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "data" / "fixtures"
GROUND_TRUTH = REPO_ROOT / "data" / "ground_truth.csv"

SAMPLE_TITLE = "Junior AI Developer"
SAMPLE_LEVEL = "junior"


def job_posting(
    *,
    title: str = SAMPLE_TITLE,
    seniority: str = SAMPLE_LEVEL,
    tech_stack: list[str] | str | None = None,
    requirements: list[str] | None = None,
    remote_ok: bool = False,
) -> dict[str, object]:
    if tech_stack is None:
        tech_stack = ["Python", "LLMs"]
    if requirements is None:
        requirements = ["Python experience", "LLM familiarity"]
    return {
        "job_title": title,
        "seniority_level": seniority,
        "tech_stack": tech_stack,
        "requirements": requirements,
        "remote_ok": remote_ok,
    }


@pytest.fixture
def repo_cwd(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(REPO_ROOT)
    return REPO_ROOT
