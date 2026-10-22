"""Strict JSON contract for scraped job postings."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SeniorityLevel = Literal["junior", "mid", "intern", "associate", "unspecified"]
_TRUE = frozenset({"true", "1", "yes", "y"})
_FALSE = frozenset({"false", "0", "no", "n"})


def _clean_items(values: list[Any]) -> list[str]:
    cleaned: list[str] = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            cleaned.append(text)
    return cleaned


class JobPostingSchema(BaseModel):
    """Tech stack and requirements extracted from an eligible (non-Senior) posting."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
        json_schema_extra={
            "title": "JobPostingSchema",
            "description": "Structured fields for an AI job posting filter pipeline.",
        },
    )

    job_title: str = Field(min_length=2, max_length=200)
    seniority_level: SeniorityLevel
    tech_stack: list[str] = Field(min_length=1)
    requirements: list[str] = Field(min_length=1)
    remote_ok: bool = False

    @field_validator("job_title", mode="before")
    @classmethod
    def _strip_title(cls, value: Any) -> Any:
        if value is None:
            return value
        return str(value).strip()

    @field_validator("seniority_level", mode="before")
    @classmethod
    def _normalize_level(cls, value: Any) -> Any:
        if value is None:
            return value
        return str(value).strip().casefold()

    @field_validator("tech_stack", "requirements", mode="before")
    @classmethod
    def _coerce_list(cls, value: Any) -> Any:
        if isinstance(value, (int, float, dict, bool)):
            raise ValueError("must be a list or comma-separated string")
        if value is None:
            return []
        if isinstance(value, str):
            parts = [p.strip() for p in value.replace("|", ",").split(",")]
            return [p for p in parts if p]
        if isinstance(value, list):
            return value
        return [str(value)]

    @field_validator("tech_stack", "requirements")
    @classmethod
    def _non_empty_items(cls, values: list[str]) -> list[str]:
        cleaned = _clean_items(values)
        if not cleaned:
            raise ValueError("list must contain at least one non-empty item")
        return cleaned

    @field_validator("remote_ok", mode="before")
    @classmethod
    def _coerce_bool(cls, value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in _TRUE:
                return True
            if lowered in _FALSE:
                return False
        return value
