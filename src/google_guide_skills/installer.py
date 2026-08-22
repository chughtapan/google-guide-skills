"""Install generated skills through the open `skills` CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .errors import GoogleGuideSkillsError
from .models import Manifest

DEFAULT_AGENTS = ("codex", "claude-code")
SKILLS_CLI_PACKAGE = "skills@1.5.23"
INSTALL_TIMEOUT_SECONDS = 300


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
