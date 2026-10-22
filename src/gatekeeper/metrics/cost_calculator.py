"""FinOps ROI: what the gatekeeper actually spent versus sending every document to the cloud."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

PROJECTION_DOCS = 10_000


@dataclass(frozen=True, slots=True)
class PricingModel:
    """USD per document (baseline) and per model call (gatekeeper tiers)."""

    naive_cloud_per_doc: float = 0.015
    local_per_call: float = 0.0002
    cloud_per_call: float = 0.015

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PricingModel:
        source = os.environ if env is None else env
        defaults = cls()

        def read(name: str, default: float) -> float:
            raw = source.get(name, "").strip()
            if not raw:
                return default
            value = float(raw)
            if value < 0:
                raise ValueError(f"{name} must be >= 0")
            return value

        return cls(
            naive_cloud_per_doc=read(
                "GATEKEEPER_PRICE_NAIVE_CLOUD_PER_DOC", defaults.naive_cloud_per_doc
            ),
            local_per_call=read("GATEKEEPER_PRICE_LOCAL_PER_CALL", defaults.local_per_call),
            cloud_per_call=read("GATEKEEPER_PRICE_CLOUD_PER_CALL", defaults.cloud_per_call),
        )


@dataclass(frozen=True, slots=True)
class CostRecord:
    filename: str
    outcome: str
    local_calls: int
    cloud_calls: int
    tokens: int
    baseline_usd: float
    actual_usd: float


@dataclass(frozen=True, slots=True)
class CostSummary:
    documents: int
    blocked_at_gate: int
    solved_local: int
    solved_cloud: int
    abstained: int
    baseline_cloud_calls: int
    actual_cloud_calls: int
    actual_local_calls: int
    gate_tokens_spent: int
    baseline_usd: float
    actual_usd: float
    saved_usd: float
    cloud_calls_saved_pct: float
    cost_saved_pct: float
    baseline_per_10k_usd: float
    actual_per_10k_usd: float
    saved_per_10k_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CostLedger:
    pricing: PricingModel = field(default_factory=PricingModel)
    records: list[CostRecord] = field(default_factory=list)

    def record(
        self,
        filename: str,
        *,
        outcome: str,
        local_calls: int,
        cloud_calls: int,
        tokens: int = 0,
    ) -> CostRecord:
        """``outcome`` is one of: blocked, local, cloud, abstain."""
        entry = CostRecord(
            filename=filename,
            outcome=outcome,
            local_calls=local_calls,
            cloud_calls=cloud_calls,
            tokens=tokens,
            baseline_usd=self.pricing.naive_cloud_per_doc,
            actual_usd=local_calls * self.pricing.local_per_call
            + cloud_calls * self.pricing.cloud_per_call,
        )
        self.records.append(entry)
        return entry

    def summary(self) -> CostSummary:
        n = len(self.records)
        baseline = sum(r.baseline_usd for r in self.records)
        actual = sum(r.actual_usd for r in self.records)
        cloud_calls = sum(r.cloud_calls for r in self.records)

        def per_10k(total: float) -> float:
            return round(total / n * PROJECTION_DOCS, 2) if n else 0.0

        return CostSummary(
            documents=n,
            blocked_at_gate=self._count("blocked"),
            solved_local=self._count("local"),
            solved_cloud=self._count("cloud"),
            abstained=self._count("abstain"),
            baseline_cloud_calls=n,
            actual_cloud_calls=cloud_calls,
            actual_local_calls=sum(r.local_calls for r in self.records),
            gate_tokens_spent=sum(r.tokens for r in self.records if r.outcome == "blocked"),
            baseline_usd=round(baseline, 6),
            actual_usd=round(actual, 6),
            saved_usd=round(baseline - actual, 6),
            cloud_calls_saved_pct=round((1 - cloud_calls / n) * 100, 1) if n else 0.0,
            cost_saved_pct=round((1 - actual / baseline) * 100, 1) if baseline else 0.0,
            baseline_per_10k_usd=per_10k(baseline),
            actual_per_10k_usd=per_10k(actual),
            saved_per_10k_usd=per_10k(baseline - actual),
        )

    def _count(self, outcome: str) -> int:
        return sum(1 for r in self.records if r.outcome == outcome)


def render_finops_table(summary: CostSummary, pricing: PricingModel) -> str:
    """Markdown table that also reads cleanly as plain console text."""
    rows = [
        ("Documents processed", f"{summary.documents}"),
        ("Blocked at CPU gate (0 LLM tokens)", f"{summary.blocked_at_gate}"),
        ("Solved by local model", f"{summary.solved_local}"),
        ("Solved after cloud escalation", f"{summary.solved_cloud}"),
        ("Abstained (no output returned)", f"{summary.abstained}"),
        ("Cloud calls: naive baseline", f"{summary.baseline_cloud_calls}"),
        ("Cloud calls: gatekeeper", f"{summary.actual_cloud_calls}"),
        ("**Total % cloud calls saved**", f"**{summary.cloud_calls_saved_pct:.1f}%**"),
        ("Cost: naive baseline", f"${summary.baseline_usd:,.4f}"),
        ("Cost: gatekeeper", f"${summary.actual_usd:,.4f}"),
        ("Cost reduction", f"{summary.cost_saved_pct:.1f}%"),
        ("Projected cost per 10,000 docs: baseline", f"${summary.baseline_per_10k_usd:,.2f}"),
        ("Projected cost per 10,000 docs: gatekeeper", f"${summary.actual_per_10k_usd:,.2f}"),
        ("**Estimated $ saved per 10,000 docs**", f"**${summary.saved_per_10k_usd:,.2f}**"),
    ]
    width = max(len(label) for label, _ in rows)
    value_width = max(len(value) for _, value in rows)
    lines = [
        f"| {'Metric'.ljust(width)} | {'Value'.rjust(value_width)} |",
        f"|{'-' * (width + 2)}|{'-' * (value_width + 1)}:|",
    ]
    lines += [f"| {label.ljust(width)} | {value.rjust(value_width)} |" for label, value in rows]
    lines.append("")
    lines.append(
        f"Pricing: naive cloud ${pricing.naive_cloud_per_doc}/doc; "
        f"local ${pricing.local_per_call}/call; cloud ${pricing.cloud_per_call}/call."
    )
    return "\n".join(lines)
