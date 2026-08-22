"""Synchronize pinned upstream repositories without mutating source content."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import SourceError
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .git_safe import git_dir_is_safe, repository_config_problem
from .models import Manifest, Repository
from .path_policy import require_safe_project_path

GIT_TIMEOUT_SECONDS = 300


def source_root(manifest: Manifest) -> Path:
    return manifest.project_root / ".cache" / "sources"


def checkout_path(manifest: Manifest, repository_id: str) -> Path:
    return source_root(manifest) / repository_id


def _run(args: list[str], cwd: Path | None = None) -> str:
    command = git_command(*args[1:]) if args and args[0] == "git" else args
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=(
                git_environment(cwd)
                if args and args[0] == "git" and cwd and git_dir_is_safe(cwd)
                else git_environment()
                if args and args[0] == "git"
                else None
            ),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        output = exc.stdout if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        raise SourceError(f"Command failed: {' '.join(args)}\n{output or ''}".rstrip()) from exc
    return completed.stdout.strip()


def _remote_url(path: Path) -> str:
    return _run(["git", "remote", "get-url", "origin"], cwd=path)


def sync_repository(manifest: Manifest, repository: Repository) -> Path:
    """Clone or move one cache checkout to its exact pinned commit."""

    root = require_safe_project_path(
        manifest.project_root,
        source_root(manifest),
        context="Source cache",
        error_type=SourceError,
    )
    root.mkdir(parents=True, exist_ok=True)
    target = require_safe_project_path(
        manifest.project_root,
        checkout_path(manifest, repository.id),
        context="Source checkout",
        error_type=SourceError,
    )
    created = not target.exists()
    if created:
        target.mkdir()
        _run(["git", "init", "--quiet", "--template="], cwd=target)
        _run(["git", "remote", "add", "origin", repository.url], cwd=target)
    elif not git_dir_is_safe(target):
        raise SourceError(
            f"Refusing to replace non-git cache path {target}. Move it aside and retry."
        )

    if not created:
        config_problem = repository_config_problem(
            target, repository.url, repository.default_branch
        )
        if config_problem:
            raise SourceError(
                f"Cache checkout {target} has unsafe local Git config: {config_problem}. "
                "Move it aside and retry."
            )

    actual_remote = _remote_url(target)
    accepted = {repository.url, repository.url.removesuffix(".git")}
    if actual_remote not in accepted and actual_remote.removesuffix(".git") not in accepted:
        raise SourceError(
            f"Cache checkout {target} points to {actual_remote}, expected {repository.url}. "
            "Move it aside and retry."
        )

    replacements = _run(["git", "replace", "--list"], cwd=target)
    if replacements:
        raise SourceError(f"Cache checkout {target} contains forbidden Git replacement refs")

    has_revision = (
        subprocess.run(
            git_command("cat-file", "-e", f"{repository.revision}^{{commit}}"),
            cwd=target,
            env=git_environment(target),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        ).returncode
        == 0
    )
    if not has_revision:
        _run(["git", "fetch", "--depth", "1", "origin", repository.revision], cwd=target)

    status = _run(["git", "status", "--porcelain"], cwd=target)
    if status:
        raise SourceError(
            f"Cache checkout {target} has local changes. The generator will not overwrite them."
        )
    _run(["git", "checkout", "--detach", repository.revision], cwd=target)
    actual_revision = _run(["git", "rev-parse", "HEAD"], cwd=target)
    if actual_revision != repository.revision:
        raise SourceError(
            f"Checkout verification failed for {repository.id}: {actual_revision} != "
            f"{repository.revision}"
        )
    return target


def sync(manifest: Manifest, repository_ids: list[str] | None = None) -> list[Path]:
    ids = repository_ids or list(manifest.repositories)
    unknown = sorted(set(ids) - set(manifest.repositories))
    if unknown:
        raise SourceError(f"Unknown repositories: {', '.join(unknown)}")
    return [sync_repository(manifest, manifest.repositories[repo_id]) for repo_id in ids]
