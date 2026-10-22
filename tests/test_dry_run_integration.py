from __future__ import annotations

from collections import Counter

import pytest

from gatekeeper.llm import MockLLMProvider
from gatekeeper.metrics import load_ground_truth, score, summarize
from gatekeeper.pipeline import ExtractionResult, ExtractionStatus, Tier, TieredPipeline
from tests.conftest import FIXTURES, GROUND_TRUTH

EXPECTED_ROUTES = {
    "A": (ExtractionStatus.BLOCKED, Tier.GATE, 5),
    "B": (ExtractionStatus.SUCCESS, Tier.LOCAL, 8),
    "C": (ExtractionStatus.SUCCESS, Tier.CLOUD, 4),
    "D": (ExtractionStatus.ABSTAIN, None, 3),
}


@pytest.fixture(scope="module")
def truth():
    return load_ground_truth(GROUND_TRUTH)


async def _run_all() -> list[ExtractionResult]:
    pipeline = TieredPipeline(MockLLMProvider("local"), MockLLMProvider("cloud"))
    return [
        await pipeline.run(p.name, p.read_text(encoding="utf-8"))
        for p in sorted(FIXTURES.glob("*.txt"))
    ]


def test_fixture_counts(truth) -> None:
    assert len(truth) == 20
    assert Counter(row.scenario for row in truth.values()) == {
        k: c for k, (_, _, c) in EXPECTED_ROUTES.items()
    }


async def test_routing_and_accuracy(truth) -> None:
    results = await _run_all()
    for result in results:
        status, tier, _ = EXPECTED_ROUTES[truth[result.filename].scenario]
        assert (result.status, result.resolved_by) == (status, tier), result.filename
    evaluation = summarize([score(r, truth[r.filename]) for r in results])
    assert evaluation.hallucinations == 0
    assert evaluation.correct == 20


async def test_escalation_trace() -> None:
    pipeline = TieredPipeline(MockLLMProvider("local"), MockLLMProvider("cloud"))
    text = (FIXTURES / "sample_escalation.txt").read_text(encoding="utf-8")
    result = await pipeline.run("sample_escalation.txt", text)
    assert "Failed Schema Validation" in result.trace[1].label
    assert result.resolved_by is Tier.CLOUD
