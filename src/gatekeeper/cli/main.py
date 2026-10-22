"""``python -m gatekeeper {benchmark,extract}``.

All path arguments are confined to the current working directory, so run the
CLI from the repository root.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from gatekeeper.cli.report import (
    BenchmarkRun,
    render_benchmark_markdown,
    render_console_report,
    write_artifacts,
)
from gatekeeper.config import Settings
from gatekeeper.llm import MockLLMProvider, OllamaProvider, OpenAICompatibleProvider
from gatekeeper.llm.base import LLMProvider
from gatekeeper.metrics import CostLedger, PricingModel, load_ground_truth, score, summarize
from gatekeeper.paths import PathOutsideWorkspaceError, confine_path
from gatekeeper.pipeline import ExtractionResult, ExtractionStatus, PipelineConfig, TieredPipeline

log = logging.getLogger("gatekeeper")


def build_pipeline(*, dry_run: bool, apply_gate: bool, settings: Settings) -> TieredPipeline:
    config = PipelineConfig(apply_gate=apply_gate)
    if dry_run:
        return TieredPipeline(MockLLMProvider("local"), MockLLMProvider("cloud"), config)

    local = OllamaProvider(
        settings.local_model, settings.ollama_base_url, timeout_s=settings.request_timeout_s
    )
    cloud: LLMProvider | None = None
    if settings.cloud_api_key:
        cloud = OpenAICompatibleProvider(
            settings.cloud_model,
            settings.cloud_base_url,
            settings.cloud_api_key,
            timeout_s=settings.request_timeout_s,
        )
    else:
        log.warning("GATEKEEPER_CLOUD_API_KEY not set: local failures will abstain")
    return TieredPipeline(local, cloud, config)


def ledger_outcome(result: ExtractionResult) -> str:
    if result.status is ExtractionStatus.BLOCKED:
        return "blocked"
    if result.status is ExtractionStatus.SUCCESS and result.resolved_by is not None:
        return result.resolved_by.value
    return "abstain"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


async def _benchmark(args: argparse.Namespace, root: Path) -> int:
    input_dir = confine_path(args.input_dir, root=root, must_exist=True)
    truth_path = confine_path(args.ground_truth, root=root, must_exist=True)
    output_dir = confine_path(args.output_dir, root=root)
    markdown_out = confine_path(args.markdown_out, root=root) if args.markdown_out else None

    files = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix == ".txt")
    if args.limit:
        files = files[: args.limit]
    if not files:
        log.error("no .txt fixtures in %s", input_dir.name)
        return 1

    truth = load_ground_truth(truth_path)
    pipeline = build_pipeline(
        dry_run=args.dry_run, apply_gate=not args.no_gate, settings=Settings.from_env()
    )
    pricing = PricingModel.from_env()
    ledger = CostLedger(pricing)
    results: list[ExtractionResult] = []
    verdicts = []

    for path in files:
        result = await pipeline.run(path.name, _read_text(path))
        results.append(result)
        ledger.record(
            path.name,
            outcome=ledger_outcome(result),
            local_calls=result.local_calls,
            cloud_calls=result.cloud_calls,
            tokens=result.total_tokens,
        )
        if path.name in truth:
            verdicts.append(score(result, truth[path.name]))
        log.info("%s status=%s reason=%s", path.name, result.status.value, result.reason)

    run = BenchmarkRun(
        mode="dry-run (MockLLMProvider)" if args.dry_run else "live (Ollama + cloud API)",
        results=results,
        verdicts=verdicts,
        evaluation=summarize(verdicts),
        cost=ledger.summary(),
        pricing=pricing,
    )
    print(render_console_report(run))
    write_artifacts(run, output_dir)
    if markdown_out:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(render_benchmark_markdown(run), encoding="utf-8")
    return 0 if run.evaluation.hallucinations == 0 else 2


async def _extract(args: argparse.Namespace, root: Path) -> int:
    path = confine_path(args.file, root=root, must_exist=True)
    pipeline = build_pipeline(
        dry_run=args.dry_run, apply_gate=not args.no_gate, settings=Settings.from_env()
    )
    result = await pipeline.run(path.name, _read_text(path))

    if args.explain:
        print(f"Trace for {path.name}")
        for index, step in enumerate(result.trace, start=1):
            print(f"  {index}. [{step.label}]  {step.detail}")
        for attempt in result.attempts:
            outcome = "ok" if attempt.failure is None else attempt.failure.value
            print(
                f"     tier={attempt.tier.value} model={attempt.model} "
                f"tokens={attempt.prompt_tokens}+{attempt.completion_tokens} result={outcome}"
            )
        print()
        print(result.trace_chain())
        print()

    print(
        json.dumps(
            {
                "filename": result.filename,
                "status": result.status.value,
                "resolved_by": result.resolved_by.value if result.resolved_by else None,
                "reason": result.reason,
                "output": result.output,
            },
            indent=2,
        )
    )
    return 0 if result.status is not ExtractionStatus.ABSTAIN else 3


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gatekeeper", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--dry-run", action="store_true", help="use deterministic mock models (no keys, no network)"
    )
    common.add_argument("--no-gate", action="store_true", help="skip the CPU relevance gate")

    bench = sub.add_parser("benchmark", parents=[common], help="run fixtures and print FinOps ROI")
    bench.add_argument("--input-dir", default="data/fixtures")
    bench.add_argument("--ground-truth", default="data/ground_truth.csv")
    bench.add_argument("--output-dir", default="reports")
    bench.add_argument("--markdown-out", default=None, help="also write a Markdown report here")
    bench.add_argument("--limit", type=int, default=None)

    extract = sub.add_parser("extract", parents=[common], help="extract a single document")
    extract.add_argument("--file", required=True)
    extract.add_argument("--explain", action="store_true", help="print a step-by-step trace")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = _parser().parse_args(argv)
    root = Path.cwd().resolve()
    load_dotenv(root / ".env")
    handler = _benchmark if args.command == "benchmark" else _extract
    try:
        return asyncio.run(handler(args, root))
    except (PathOutsideWorkspaceError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
