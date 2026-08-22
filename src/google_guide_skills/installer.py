"""Install generated skills through the open `skills` CLI."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .errors import GoogleGuideSkillsError
from .models import Manifest
from .path_policy import require_safe_project_path

DEFAULT_AGENTS = ("codex", "claude-code")
SKILLS_CLI_PACKAGE = "skills@1.5.23"
INSTALL_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class UserInstallAction:
    """One checked user-level skill link operation."""

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


def _inside_local_eval_boundary(manifest: Manifest, project: Path) -> bool:
    boundary = (manifest.project_root / "evals" / "results").resolve()
    try:
        project.resolve().relative_to(boundary)
    except ValueError:
        return False
    return True


def _checked_tree_hashes(path: Path, context: str) -> dict[str, str]:
    if path.is_symlink() or not path.is_dir():
        raise GoogleGuideSkillsError(f"{context} must be a real directory")
    hashes: dict[str, str] = {}
    for candidate in sorted(path.rglob("*")):
        if candidate.is_symlink():
            raise GoogleGuideSkillsError(f"{context} contains a symlink: {candidate}")
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise GoogleGuideSkillsError(f"{context} contains a non-regular path: {candidate}")
        hashes[candidate.relative_to(path).as_posix()] = hashlib.sha256(
            candidate.read_bytes()
        ).hexdigest()
    return hashes


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


def install_user_links(
    manifest: Manifest,
    agents: list[str],
    skills: list[str] | None = None,
    *,
    include_local: bool = False,
    dry_run: bool = False,
    user_home: Path | None = None,
) -> list[UserInstallAction]:
    """Symlink generated skills into user agent homes without exporting local-only bytes."""

    if not agents:
        raise GoogleGuideSkillsError("Select at least one target agent")
    available: dict[str, tuple[Path, str]] = {
        "google-guides-index": (
            manifest.root_for("committed") / "google-guides-index",
            "committed",
        )
    }
    for collection, artifact in manifest.artifacts(include_local=True):
        if collection.distribution == "local-only" and not include_local:
            continue
        available[artifact.name] = (
            manifest.root_for(collection.distribution) / artifact.name,
            collection.distribution,
        )
    requested = set(skills) if skills is not None else set(available)
    unknown = sorted(requested - set(available))
    if unknown:
        raise GoogleGuideSkillsError(
            "Selected skills are unavailable under the current distribution policy: "
            + ", ".join(unknown)
        )

    source_hashes: dict[str, dict[str, str]] = {}
    for name in sorted(requested):
        source, distribution = available[name]
        source = require_safe_project_path(
            manifest.project_root,
            source,
            context=f"Generated skill {name}",
            error_type=GoogleGuideSkillsError,
        )
        if not source.is_dir():
            hint = (
                "; run `google-guides all --include-swe-book` first"
                if distribution == "local-only"
                else ""
            )
            raise GoogleGuideSkillsError(f"Generated skill does not exist: {source}{hint}")
        if (source / "SKILL.md").is_symlink() or not (source / "SKILL.md").is_file():
            raise GoogleGuideSkillsError(f"Generated skill is missing SKILL.md: {source}")
        available[name] = (source, distribution)
        source_hashes[name] = _checked_tree_hashes(source, f"Generated skill {name}")

    planned: list[UserInstallAction] = []
    for agent in agents:
        destination_root = _user_skill_root(agent, user_home)
        if destination_root.is_symlink():
            raise GoogleGuideSkillsError(
                f"User skill root must be a real directory, not a symlink: {destination_root}"
            )
        if destination_root.exists() and not destination_root.is_dir():
            raise GoogleGuideSkillsError(
                f"User skill root is not a directory: {destination_root}"
            )
        for name in sorted(requested):
            source, distribution = available[name]
            destination = destination_root / name
            if destination.is_symlink():
                try:
                    matches = destination.resolve(strict=True) == source.resolve(strict=True)
                except FileNotFoundError:
                    matches = False
                if not matches:
                    raise GoogleGuideSkillsError(
                        f"User skill destination is an unrelated symlink: {destination}"
                    )
                status = "already-linked"
            elif destination.exists():
                if not destination.is_dir() or _checked_tree_hashes(
                    destination, f"Installed skill {name}"
                ) != source_hashes[name]:
                    raise GoogleGuideSkillsError(
                        f"User skill destination already exists with different content: "
                        f"{destination}"
                    )
                status = "already-identical"
            else:
                status = "would-link" if dry_run else "linked"
            planned.append(
                UserInstallAction(
                    agent=agent,
                    skill=name,
                    distribution=distribution,
                    source=source.resolve(),
                    destination=destination,
                    status=status,
                )
            )

    if dry_run:
        return planned
    for action in planned:
        if action.status != "linked":
            continue
        action.destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            action.destination.symlink_to(action.source, target_is_directory=True)
        except OSError as exc:
            raise GoogleGuideSkillsError(
                f"Could not create user skill link {action.destination}: {exc}"
            ) from exc
    return planned


def install_commands(
    manifest: Manifest,
    project: Path,
    agents: list[str],
    skills: list[str] | None = None,
    include_local: bool = False,
    copy: bool = False,
    global_install: bool = False,
) -> list[list[str]]:
    if not agents:
        raise GoogleGuideSkillsError("Select at least one target agent")
    if not project.is_dir():
        raise GoogleGuideSkillsError(f"Install project does not exist: {project}")
    command_roots = [(manifest.root_for("committed"), "committed")]
    if include_local:
        if global_install or not _inside_local_eval_boundary(manifest, project):
            raise GoogleGuideSkillsError(
                "Local-only skills may be installed only into ignored evaluation workspaces "
                "under evals/results and never globally"
            )
        command_roots.append((manifest.root_for("local-only"), "local-only"))

    available_by_distribution: dict[str, set[str]] = {
        "committed": {"google-guides-index"},
        "local-only": set(),
    }
    for collection, artifact in manifest.artifacts(include_local=True):
        available_by_distribution[collection.distribution].add(artifact.name)

    requested = set(skills) if skills is not None else None
    available = set().union(
        *(available_by_distribution[distribution] for _root, distribution in command_roots)
    )
    if requested is not None:
        unknown = sorted(requested - available)
        if unknown:
            raise GoogleGuideSkillsError(
                "Selected skills are unavailable under the current distribution policy: "
                + ", ".join(unknown)
            )

    commands: list[list[str]] = []
    for source, distribution in command_roots:
        if not source.is_dir():
            raise GoogleGuideSkillsError(f"Generated skill root does not exist: {source}")
        selected = (
            sorted(requested & available_by_distribution[distribution])
            if requested is not None
            else sorted(available_by_distribution[distribution])
        )
        if not selected:
            continue
        command = ["npx", "--yes", SKILLS_CLI_PACKAGE, "add", str(source)]
        for agent in agents:
            command.extend(["--agent", agent])
        for skill in selected:
            command.extend(["--skill", skill])
        command.append("--yes")
        if copy:
            command.append("--copy")
        if global_install:
            command.append("--global")
        commands.append(command)
    return commands


def install(
    manifest: Manifest,
    project: Path,
    agents: list[str],
    skills: list[str] | None = None,
    include_local: bool = False,
    copy: bool = False,
    global_install: bool = False,
    dry_run: bool = False,
) -> list[list[str]]:
    if include_local:
        raise GoogleGuideSkillsError(
            "The public installer does not export local-only skills; use the isolated "
            "evaluation command or inspect .generated/skills in place"
        )
    if global_install:
        raise GoogleGuideSkillsError(
            "Global installation is disabled because isolated npx execution cannot safely "
            "write persistent user-agent directories; install into an explicit project"
        )
    if shutil.which("npx") is None:
        raise GoogleGuideSkillsError("npx is required; install a current Node.js release")
    commands = install_commands(
        manifest,
        project.resolve(),
        agents,
        skills=skills,
        include_local=include_local,
        copy=copy,
        global_install=global_install,
    )
    if dry_run:
        return commands
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
    return commands
