"""Turn a raw model completion into a validated job posting or a typed failure."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from gatekeeper.schemas.job_posting import JobPostingSchema

_FENCE = re.compile(r"^\s*```(?:json)?\s*(?P<body>.*?)\s*```\s*$", re.S | re.I)


class FailureKind(StrEnum):
    TRANSPORT = "transport_error"
    INVALID_JSON = "invalid_json"
    SCHEMA = "schema_violation"


@dataclass(frozen=True, slots=True)
class ValidationOutcome:
    """``detail`` lists error types and field paths only, never scraped text (CWE-532)."""

    document: JobPostingSchema | None
    failure: FailureKind | None
    detail: str

    @property
    def ok(self) -> bool:
        return self.document is not None


def strip_code_fences(raw: str) -> str:
    match = _FENCE.match(raw)
    return match.group("body") if match else raw.strip()


def validate_model_output(raw: str) -> ValidationOutcome:
    try:
        payload = json.loads(strip_code_fences(raw))
    except json.JSONDecodeError:
        return ValidationOutcome(None, FailureKind.INVALID_JSON, "JSONDecodeError")
    if not isinstance(payload, dict):
        return ValidationOutcome(None, FailureKind.SCHEMA, "top-level JSON is not an object")

    try:
        document = JobPostingSchema.model_validate(payload)
    except ValidationError as exc:
        fields = sorted(
            {".".join(str(part) for part in err["loc"]) or "<root>" for err in exc.errors()}
        )
        return ValidationOutcome(
            None, FailureKind.SCHEMA, f"schema_violation at {', '.join(fields)}"
        )

    return ValidationOutcome(document, None, "ok")
