"""Install generated skills into user or project agent directories."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from .errors import GoogleGuideSkillsError
from .metrics import CODEX_FALLBACK_METADATA_CHARS, metadata_budget_records
from .models import Manifest
from .packs import select_skills
from .path_policy import checked_tree_hashes, require_safe_project_path
from .strict_yaml import strict_safe_load

DEFAULT_AGENTS = ("codex", "claude-code")
SKILLS_CLI_PACKAGE = "skills@1.5.23"
INSTALL_TIMEOUT_SECONDS = 300
MAX_EXISTING_SKILL_ENTRIES = 10_000
SWE_BOOK_COLLECTION_ID = "software-engineering-at-google"
PROJECT_SKILL_ROOTS = {
    "codex": Path(".agents/skills"),
    "claude-code": Path(".claude/skills"),
}


@dataclass(frozen=True)
class InstallLinkAction:
    """One checked skill link operation."""

    agent: str
    skill: str
    distribution: str
    source: Path
    destination: Path
    status: str


def minimal_process_env(home: Path | None = None) -> dict[str, str]:
    """Pass only runtime/network basics to third-party subprocesses."""
    allowed = {
        "PATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "NODE_EXTRA_CA_CERTS",
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    if home is not None:
        env["HOME"] = str(home)
        env["XDG_CONFIG_HOME"] = str(home / ".config")
        env["XDG_CACHE_HOME"] = str(home / ".cache")
        env["npm_config_cache"] = str(home / ".npm")
        env["npm_config_userconfig"] = os.devnull
        env["npm_config_update_notifier"] = "false"
    return env


def _user_skill_root(agent: str, user_home: Path | None) -> Path:
    home = (user_home or Path.home()).expanduser().resolve()
    if agent == "codex":
        configured = os.environ.get("CODEX_HOME") if user_home is None else None
        agent_home = Path(configured).expanduser() if configured else home / ".codex"
    elif agent == "claude-code":
        configured = os.environ.get("CLAUDE_CONFIG_DIR") if user_home is None else None
        agent_home = Path(configured).expanduser() if configured else home / ".claude"
    else:
        raise GoogleGuideSkillsError(f"Unsupported user-level install agent: {agent}")
    if not agent_home.is_absolute():
        raise GoogleGuideSkillsError(f"Agent home must be absolute: {agent_home}")
    skill_root = agent_home / "skills"
    if skill_root in {Path("/"), home}:
        raise GoogleGuideSkillsError(f"Refusing broad user skill root: {skill_root}")
    return skill_root


def _project_skill_root(agent: str, project: Path) -> Path:
    if agent not in PROJECT_SKILL_ROOTS:
        raise GoogleGuideSkillsError(f"Unsupported project install agent: {agent}")
    project = project.expanduser()
    if not project.is_dir():
        raise GoogleGuideSkillsError(f"Install project does not exist: {project}")
    project = project.resolve(strict=True)
    skill_root = project / PROJECT_SKILL_ROOTS[agent]
    if not skill_root.resolve(strict=False).is_relative_to(project):
        raise GoogleGuideSkillsError(f"Project skill root escapes the project: {skill_root}")
    return skill_root


def _install_skill_root(
    agent: str,
    user_home: Path | None,
    project: Path | None,
) -> Path:
    if project is None:
        return _user_skill_root(agent, user_home)
    if user_home is not None:
        raise GoogleGuideSkillsError("user_home cannot be combined with a project install")
    return _project_skill_root(agent, project)


def selected_install_skills(
    manifest: Manifest,
    skills: list[str] | None,
    packs: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Return selected committed and local-only skill names."""
    distributions = {
        artifact.name: collection.distribution
        for collection, artifact in manifest.artifacts(include_local=True)
    }
    requested = set(select_skills(manifest, skills, packs))
    committed = sorted(name for name in requested if distributions[name] == "committed")
    local = sorted(name for name in requested if distributions[name] == "local-only")
    return committed, local


def _existing_skill_files(root: Path, replaced: set[str]) -> list[Path]:
    """Find nested skills through directory links without following cycles."""
    if not root.exists() and not root.is_symlink():
        return []
    pending: list[tuple[Path, frozenset[Path]]] = [(root, frozenset())]
    files: list[Path] = []
    entries = 0
    try:
        while pending:
            directory, ancestors = pending.pop()
            canonical = directory.resolve(strict=True)
            if canonical in ancestors:
                continue
            ancestors = ancestors | {canonical}
            for path in directory.iterdir():
                entries += 1
                if entries > MAX_EXISTING_SKILL_ENTRIES:
                    raise GoogleGuideSkillsError(
                        f"Cannot budget installed skills at {root}: "
                        f"scan exceeds {MAX_EXISTING_SKILL_ENTRIES} entries"
                    )
                if path.name.startswith(".") or (directory == root and path.name in replaced):
                    continue
                if path.name == "SKILL.md" and path.is_file():
                    files.append(path)
                elif path.is_dir():
                    pending.append((path, ancestors))
    except (OSError, RuntimeError) as exc:
        raise GoogleGuideSkillsError(f"Cannot scan installed skills at {root}: {exc}") from exc
    return sorted(files)


def preflight_install_budget(
    manifest: Manifest,
    agents: list[str],
    skills: list[str],
    *,
    project: Path | None = None,
    user_home: Path | None = None,
) -> None:
    """Reject an overflowing resulting directory before changing either agent's files."""
    proposed = {
        artifact.name: artifact.description
        for _, artifact in manifest.artifacts(include_local=True)
        if artifact.name in skills
    }
    for agent in agents:
        root = _install_skill_root(agent, user_home, project)
        records = dict(proposed)
        display_names: dict[str, str] = {}
        for path in _existing_skill_files(root, set(proposed)):
            relative = path.parent.relative_to(root).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
                parts = text.split("\n---\n", 1) if text.startswith("---\n") else []
                metadata = strict_safe_load(parts[0][4:]) if len(parts) == 2 else None
                if not isinstance(metadata, dict) or not all(
                    isinstance(metadata.get(key), str) and metadata[key].strip()
                    for key in ("name", "description")
                ):
                    raise ValueError("Missing name or description")
            except (OSError, ValueError, yaml.YAMLError) as exc:
                raise GoogleGuideSkillsError(f"Cannot budget installed skill: {path}") from exc
            records[relative] = metadata["description"]
            display_names[relative] = metadata["name"]
        budget = metadata_budget_records(
            list(records.items()), install_root=str(root), display_names=display_names
        )
        if budget["codex_list_chars"] > CODEX_FALLBACK_METADATA_CHARS:
            raise GoogleGuideSkillsError(
                f"Install metadata at {root} would use {budget['codex_list_chars']} characters "
                f"(limit {CODEX_FALLBACK_METADATA_CHARS}). Select fewer packs/skills or use a "
                "separate project. No skills were installed or removed."
            )


def swe_book_license_notice(manifest: Manifest) -> str:
    """Return the license notice shown before SWE-book installation."""
    collection = manifest.collections[SWE_BOOK_COLLECTION_ID]
    license_info = manifest.license_for(collection)
    notice = (
        "Software Engineering at Google material is licensed under "
        f"{license_info.name} ({license_info.spdx}). Review {license_info.url} and use the "
        "generated skills only as the license permits."
    )
    return f"{notice} {license_info.warning}" if license_info.warning else notice


def require_swe_book_license_acceptance(
    manifest: Manifest,
    *,
    accepted: bool,
    prompt: Callable[[str], str] | None = None,
) -> str:
    """Require explicit acceptance before installing generated SWE-book skills."""
    notice = swe_book_license_notice(manifest)
    if accepted:
        return notice
    if prompt is None:
        if not sys.stdin.isatty():
            raise GoogleGuideSkillsError(
                f"SWE-book installation requires license acceptance. {notice} "
                "Rerun with --accept-swe-book-license to continue."
            )
        prompt = input
    answer = prompt(f"{notice}\nAccept this license for this installation? [y/N] ")
    if answer.strip().lower() not in {"y", "yes"}:
        raise GoogleGuideSkillsError(
            "SWE-book license was not accepted; installation stopped before changing files"
        )
    return notice


def _available_link_skills(manifest: Manifest, include_local: bool) -> dict[str, tuple[Path, str]]:
    available: dict[str, tuple[Path, str]] = {}
    for collection, artifact in manifest.artifacts(include_local=True):
        if collection.distribution == "local-only" and not include_local:
            continue
        available[artifact.name] = (
            manifest.root_for(collection.distribution) / artifact.name,
            collection.distribution,
        )
    return available


def _resolve_link_sources(
    manifest: Manifest,
    available: dict[str, tuple[Path, str]],
    requested: set[str],
    *,
    dry_run: bool,
) -> tuple[dict[str, tuple[Path, str]], dict[str, dict[str, str] | None]]:
    resolved = dict(available)
    hashes: dict[str, dict[str, str] | None] = {}
    for name in sorted(requested):
        source, distribution = available[name]
        source = require_safe_project_path(
            manifest.project_root,
            source,
            context=f"Generated skill {name}",
            error_type=GoogleGuideSkillsError,
        )
        if not source.is_dir():
            if dry_run and distribution == "local-only":
                resolved[name] = source, distribution
                hashes[name] = None
                continue
            hint = (
                "; run `google-guides all --include-swe-book` first"
                if distribution == "local-only"
                else ""
            )
            raise GoogleGuideSkillsError(f"Generated skill does not exist: {source}{hint}")
        skill_file = source / "SKILL.md"
        if skill_file.is_symlink() or not skill_file.is_file():
            raise GoogleGuideSkillsError(f"Generated skill is missing SKILL.md: {source}")
        resolved[name] = source, distribution
        hashes[name] = checked_tree_hashes(
            source,
            context=f"Generated skill {name}",
            error_type=GoogleGuideSkillsError,
        )
    return resolved, hashes


def _link_status(
    destination: Path,
    source: Path,
    source_hashes: dict[str, str] | None,
    skill: str,
    dry_run: bool,
) -> str:
    if destination.is_symlink():
        try:
            matches = destination.resolve(strict=True) == source.resolve(strict=True)
        except FileNotFoundError:
            matches = False
        if not matches:
            raise GoogleGuideSkillsError(
                f"Skill destination is an unrelated symlink: {destination}"
            )
        return "already-linked"
    if destination.exists():
        if source_hashes is None:
            raise GoogleGuideSkillsError(
                f"Generate {skill} before checking the existing destination: {destination}"
            )
        if (
            not destination.is_dir()
            or checked_tree_hashes(
                destination,
                context=f"Installed skill {skill}",
                error_type=GoogleGuideSkillsError,
            )
            != source_hashes
        ):
            raise GoogleGuideSkillsError(
                f"Skill destination already exists with different content: {destination}"
            )
        return "would-relink" if dry_run else "relinked"
    return "would-link" if dry_run else "linked"


def _replace_identical_copy_with_link(action: InstallLinkAction) -> None:
    """Replace a verified identical copy and restore it if link creation fails."""
    with tempfile.TemporaryDirectory(
        prefix=f".{action.skill}-backup-", dir=action.destination.parent
    ) as temporary:
        backup = Path(temporary) / action.skill
        action.destination.replace(backup)
        try:
            action.destination.symlink_to(action.source, target_is_directory=True)
        except OSError:
            backup.replace(action.destination)
            raise


def _apply_install_link(action: InstallLinkAction) -> None:
    action.destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if action.status == "relinked":
        _replace_identical_copy_with_link(action)
    else:
        action.destination.symlink_to(action.source, target_is_directory=True)


def _plan_install_links(
    agents: list[str],
    requested: set[str],
    available: dict[str, tuple[Path, str]],
    source_hashes: dict[str, dict[str, str] | None],
    dry_run: bool,
    user_home: Path | None,
    project: Path | None,
) -> list[InstallLinkAction]:
    planned: list[InstallLinkAction] = []
    for agent in agents:
        destination_root = _install_skill_root(agent, user_home, project)
        if destination_root.is_symlink():
            raise GoogleGuideSkillsError(
                f"Skill root must be a real directory, not a symlink: {destination_root}"
            )
        if destination_root.exists() and not destination_root.is_dir():
            raise GoogleGuideSkillsError(f"Skill root is not a directory: {destination_root}")
        for name in sorted(requested):
            source, distribution = available[name]
            destination = destination_root / name
            planned.append(
                InstallLinkAction(
                    agent=agent,
                    skill=name,
                    distribution=distribution,
                    source=source.resolve(),
                    destination=destination,
                    status=_link_status(
                        destination,
                        source,
                        source_hashes[name],
                        name,
                        dry_run,
                    ),
                )
            )
    return planned


def install_links(
    manifest: Manifest,
    agents: list[str],
    skills: list[str] | None = None,
    *,
    include_local: bool = False,
    dry_run: bool = False,
    user_home: Path | None = None,
    project: Path | None = None,
) -> list[InstallLinkAction]:
    """Symlink generated skills into user or project agent directories."""
    if not agents:
        raise GoogleGuideSkillsError("Select at least one target agent")
    available = _available_link_skills(manifest, include_local)
    requested = set(skills) if skills is not None else set(select_skills(manifest)) & set(available)
    unknown = sorted(requested - set(available))
    if unknown:
        raise GoogleGuideSkillsError(
            "Selected skills are unavailable under the current distribution policy: "
            + ", ".join(unknown)
        )
    preflight_install_budget(
        manifest, agents, sorted(requested), project=project, user_home=user_home
    )
    available, source_hashes = _resolve_link_sources(
        manifest,
        available,
        requested,
        dry_run=dry_run,
    )
    planned = _plan_install_links(
        agents,
        requested,
        available,
        source_hashes,
        dry_run,
        user_home,
        project,
    )
    if dry_run:
        return planned
    for action in planned:
        if action.status not in {"linked", "relinked"}:
            continue
        try:
            _apply_install_link(action)
        except OSError as exc:
            raise GoogleGuideSkillsError(
                f"Could not create skill link {action.destination}: {exc}"
            ) from exc
    return planned


def _committed_skills(manifest: Manifest) -> set[str]:
    return {artifact.name for _collection, artifact in manifest.artifacts(include_local=False)}


def _install_command(
    source: Path,
    agents: list[str],
    selected: list[str],
    copy: bool,
) -> list[str]:
    command = ["npx", "--yes", SKILLS_CLI_PACKAGE, "add", str(source)]
    for agent in agents:
        command.extend(["--agent", agent])
    for skill in selected:
        command.extend(["--skill", skill])
    command.append("--yes")
    if copy:
        command.append("--copy")
    return command


def install_commands(
    manifest: Manifest,
    project: Path,
    agents: list[str],
    skills: list[str] | None = None,
    copy: bool = False,
) -> list[list[str]]:
    """Build a `skills` CLI command for committed skills in one project."""
    if not agents:
        raise GoogleGuideSkillsError("Select at least one target agent")
    if not project.is_dir():
        raise GoogleGuideSkillsError(f"Install project does not exist: {project}")
    source = manifest.root_for("committed")
    if not source.is_dir():
        raise GoogleGuideSkillsError(f"Generated skill root does not exist: {source}")
    available = _committed_skills(manifest)
    requested = set(skills) if skills is not None else None
    if requested is not None:
        unknown = sorted(requested - available)
        if unknown:
            raise GoogleGuideSkillsError(
                "Selected skills are unavailable under the current distribution policy: "
                + ", ".join(unknown)
            )
    selected = sorted(
        requested if requested is not None else set(select_skills(manifest)) & available
    )
    preflight_install_budget(manifest, agents, selected, project=project)
    return [_install_command(source, agents, selected, copy)] if selected else []


def _execute_install_commands(project: Path, commands: list[list[str]]) -> None:
    with tempfile.TemporaryDirectory(prefix="google-guides-npx-home-") as temporary:
        env = minimal_process_env(Path(temporary))
        for command in commands:
            try:
                subprocess.run(
                    command,
                    cwd=project,
                    env=env,
                    timeout=INSTALL_TIMEOUT_SECONDS,
                    check=True,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise GoogleGuideSkillsError(
                    f"Skill installation failed: {' '.join(command)}"
                ) from exc


def install(
    manifest: Manifest,
    project: Path,
    agents: list[str],
    skills: list[str] | None = None,
    copy: bool = False,
    dry_run: bool = False,
) -> list[list[str]]:
    """Install redistributable skills into an explicit project."""
    if shutil.which("npx") is None:
        raise GoogleGuideSkillsError("npx is required; install a current Node.js release")
    commands = install_commands(
        manifest,
        project.resolve(),
        agents,
        skills=skills,
        copy=copy,
    )
    if dry_run:
        return commands
    _execute_install_commands(project, commands)
    return commands
