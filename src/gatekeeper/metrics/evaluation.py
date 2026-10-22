"""Score pipeline results against ``ground_truth.csv``."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gatekeeper.pipeline.tiered import ExtractionResult, ExtractionStatus

_COLUMNS = (
    "filename",
    "scenario",
    "description",
    "expected_status",
    "expected_resolved_by",
    "expected_job_title",
    "expected_seniority",
    "expected_tech_stack",
)


@dataclass(frozen=True, slots=True)
class GroundTruthRow:
    filename: str
    scenario: str
    description: str
    expected_status: str
    expected_resolved_by: str
    expected_job_title: str | None
    expected_seniority: str | None
    expected_tech_stack: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Verdict:
    filename: str
    scenario: str
    verdict: str
    status: str
    resolved_by: str


def _split_tech(raw: str) -> tuple[str, ...]:
    if not raw.strip():
        return ()
    return tuple(p.strip() for p in raw.split("|") if p.strip())


def load_ground_truth(path: Path) -> dict[str, GroundTruthRow]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"ground truth missing columns: {sorted(missing)}")
        rows: dict[str, GroundTruthRow] = {}
        for raw in reader:
            rows[raw["filename"]] = GroundTruthRow(
                filename=raw["filename"],
                scenario=raw["scenario"],
                description=raw["description"],
                expected_status=raw["expected_status"],
                expected_resolved_by=raw["expected_resolved_by"],
                expected_job_title=raw["expected_job_title"] or None,
                expected_seniority=raw["expected_seniority"] or None,
                expected_tech_stack=_split_tech(raw["expected_tech_stack"]),
            )
    return rows


def _field_match(output: dict[str, Any] | None, truth: GroundTruthRow) -> bool:
    if not output:
        return False
    if output.get("job_title") != truth.expected_job_title:
        return False
    if output.get("seniority_level") != truth.expected_seniority:
        return False
    stack = tuple(output.get("tech_stack") or ())
    return stack == truth.expected_tech_stack


def score(result: ExtractionResult, truth: GroundTruthRow) -> Verdict:
    resolved_by = result.resolved_by.value if result.resolved_by else "none"
    route_ok = (
        result.status.value == truth.expected_status and resolved_by == truth.expected_resolved_by
    )
    if result.status is ExtractionStatus.SUCCESS:
        fields_ok = _field_match(result.output, truth)
        verdict = "hallucination" if not fields_ok else "correct" if route_ok else "wrong_route"
    else:
        verdict = "correct" if route_ok else "wrong_route"
    return Verdict(result.filename, truth.scenario, verdict, result.status.value, resolved_by)


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    total: int
    correct: int
    wrong_route: int
    hallucinations: int
    by_scenario: dict[str, dict[str, int]]

    @property
    def accuracy_pct(self) -> float:
        return round(self.correct / self.total * 100, 1) if self.total else 0.0


def summarize(verdicts: list[Verdict]) -> EvaluationSummary:
    counts = Counter(v.verdict for v in verdicts)
    by_scenario: dict[str, dict[str, int]] = {}
    for v in verdicts:
        bucket = by_scenario.setdefault(v.scenario, {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += v.verdict == "correct"
    return EvaluationSummary(
        total=len(verdicts),
        correct=counts.get("correct", 0),
        wrong_route=counts.get("wrong_route", 0),
        hallucinations=counts.get("hallucination", 0),
        by_scenario=dict(sorted(by_scenario.items())),
    )
