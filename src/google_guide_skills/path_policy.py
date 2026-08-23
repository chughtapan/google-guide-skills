"""Shared physical-path checks for generated and cached output."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TypeVar

from .errors import GoogleGuideSkillsError

ErrorT = TypeVar("ErrorT", bound=GoogleGuideSkillsError)


def checked_tree_hashes(
    path: Path,
    *,
    context: str,
    error_type: type[ErrorT],
) -> dict[str, str]:
    """Hash a directory tree after rejecting links and special files."""
    if path.is_symlink() or not path.is_dir():
        raise error_type(f"{context} must be a real directory, not a symlink")
    hashes: dict[str, str] = {}
    for candidate in sorted(path.rglob("*")):
        if candidate.is_symlink():
            raise error_type(f"{context} contains a symlink: {candidate}")
        relative = candidate.relative_to(path).as_posix()
        if candidate.is_dir():
            hashes[f"{relative}/"] = "directory"
        elif candidate.is_file():
            hashes[relative] = hashlib.sha256(candidate.read_bytes()).hexdigest()
        else:
            raise error_type(f"{context} contains a non-regular path: {candidate}")
    return hashes


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
