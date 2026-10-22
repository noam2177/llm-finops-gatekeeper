from __future__ import annotations

import json

from gatekeeper.llm.base import LLMResponse, ProviderError
from gatekeeper.pipeline import (
    ExtractionStatus,
    FailureKind,
    Tier,
    TieredPipeline,
)
from tests.conftest import job_posting

RELEVANT = """JOB_POSTING_SCRAPE
Title: Junior AI Developer
Seniority: junior
We are hiring. Tech stack: Python
Requirements:
- Python
"""
GOOD = json.dumps(job_posting())
BAD_SCHEMA = json.dumps({**job_posting(), "tech_stack": {"bad": True}})


class ScriptedProvider:
    def __init__(self, name: str, reply: str | ProviderError) -> None:
        self._name = name
        self._reply = reply
        self.calls = 0

    @property
    def model(self) -> str:
        return self._name

    async def complete_extraction(self, document_text: str) -> LLMResponse:
        self.calls += 1
        if isinstance(self._reply, ProviderError):
            raise self._reply
        return LLMResponse(self._reply, self._name, prompt_tokens=100, completion_tokens=20)


class ExplodingProvider:
    model = "must-not-run"

    async def complete_extraction(self, document_text: str) -> LLMResponse:
        raise AssertionError("provider must not run when the gate blocks")


async def test_local_ok_skips_cloud() -> None:
    local, cloud = ScriptedProvider("local", GOOD), ScriptedProvider("cloud", GOOD)
    result = await TieredPipeline(local, cloud).run("a.txt", RELEVANT)
    assert result.status is ExtractionStatus.SUCCESS
    assert result.resolved_by is Tier.LOCAL
    assert (local.calls, cloud.calls) == (1, 0)


async def test_gate_blocks_senior_without_llm() -> None:
    pipeline = TieredPipeline(ExplodingProvider(), ExplodingProvider())
    result = await pipeline.run("senior.txt", "Senior Engineer — we are hiring")
    assert result.status is ExtractionStatus.BLOCKED
    assert result.gate is not None and result.gate.family_id == "senior_role"


async def test_schema_failure_escalates_by_default() -> None:
    local, cloud = ScriptedProvider("local", BAD_SCHEMA), ScriptedProvider("cloud", GOOD)
    result = await TieredPipeline(local, cloud).run("a.txt", RELEVANT)
    assert result.resolved_by is Tier.CLOUD
    assert result.attempts[0].failure is FailureKind.SCHEMA
    assert "Failed Schema Validation" in result.trace[1].label


async def test_no_cloud_provider_abstains() -> None:
    local = ScriptedProvider("local", "not json")
    result = await TieredPipeline(local, None).run("a.txt", RELEVANT)
    assert result.status is ExtractionStatus.ABSTAIN


async def test_both_tiers_fail_abstains() -> None:
    local = ScriptedProvider("local", BAD_SCHEMA)
    cloud = ScriptedProvider("cloud", '{"job_title": ')
    result = await TieredPipeline(local, cloud).run("a.txt", RELEVANT)
    assert result.status is ExtractionStatus.ABSTAIN
    assert [a.failure for a in result.attempts] == [FailureKind.SCHEMA, FailureKind.INVALID_JSON]
