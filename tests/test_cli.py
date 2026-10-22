from __future__ import annotations

import json
from pathlib import Path

import pytest

from gatekeeper.cli.main import main
from gatekeeper.paths import PathOutsideWorkspaceError, confine_path


def test_confine_path_accepts_inside(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    assert confine_path("data", root=tmp_path, must_exist=True) == (tmp_path / "data").resolve()


@pytest.mark.parametrize("raw", ["../outside", "data/../../x"])
def test_confine_path_rejects_traversal(tmp_path: Path, raw: str) -> None:
    with pytest.raises(PathOutsideWorkspaceError):
        confine_path(raw, root=tmp_path)


def test_extract_explain(repo_cwd: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["extract", "--file", "data/fixtures/sample_escalation.txt", "--dry-run", "--explain"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Failed Schema Validation" in out
    assert "Escalating to Cloud API" in out
    payload = json.loads(out[out.index("{") :])
    assert payload["resolved_by"] == "cloud"


def test_extract_abstain_exit_code(repo_cwd: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["extract", "--file", "data/fixtures/sample_abstain_corrupted.txt", "--dry-run"])
    assert code == 3
    assert json.loads(capsys.readouterr().out)["output"] is None


def test_benchmark_dry_run(repo_cwd: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = Path("reports") / "pytest"
    code = main(["benchmark", "--dry-run", "--output-dir", str(output_dir)])
    out = capsys.readouterr().out
    assert code == 0
    assert "**65.0%**" in out
    summary = json.loads((repo_cwd / output_dir / "benchmark_summary.json").read_text("utf-8"))
    assert summary["evaluation"]["hallucinations"] == 0
    assert summary["cost"]["actual_cloud_calls"] == 7
