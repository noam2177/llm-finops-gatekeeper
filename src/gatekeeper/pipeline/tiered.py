"""Gate -> local model -> cloud model -> abstain.

Each document costs at most one local and one cloud call. Cloud is used only
when the local output fails a check listed in ``PipelineConfig.escalate_on``;
if the last tier still fails, the pipeline abstains and returns no output.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from gatekeeper.gates.senior_role_gate import GateDecision, senior_role_gate
from gatekeeper.llm.base import LLMProvider, ProviderError
from gatekeeper.pipeline.validation import FailureKind, validate_model_output


class ExtractionStatus(StrEnum):
    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    ABSTAIN = "ABSTAIN"


class Tier(StrEnum):
    GATE = "gate"
    LOCAL = "local"
    CLOUD = "cloud"


DEFAULT_ESCALATE_ON: frozenset[FailureKind] = frozenset(FailureKind)

_FAILURE_LABELS: dict[FailureKind, str] = {
    FailureKind.TRANSPORT: "Unavailable",
    FailureKind.INVALID_JSON: "Failed JSON Parse",
    FailureKind.SCHEMA: "Failed Schema Validation",
}


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    apply_gate: bool = True
    escalate_on: frozenset[FailureKind] = DEFAULT_ESCALATE_ON


@dataclass(frozen=True, slots=True)
class TraceStep:
    label: str
    detail: str


@dataclass(frozen=True, slots=True)
class TierAttempt:
    tier: Tier
    model: str
    failure: FailureKind | None
    detail: str
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def ok(self) -> bool:
        return self.failure is None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    filename: str
    status: ExtractionStatus
    resolved_by: Tier | None
    reason: str
    output: dict[str, Any] | None
    gate: GateDecision | None
    attempts: tuple[TierAttempt, ...] = ()
    trace: tuple[TraceStep, ...] = ()
    elapsed_ms: float = 0.0

    @property
    def local_calls(self) -> int:
        return sum(1 for a in self.attempts if a.tier is Tier.LOCAL)

    @property
    def cloud_calls(self) -> int:
        return sum(1 for a in self.attempts if a.tier is Tier.CLOUD)

    @property
    def escalated(self) -> bool:
        return self.cloud_calls > 0

    @property
    def total_tokens(self) -> int:
        return sum(a.prompt_tokens + a.completion_tokens for a in self.attempts)

    def trace_chain(self) -> str:
        return " -> ".join(f"[{step.label}]" for step in self.trace)


@dataclass(slots=True)
class _Run:
    filename: str
    started: float
    gate: GateDecision | None = None
    attempts: list[TierAttempt] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)

    def finish(
        self,
        status: ExtractionStatus,
        resolved_by: Tier | None,
        reason: str,
        output: dict[str, Any] | None = None,
    ) -> ExtractionResult:
        return ExtractionResult(
            filename=self.filename,
            status=status,
            resolved_by=resolved_by,
            reason=reason,
            output=output,
            gate=self.gate,
            attempts=tuple(self.attempts),
            trace=tuple(self.trace),
            elapsed_ms=round((time.perf_counter() - self.started) * 1000, 3),
        )


class TieredPipeline:
    def __init__(
        self,
        local: LLMProvider,
        cloud: LLMProvider | None,
        config: PipelineConfig | None = None,
    ) -> None:
        self._local = local
        self._cloud = cloud
        self._config = config or PipelineConfig()

    async def run(self, filename: str, text: str) -> ExtractionResult:
        run = _Run(filename=filename, started=time.perf_counter())

        if self._config.apply_gate:
            run.gate = senior_role_gate(text)
            if not run.gate.relevant:
                run.trace.append(
                    TraceStep("Gate Blocked", f"{run.gate.reason}, family={run.gate.family_id}")
                )
                return run.finish(
                    ExtractionStatus.BLOCKED, Tier.GATE, f"gate_blocked:{run.gate.reason}"
                )
            run.trace.append(TraceStep("Gate Passed", "anchors: " + ", ".join(run.gate.matched)))
        else:
            run.trace.append(TraceStep("Gate Skipped", "apply_gate=False"))

        local = await _attempt(Tier.LOCAL, self._local, text)
        run.attempts.append(local.attempt)
        if local.attempt.ok:
            run.trace.append(
                TraceStep("Tier 1: Local Model Passed Validation", local.attempt.model)
            )
            run.trace.append(TraceStep("Validated JSON Output", "JobPostingSchema ok"))
            return run.finish(ExtractionStatus.SUCCESS, Tier.LOCAL, "local_ok", local.output)

        failure = local.attempt.failure
        assert failure is not None
        run.trace.append(
            TraceStep(f"Tier 1: Local Model {_FAILURE_LABELS[failure]}", local.attempt.detail)
        )

        if failure not in self._config.escalate_on:
            run.trace.append(TraceStep("Abstained", f"policy keeps {failure.value} local"))
            return run.finish(
                ExtractionStatus.ABSTAIN, None, f"local_{failure.value}_not_escalated"
            )
        if self._cloud is None:
            run.trace.append(TraceStep("Abstained", "no cloud provider configured"))
            return run.finish(ExtractionStatus.ABSTAIN, None, "escalation_unavailable")

        run.trace.append(TraceStep("Tier 2: Escalating to Cloud API", self._cloud.model))
        cloud = await _attempt(Tier.CLOUD, self._cloud, text)
        run.attempts.append(cloud.attempt)
        if cloud.attempt.ok:
            run.trace.append(TraceStep("Validated JSON Output", "JobPostingSchema ok"))
            return run.finish(ExtractionStatus.SUCCESS, Tier.CLOUD, "cloud_ok", cloud.output)

        cloud_failure = cloud.attempt.failure
        assert cloud_failure is not None
        run.trace.append(
            TraceStep(f"Tier 2: Cloud Model {_FAILURE_LABELS[cloud_failure]}", cloud.attempt.detail)
        )
        run.trace.append(TraceStep("Abstained", "no tier produced a valid output"))
        return run.finish(ExtractionStatus.ABSTAIN, None, "both_tiers_failed")


@dataclass(frozen=True, slots=True)
class _TierOutcome:
    attempt: TierAttempt
    output: dict[str, Any] | None


async def _attempt(tier: Tier, provider: LLMProvider, text: str) -> _TierOutcome:
    try:
        response = await provider.complete_extraction(text)
    except ProviderError as exc:
        return _TierOutcome(
            TierAttempt(tier, provider.model, FailureKind.TRANSPORT, exc.kind), None
        )

    outcome = validate_model_output(response.text)
    attempt = TierAttempt(
        tier=tier,
        model=response.model,
        failure=outcome.failure,
        detail=outcome.detail,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
    )
    output = outcome.document.model_dump(mode="json") if outcome.document else None
    return _TierOutcome(attempt, output)
