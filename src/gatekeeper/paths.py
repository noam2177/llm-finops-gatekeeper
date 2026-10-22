"""Path confinement for every CLI path argument (OWASP A01 / CWE-22, CWE-73)."""

from __future__ import annotations

from pathlib import Path


class PathOutsideWorkspaceError(ValueError):
    pass


def confine_path(raw: str | Path, *, root: Path, must_exist: bool = False) -> Path:
    """Resolve ``raw`` (relative to ``root``) and require the result to stay inside ``root``."""
    root = root.resolve()
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PathOutsideWorkspaceError(f"path escapes workspace root: {raw}") from exc
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"path does not exist: {raw}")
    return resolved
