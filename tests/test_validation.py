from __future__ import annotations

import json

import pytest

from gatekeeper.pipeline import FailureKind, validate_model_output
from gatekeeper.pipeline.validation import strip_code_fences
from tests.conftest import job_posting


def test_valid_output() -> None:
    outcome = validate_model_output(json.dumps(job_posting()))
    assert outcome.ok
    assert outcome.failure is None


@pytest.mark.parametrize("fence", ["```json\n{}\n```", "```\n{}\n```"])
def test_code_fences_stripped(fence: str) -> None:
    assert strip_code_fences(fence) == "{}"


def test_invalid_json() -> None:
    assert validate_model_output('{"job_title": ').failure is FailureKind.INVALID_JSON


def test_schema_violation_on_wrong_type() -> None:
    outcome = validate_model_output(json.dumps({**job_posting(), "tech_stack": 42}))
    assert outcome.failure is FailureKind.SCHEMA
    assert "tech_stack" in outcome.detail


def test_detail_never_contains_posting_title() -> None:
    outcome = validate_model_output(json.dumps(job_posting(requirements=[])))
    assert "Python experience" not in outcome.detail
