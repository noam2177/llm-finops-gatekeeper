from __future__ import annotations

import pytest
from pydantic import ValidationError

from gatekeeper.schemas import JobPostingSchema
from tests.conftest import job_posting


def test_valid_posting() -> None:
    doc = JobPostingSchema.model_validate(job_posting())
    assert doc.job_title == "Junior AI Developer"
    assert doc.tech_stack == ["Python", "LLMs"]


def test_tech_stack_from_comma_string() -> None:
    doc = JobPostingSchema.model_validate(job_posting(tech_stack="Python, FastAPI, pytest"))
    assert doc.tech_stack == ["Python", "FastAPI", "pytest"]


def test_seniority_normalized() -> None:
    doc = JobPostingSchema.model_validate(job_posting(seniority="Mid"))
    assert doc.seniority_level == "mid"


@pytest.mark.parametrize(("raw", "expected"), [("yes", True), ("false", False), ("TRUE", True)])
def test_remote_coercion(raw: str, expected: bool) -> None:
    doc = JobPostingSchema.model_validate(job_posting(remote_ok=raw))
    assert doc.remote_ok is expected


@pytest.mark.parametrize("bad_stack", [[], "", ["   "]])
def test_empty_tech_stack_rejected(bad_stack: object) -> None:
    with pytest.raises(ValidationError):
        JobPostingSchema.model_validate(job_posting(tech_stack=bad_stack))


def test_empty_requirements_rejected() -> None:
    with pytest.raises(ValidationError):
        JobPostingSchema.model_validate(job_posting(requirements=[]))


def test_errors_hide_scraped_values() -> None:
    with pytest.raises(ValidationError) as info:
        JobPostingSchema.model_validate(job_posting(tech_stack={"secret": "client"}))
    assert "secret" not in str(info.value).lower()
