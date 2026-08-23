"""Shared physical-path checks for generated and cached output."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from .errors import GoogleGuideSkillsError

ErrorT = TypeVar("ErrorT", bound=GoogleGuideSkillsError)


def require_safe_project_path(
    project_root: Path,
    path: Path,
    *,
    context: str,
    error_type: type[ErrorT],
) -> Path:
    """Reject lexical escapes and every existing symlink component."""
    root = project_root.resolve()
    absolute = path if path.is_absolute() else project_root / path
    try:
        relative = absolute.relative_to(project_root)
    except ValueError as exc:
        raise error_type(f"{context} escapes the project root: {path}") from exc
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise error_type(f"{context} may not contain symlinks: {current}")
    try:
        absolute.resolve().relative_to(root)
    except ValueError as exc:
        raise error_type(f"{context} resolves outside the project root: {path}") from exc
    return absolute
