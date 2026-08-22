"""Fresh-process discoverability and answer-quality evaluations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import __version__
from .errors import EvaluationError
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .installer import SKILLS_CLI_PACKAGE, install_commands, minimal_process_env
from .metrics import CODEX_FALLBACK_METADATA_CHARS, metadata_budget
from .models import Manifest
from .strict_yaml import strict_safe_load

SUPPORTED_AGENTS = ("codex", "claude-code")
SUPPORTED_PROFILES = ("single", "all", "all-no-index", "index", "index-ab")
SUPPORTED_STAGES = (
    "controls",
    "smoke",
    "local-smoke",
    "representative",
    "index-experiment",
)
MARKER_RE = re.compile(r"\bEVAL_SKILL:\s*([a-z0-9-]+|none)\b", re.IGNORECASE)
EVAL_KEY_ENV = {
    "codex": ("GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "OPENAI_API_KEY"),
    "claude-code": ("GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
}
EVAL_SANDBOX_PROJECT = Path("/w")
EVAL_SANDBOX_OUTPUT = Path("/o")
EVAL_SANDBOX_STATE = Path("/h")


def _preflight_live(agents: list[str]) -> None:
    """Fail once, before paid work, when live-run prerequisites are unavailable."""

    if shutil.which("npx") is None:
        raise EvaluationError("npx is required for evaluation installs")
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise EvaluationError("bwrap is required for filesystem-isolated live evaluations")
    try:
        probe = subprocess.run(
            [
                bwrap,
                "--die-with-parent",
                "--ro-bind",
                "/",
                "/",
                "--dev",
                "/dev",
                "--proc",
                "/proc",
                "--",
                "/bin/true",
            ],
            env=minimal_process_env(),
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EvaluationError(f"Could not start the bwrap isolation probe: {exc}") from exc
    if probe.returncode:
        raise EvaluationError(
            "bwrap filesystem isolation is unavailable: "
            + (probe.stderr.strip() or f"exit {probe.returncode}")
        )
    for agent in agents:
        binary = "codex" if agent == "codex" else "claude"
        if shutil.which(binary) is None:
            raise EvaluationError(f"Required agent CLI is not installed: {binary}")
        source_key, _provider_key = EVAL_KEY_ENV[agent]
        if not os.environ.get(source_key):
            raise EvaluationError(
                f"{agent} evaluation requires a disposable key in {source_key}"
            )


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _filesystem_sandbox_command(
    agent: str,
    command: list[str],
    project: Path,
    isolation_root: Path,
    *,
    writable_mounts: tuple[tuple[Path, Path], ...] = (),
) -> list[str]:
    """Wrap an agent CLI so only one ephemeral run root is visible from user storage."""

    bwrap = shutil.which("bwrap")
    executable = shutil.which(command[0])
    if bwrap is None or executable is None:
        missing = "bwrap" if bwrap is None else command[0]
        raise EvaluationError(f"Required isolation executable is not installed: {missing}")
    isolation_root = isolation_root.resolve()
    project = project.resolve()
    if not _is_under(project, isolation_root):
        raise EvaluationError("Agent workspace must be inside its isolated run root")
    bindings = ((project, EVAL_SANDBOX_PROJECT), *writable_mounts)
    for source, destination in bindings:
        source = source.resolve()
        if not _is_under(source, isolation_root):
            raise EvaluationError("Agent writable mount must be inside its isolated run root")
        if not destination.is_absolute() or destination == Path("/"):
            raise EvaluationError("Agent-visible mount destinations must be absolute and narrow")

    system_roots = [
        path
        for path in map(Path, ("/usr", "/bin", "/lib", "/lib64", "/nix/store", "/sys"))
        if path.exists()
    ]
    resolved = Path(executable).resolve()
    launch = [str(resolved), *command[1:]]
    mounts: list[Path] = []
    if agent == "codex" and resolved.suffix == ".js":
        node = shutil.which("node")
        if node is None:
            raise EvaluationError("Codex isolation requires the Node.js executable")
        node_path = Path(node).resolve()
        package_root = resolved.parents[1]
        for candidate in (node_path, package_root):
            if not any(_is_under(candidate, root) for root in system_roots):
                mounts.append(candidate)
        launch = [str(node_path), str(resolved), *command[1:]]
    elif not any(_is_under(resolved, root) for root in system_roots):
        mounts.append(resolved)

    args = [
        bwrap,
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--tmpfs",
        "/",
    ]
    directories: set[Path] = {Path("/tmp")}
    for root in system_roots:
        directories.add(root)
    directories.add(Path("/etc"))
    etc_sources = [
        path
        for path in map(
            Path,
            (
                "/etc/ssl",
                "/etc/resolv.conf",
                "/etc/hosts",
                "/etc/nsswitch.conf",
                "/etc/passwd",
                "/etc/group",
                "/etc/ld.so.cache",
                "/etc/localtime",
                "/etc/gai.conf",
            ),
        )
        if path.exists()
    ]
    for _source, destination in bindings:
        directories.add(destination)
        current = destination.parent
        while current != Path("/"):
            directories.add(current)
            current = current.parent
    for source in (*mounts, *etc_sources):
        current = source.parent
        while current != Path("/"):
            directories.add(current)
            current = current.parent
    for directory in sorted(directories, key=lambda path: len(path.parts)):
        args.extend(("--dir", str(directory)))
    for root in system_roots:
        args.extend(("--ro-bind", str(root), str(root)))
    for source in etc_sources:
        args.extend(("--ro-bind", str(source), str(source)))
    args.extend(("--dev", "/dev", "--proc", "/proc"))
    for mount in mounts:
        args.extend(("--ro-bind", str(mount), str(mount)))
    for source, destination in bindings:
        args.extend(("--bind", str(source.resolve()), str(destination)))
    args.extend(("--chdir", str(EVAL_SANDBOX_PROJECT), "--", *launch))
    return args


@dataclass(frozen=True)
class EvalCase:
    """One auditable trigger expectation and optional deterministic answer rubric."""

    id: str
    stage: str
    split: str
    prompt: str
    expected_skills: tuple[str, ...]
    forbidden_skills: tuple[str, ...]
    polarity: str = "positive"
    profile_expectations: tuple[
        tuple[str, tuple[str, ...], tuple[str, ...]], ...
    ] = ()
    rubric: tuple[tuple[str, ...], ...] = ()
    forbidden_claims: tuple[str, ...] = ()

    @property
    def candidate_skills(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.expected_skills, *self.forbidden_skills)))

    def expectations_for(self, profile: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        for selected, expected, forbidden in self.profile_expectations:
            if selected == profile:
                return expected, forbidden
        return self.expected_skills, self.forbidden_skills


def _strings(value: object, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise EvaluationError(f"{context} must be a list of non-empty strings")
    return tuple(value)


def _rubric(value: object, context: str) -> tuple[tuple[str, ...], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise EvaluationError(f"{context} must be a list of regex-alternative lists")
    groups: list[tuple[str, ...]] = []
    for index, group in enumerate(value):
        alternatives = _strings(group, f"{context}[{index}]")
        if not alternatives:
            raise EvaluationError(f"{context}[{index}] cannot be empty")
        try:
            for pattern in alternatives:
                re.compile(pattern)
        except re.error as exc:
            raise EvaluationError(f"{context}[{index}] has an invalid regex: {exc}") from exc
        groups.append(alternatives)
    return tuple(groups)


def _patterns(value: object, context: str) -> tuple[str, ...]:
    patterns = _strings(value, context)
    try:
        for pattern in patterns:
            re.compile(pattern)
    except re.error as exc:
        raise EvaluationError(f"{context} has an invalid regex: {exc}") from exc
    return patterns


def _case(
    raw: object,
    *,
    context: str,
    stage: str,
    expected_default: tuple[str, ...] = (),
    forbidden_default: tuple[str, ...] = (),
    polarity: str = "positive",
) -> EvalCase:
    if not isinstance(raw, dict):
        raise EvaluationError(f"{context} must be a mapping")
    case_id = raw.get("id")
    prompt = raw.get("prompt")
    split = raw.get("split", "validation")
    if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", case_id):
        raise EvaluationError(f"{context}.id must use lowercase letters, digits, and hyphens")
    if not isinstance(prompt, str) or not prompt.strip():
        raise EvaluationError(f"{context}.prompt must be a non-empty string")
    if split not in {"train", "validation"}:
        raise EvaluationError(f"{context}.split must be train or validation")
    profiles_raw = raw.get("profiles", {})
    if not isinstance(profiles_raw, dict):
        raise EvaluationError(f"{context}.profiles must be a mapping")
    profile_expectations: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
    for selected_profile, expectation_raw in profiles_raw.items():
        if selected_profile not in {"single", "all", "all-no-index", "index"}:
            raise EvaluationError(f"{context}.profiles has unknown profile {selected_profile!r}")
        if not isinstance(expectation_raw, dict):
            raise EvaluationError(
                f"{context}.profiles.{selected_profile} must be a mapping"
            )
        expected = _strings(
            expectation_raw.get("expected"),
            f"{context}.profiles.{selected_profile}.expected",
        )
        forbidden = _strings(
            expectation_raw.get("forbidden"),
            f"{context}.profiles.{selected_profile}.forbidden",
        )
        if set(expected) & set(forbidden):
            raise EvaluationError(
                f"{context}.profiles.{selected_profile} expects and forbids the same skill"
            )
        profile_expectations.append((str(selected_profile), expected, forbidden))
    return EvalCase(
        id=case_id,
        stage=stage,
        split=split,
        prompt=prompt.strip(),
        expected_skills=_strings(raw.get("expected"), f"{context}.expected") or expected_default,
        forbidden_skills=_strings(raw.get("forbidden"), f"{context}.forbidden")
        or forbidden_default,
        polarity=polarity,
        profile_expectations=tuple(profile_expectations),
        rubric=_rubric(raw.get("rubric"), f"{context}.rubric"),
        forbidden_claims=_patterns(raw.get("forbidden_claims"), f"{context}.forbidden_claims"),
    )


def load_cases(manifest: Manifest, path: Path | None = None) -> list[EvalCase]:
    """Load smoke cases and expand representative positive/negative suites."""

    cases_path = path or manifest.project_root / "evals" / "cases.yaml"
    try:
        data = strict_safe_load(cases_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationError(f"Cannot read evaluation cases: {exc}") from exc
    except yaml.YAMLError as exc:
        raise EvaluationError(f"Invalid evaluation YAML: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise EvaluationError("Evaluation cases require schema_version: 1")

    values: list[EvalCase] = []
    smoke = data.get("smoke")
    if not isinstance(smoke, list) or not smoke:
        raise EvaluationError("Evaluation cases require a non-empty smoke list")
    values.extend(
        _case(raw, context=f"smoke[{index}]", stage="smoke") for index, raw in enumerate(smoke)
    )

    controls = data.get("explicit_controls")
    if controls is not None:
        if not isinstance(controls, dict):
            raise EvaluationError("explicit_controls must be a mapping")
        template = controls.get("prompt_template")
        if not isinstance(template, str) or "{invocation}" not in template:
            raise EvaluationError(
                "explicit_controls.prompt_template must contain the {invocation} placeholder"
            )
        if not template.startswith("{invocation}"):
            raise EvaluationError(
                "explicit_controls.prompt_template must begin with {invocation}"
            )
        for smoke_case in tuple(values):
            if smoke_case.stage != "smoke" or len(smoke_case.expected_skills) != 1:
                continue
            skill = smoke_case.expected_skills[0]
            values.append(
                EvalCase(
                    id=f"control-{skill}",
                    stage="controls",
                    split="validation",
                    prompt=template,
                    expected_skills=(skill,),
                    forbidden_skills=(),
                    polarity="control",
                )
            )

    local_smoke = data.get("local_smoke", [])
    if not isinstance(local_smoke, list):
        raise EvaluationError("local_smoke must be a list")
    values.extend(
        _case(raw, context=f"local_smoke[{index}]", stage="local-smoke")
        for index, raw in enumerate(local_smoke)
    )

    suites = data.get("representative", [])
    if not isinstance(suites, list):
        raise EvaluationError("representative must be a list")
    for suite_index, suite in enumerate(suites):
        context = f"representative[{suite_index}]"
        if not isinstance(suite, dict):
            raise EvaluationError(f"{context} must be a mapping")
        skill = suite.get("skill")
        if not isinstance(skill, str) or not skill:
            raise EvaluationError(f"{context}.skill must be a non-empty string")
        for polarity, expected, forbidden in (
            ("positive", (skill,), ()),
            ("negative", (), (skill,)),
        ):
            raw_cases = suite.get(polarity)
            if not isinstance(raw_cases, list) or not raw_cases:
                raise EvaluationError(f"{context}.{polarity} must be a non-empty list")
            values.extend(
                _case(
                    raw,
                    context=f"{context}.{polarity}[{index}]",
                    stage="representative",
                    expected_default=expected,
                    forbidden_default=forbidden,
                    polarity=polarity,
                )
                for index, raw in enumerate(raw_cases)
            )

    index_experiment = data.get("index_experiment")
    if index_experiment is not None:
        if not isinstance(index_experiment, dict):
            raise EvaluationError("index_experiment must be a mapping")
        cases_raw = index_experiment.get("cases")
        if not isinstance(cases_raw, list) or not cases_raw:
            raise EvaluationError("index_experiment.cases must be a non-empty list")
        values.extend(
            _case(
                raw,
                context=f"index_experiment.cases[{index}]",
                stage="index-experiment",
            )
            for index, raw in enumerate(cases_raw)
        )
        if index_experiment.get("forbid_index_on_direct_smoke") is True:
            adjusted: list[EvalCase] = []
            for case in values:
                if (
                    case.stage == "smoke"
                    and case.expected_skills != ("google-guides-index",)
                ):
                    overrides = tuple(
                        item for item in case.profile_expectations if item[0] != "all"
                    ) + (
                        (
                            "all",
                            case.expected_skills,
                            tuple(
                                dict.fromkeys(
                                    (*case.forbidden_skills, "google-guides-index")
                                )
                            ),
                        ),
                    )
                    case = replace(case, profile_expectations=overrides)
                adjusted.append(case)
            values = adjusted

    known = {
        artifact.name
        for collection in manifest.collections.values()
        for artifact in collection.artifacts
    } | {"google-guides-index"}
    seen: set[str] = set()
    for case in values:
        if case.id in seen:
            raise EvaluationError(f"Duplicate evaluation case id: {case.id}")
        seen.add(case.id)
        unknown = sorted(set((*case.expected_skills, *case.forbidden_skills)) - known)
        if unknown:
            raise EvaluationError(f"{case.id} references unknown skills: {', '.join(unknown)}")
        if set(case.expected_skills) & set(case.forbidden_skills):
            raise EvaluationError(f"{case.id} both expects and forbids the same skill")
        for selected_profile, expected, forbidden in case.profile_expectations:
            unknown = sorted(set((*expected, *forbidden)) - known)
            if unknown:
                raise EvaluationError(
                    f"{case.id} profile {selected_profile} references unknown skills: "
                    + ", ".join(unknown)
                )
    return values


def select_cases(
    cases: list[EvalCase],
    *,
    stages: list[str] | None = None,
    splits: list[str] | None = None,
    case_ids: list[str] | None = None,
    require_rubric: bool = False,
    limit: int | None = None,
) -> list[EvalCase]:
    selected = cases
    if stages:
        selected = [case for case in selected if case.stage in set(stages)]
    if splits:
        selected = [case for case in selected if case.split in set(splits)]
    if case_ids:
        requested = set(case_ids)
        available = {case.id for case in selected}
        missing = sorted(requested - available)
        if missing:
            raise EvaluationError(f"Unknown or filtered evaluation cases: {', '.join(missing)}")
        selected = [case for case in selected if case.id in requested]
    if require_rubric:
        selected = [case for case in selected if case.rubric]
    if limit is not None:
        if limit < 1:
            raise EvaluationError("Evaluation limit must be positive")
        selected = selected[:limit]
    if not selected:
        raise EvaluationError("No evaluation cases matched the requested filters")
    return selected


def _walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_trace(
    trace: str, final_output: str, known_skills: set[str]
) -> tuple[set[str], str | None, set[str]]:
    """Find observable skill loads separately from the agent's self-reported marker."""

    escaped = "|".join(re.escape(name) for name in sorted(known_skills, key=len, reverse=True))
    path_re = re.compile(rf"(?:\.agents|\.claude)[/\\]skills[/\\]({escaped})[/\\]SKILL\.md")
    loaded: set[str] = set()
    visible: set[str] = set()
    pending_tool_loads: dict[str, set[str]] = {}

    for line in trace.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            inventory = event.get("skills", [])
            if isinstance(inventory, list):
                for item in inventory:
                    candidate = item.get("name") if isinstance(item, dict) else item
                    if candidate in known_skills:
                        visible.add(str(candidate))
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "command_execution"
        ):
            command = item.get("command")
            if isinstance(command, str):
                command_skills = set(path_re.findall(command))
                if item.get("exit_code") == 0:
                    loaded.update(command_skills)
                else:
                    output = str(item.get("aggregated_output", ""))
                    loaded.update(
                        skill
                        for skill in command_skills
                        if re.search(rf"(?m)^name:\s*{re.escape(skill)}\s*$", output)
                    )
        event_items = [item for item in _walk(event) if isinstance(item, dict)]
        for item in event_items:
            if item.get("type") != "tool_use" or not isinstance(item.get("id"), str):
                continue
            tool_name = str(item.get("name", "")).lower()
            candidates: set[str] = set()
            if tool_name != "skill":
                if tool_name == "read":
                    tool_input = item.get("input")
                    if isinstance(tool_input, dict):
                        file_path = tool_input.get("file_path")
                        if isinstance(file_path, str):
                            candidates.update(path_re.findall(file_path))
                if candidates:
                    pending_tool_loads[str(item["id"])] = candidates
                continue
            tool_input = item.get("input")
            if isinstance(tool_input, dict):
                candidate = tool_input.get("skill") or tool_input.get("name")
                if candidate in known_skills:
                    candidates.add(str(candidate))
            if candidates:
                pending_tool_loads[str(item["id"])] = candidates
        for item in event_items:
            tool_use_id = item.get("tool_use_id")
            if item.get("type") != "tool_result" or not isinstance(tool_use_id, str):
                continue
            candidates = pending_tool_loads.pop(tool_use_id, set())
            if item.get("is_error") is not True:
                loaded.update(candidates)

    marker = MARKER_RE.findall(final_output)
    claimed = marker[-1].lower() if marker else None
    if claimed == "none":
        claimed = None
    return loaded, claimed, visible


def score_output(output: str, rubric: tuple[tuple[str, ...], ...]) -> tuple[int, int]:
    """Score one point per criterion when any accepted regex alternative matches."""

    earned = sum(
        any(re.search(pattern, output, flags=re.IGNORECASE | re.DOTALL) for pattern in group)
        for group in rubric
    )
    return earned, len(rubric)


def forbidden_claims(output: str, patterns: tuple[str, ...]) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, output, flags=re.IGNORECASE | re.DOTALL)
    ]


def trace_metadata(trace: str) -> dict[str, object]:
    """Normalize usage, cost, terminal state, and metadata-budget warnings."""

    metadata: dict[str, object] = {
        "usage": None,
        "cost_usd": None,
        "terminal_status": None,
        "resolved_model": None,
        "skill_budget_warning": "skill descriptions were shortened" in trace.lower(),
    }
    for line in trace.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = event.get("type")
        if event_type == "system" and event.get("subtype") == "init":
            metadata["resolved_model"] = event.get("model")
        message = event.get("message")
        if isinstance(message, dict) and message.get("model"):
            metadata["resolved_model"] = message["model"]
        if event_type == "result":
            metadata["usage"] = event.get("usage")
            metadata["cost_usd"] = event.get("total_cost_usd")
            metadata["terminal_status"] = event.get("subtype") or (
                "error" if event.get("is_error") else "success"
            )
            if event.get("is_error") and (event.get("error") or event.get("result")):
                metadata["terminal_error"] = _bounded_excerpt(
                    str(event.get("error") or event.get("result"))
                )
        elif event_type == "turn.completed":
            metadata["usage"] = event.get("usage")
            metadata["terminal_status"] = "completed"
        elif event_type == "turn.failed":
            metadata["terminal_status"] = "failed"
            if event.get("error") or event.get("message"):
                metadata["terminal_error"] = _bounded_excerpt(
                    str(event.get("error") or event.get("message"))
                )
    return metadata


def _bounded_excerpt(value: str, limit: int = 4000) -> str:
    """Keep a diagnostic tail without allowing one provider error to dominate a report."""

    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    return "[truncated] " + normalized[-limit:]


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _project_git_state(project_root: Path) -> dict[str, object]:
    """Record the release checkout without consulting ambient Git configuration."""

    revision = subprocess.run(
        git_command("rev-parse", "HEAD"),
        cwd=project_root,
        env=git_environment(),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    status = subprocess.run(
        git_command("status", "--porcelain", "--untracked-files=all"),
        cwd=project_root,
        env=git_environment(),
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return {
        "commit": revision.stdout.strip() if revision.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def build_agent_command(
    agent: str,
    project: Path,
    prompt: str,
    output_path: Path,
    *,
    max_budget_usd: float,
    model: str | None = None,
) -> list[str]:
    if agent == "codex":
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--json",
            "--sandbox",
            "read-only",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--output-last-message",
            str(output_path),
            "-c",
            "shell_environment_policy.inherit=none",
            "-C",
            str(project),
        ]
    elif agent == "claude-code":
        command = [
            "claude",
            "--print",
            "--output-format",
            "stream-json",
            "--verbose",
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--effort",
            "low",
            "--setting-sources",
            "project",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--no-chrome",
            "--tools",
            "Skill,Read,Glob,Grep",
            "--max-budget-usd",
            str(max_budget_usd),
        ]
    else:
        raise EvaluationError(f"Unsupported evaluation agent: {agent}")
    if model:
        command.extend(["--model", model])
    command.append(prompt)
    return command


def _isolated_agent_env(
    agent: str, temporary: Path, *, visible_root: Path | None = None
) -> dict[str, str]:
    passthrough = {
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
    env = {key: value for key, value in os.environ.items() if key in passthrough}
    home = temporary / "home"
    home.mkdir(mode=0o700)
    visible = visible_root or temporary
    visible_home = visible / "home"
    env["HOME"] = str(visible_home)
    env["XDG_CONFIG_HOME"] = str(visible_home / ".config")
    env["XDG_CACHE_HOME"] = str(visible_home / ".cache")
    env["XDG_DATA_HOME"] = str(visible_home / ".local" / "share")
    source_key, provider_key = EVAL_KEY_ENV[agent]
    value = os.environ.get(source_key)
    if not value:
        raise EvaluationError(
            f"{agent} evaluation requires a disposable key in {source_key}"
        )
    env[provider_key] = value
    if agent == "codex":
        codex_home = temporary / "codex"
        codex_home.mkdir(mode=0o700)
        env["CODEX_HOME"] = str(visible / "codex")
    else:
        claude_config = temporary / "claude"
        claude_config.mkdir(mode=0o700)
        env["CLAUDE_CONFIG_DIR"] = str(visible / "claude")
    return env


def _final_from_claude_trace(trace: str) -> str:
    result = ""
    for line in trace.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            result = event["result"]
    return result


def _run_agent(
    agent: str,
    project: Path,
    prompt: str,
    raw_dir: Path,
    *,
    timeout: int,
    max_budget_usd: float,
    model: str | None,
    isolation_root: Path | None = None,
) -> dict[str, object]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_path = raw_dir / "final.txt"
    binary = "codex" if agent == "codex" else "claude"
    if shutil.which(binary) is None:
        raise EvaluationError(f"Required agent CLI is not installed: {binary}")
    sandbox_root = (isolation_root or project.parent).resolve()
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix=".agent-home-", dir=sandbox_root
    ) as temp:
        state_root = Path(temp)
        env = _isolated_agent_env(
            agent, state_root, visible_root=EVAL_SANDBOX_STATE
        )
        command = build_agent_command(
            agent,
            EVAL_SANDBOX_PROJECT,
            prompt,
            EVAL_SANDBOX_OUTPUT / "final.txt",
            max_budget_usd=max_budget_usd,
            model=model,
        )
        command = _filesystem_sandbox_command(
            agent,
            command,
            project,
            sandbox_root,
            writable_mounts=(
                (raw_dir, EVAL_SANDBOX_OUTPUT),
                (state_root, EVAL_SANDBOX_STATE),
            ),
        )
        try:
            completed = subprocess.run(
                command,
                cwd=project,
                env=env,
                stdin=subprocess.DEVNULL,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            trace = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(trace, bytes):
                trace = trace.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            completed = None
    duration = time.monotonic() - started
    if completed is None:
        exit_code = 124
    else:
        trace = completed.stdout
        stderr = completed.stderr
        exit_code = completed.returncode
    provider_secret = env.get(EVAL_KEY_ENV[agent][1], "")
    if provider_secret:
        trace = trace.replace(provider_secret, "[REDACTED_EVAL_KEY]")
        stderr = stderr.replace(provider_secret, "[REDACTED_EVAL_KEY]")
    (raw_dir / "trace.jsonl").write_text(trace, encoding="utf-8")
    (raw_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    if output_path.is_file():
        final_output = output_path.read_text(encoding="utf-8")
    elif agent == "claude-code":
        final_output = _final_from_claude_trace(trace)
        output_path.write_text(final_output, encoding="utf-8")
    else:
        final_output = ""
        output_path.write_text("", encoding="utf-8")
    if provider_secret and provider_secret in final_output:
        final_output = final_output.replace(provider_secret, "[REDACTED_EVAL_KEY]")
        output_path.write_text(final_output, encoding="utf-8")
    return {
        "command": command,
        "duration_seconds": round(duration, 3),
        "exit_code": exit_code,
        "stderr_excerpt": _bounded_excerpt(stderr),
        "final_output": final_output,
        "trace": trace,
    }


def _evaluation_prompt(case: EvalCase, agent: str) -> str:
    case_prompt = case.prompt
    if case.stage == "controls" and len(case.expected_skills) == 1:
        prefix = "$" if agent == "codex" else "/"
        case_prompt = case_prompt.format(invocation=f"{prefix}{case.expected_skills[0]}")
    prompt = f"{case_prompt}\n\nDo not edit files. Give a concise answer."
    if agent == "codex":
        # Codex 0.147 does not expose a stable Skill tool event in JSONL. Keep the task itself
        # implicit, but request a separate self-report so the proxy cannot be mistaken for an
        # authoritative trace event.
        prompt += (
            " For run instrumentation only, end with exactly "
            "`EVAL_SKILL: <skill-name-or-none>` to report any repository skill actually used."
        )
    return prompt


def _version(command: list[str], *, home: Path | None = None) -> str | None:
    try:
        completed = subprocess.run(
            command,
            env=minimal_process_env(home),
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (completed.stdout or completed.stderr).strip().splitlines()
    return value[0] if value else None


def _prepare_workspace(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)
    completed = subprocess.run(
        git_command(
            "init",
            "--quiet",
            "--initial-branch=main",
            "--template=",
        ),
        cwd=path,
        env=git_environment(),
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    if completed.returncode:
        raise EvaluationError(f"Could not initialize evaluation workspace: {completed.stderr}")


def _install_profile(
    manifest: Manifest,
    project: Path,
    agent: str,
    profile: str,
    case: EvalCase,
    *,
    include_local: bool,
    timeout: int,
    npx_home: Path | None = None,
) -> dict[str, object]:
    if profile == "baseline":
        return {
            "commands": [],
            "installed_skills": [],
            "hashes_verified": True,
            "installed_skill_sha256": {},
            "installed_pack_sha256": _canonical_digest({}),
        }
    if shutil.which("npx") is None:
        raise EvaluationError("npx is required for evaluation installs")
    selected: list[str] | None
    if profile == "single":
        selected = list(case.candidate_skills)
        if not selected:
            raise EvaluationError(f"{case.id} has no candidate skill for the single profile")
    elif profile == "index":
        selected = ["google-guides-index"]
    elif profile == "all-no-index":
        selected = [
            artifact.name
            for collection in manifest.collections.values()
            if include_local or collection.distribution == "committed"
            for artifact in collection.artifacts
        ]
    elif profile == "all":
        selected = None
    else:
        raise EvaluationError(f"Unsupported evaluation profile: {profile}")
    commands = install_commands(
        manifest,
        project,
        [agent],
        skills=selected,
        include_local=include_local,
        copy=True,
    )

    def checked_tree_hashes(path: Path, context: str) -> dict[str, str]:
        if path.is_symlink() or not path.is_dir():
            raise EvaluationError(f"{context} must be a real directory, not a symlink")
        candidates = sorted(path.rglob("*"))
        for candidate in candidates:
            if candidate.is_symlink():
                raise EvaluationError(f"{context} contains a symlink: {candidate}")
            if not candidate.is_dir() and not candidate.is_file():
                raise EvaluationError(f"{context} contains a non-regular path: {candidate}")
        return {
            candidate.relative_to(path).as_posix(): hashlib.sha256(
                candidate.read_bytes()
            ).hexdigest()
            for candidate in candidates
            if candidate.is_file()
        }

    git_dir = project / ".git"
    git_before = (
        checked_tree_hashes(git_dir, "Evaluation Git metadata")
        if git_dir.exists()
        else None
    )

    def run_installs(home: Path) -> None:
        home.mkdir(mode=0o700, parents=True, exist_ok=True)
        npx_env = minimal_process_env(home)
        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    cwd=project,
                    env=npx_env,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    capture_output=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise EvaluationError(
                    f"Skill installation timed out: {' '.join(command)}"
                ) from exc
            if completed.returncode:
                raise EvaluationError(
                    f"Skill installation failed: {' '.join(command)}\n"
                    f"{completed.stdout}\n{completed.stderr}".rstrip()
                )

    if npx_home is None:
        with tempfile.TemporaryDirectory(prefix="google-guides-npx-home-") as temporary:
            run_installs(Path(temporary))
    else:
        run_installs(npx_home)

    if git_before is not None and checked_tree_hashes(
        git_dir, "Evaluation Git metadata"
    ) != git_before:
        raise EvaluationError("Skill installer modified evaluation Git metadata")

    namespace_name = ".agents" if agent == "codex" else ".claude"
    allowed_top_level = {".git", namespace_name, "skills-lock.json"}
    unexpected_top_level = sorted(
        candidate.name
        for candidate in project.iterdir()
        if candidate.name not in allowed_top_level
    )
    if unexpected_top_level:
        raise EvaluationError(
            "Skill installer added unexpected project files: "
            + ", ".join(unexpected_top_level)
        )
    namespace = project / namespace_name
    if namespace.is_symlink():
        raise EvaluationError("Skill installer created a symlinked agent namespace")
    if namespace.is_dir():
        namespace_extras = sorted(
            candidate.name for candidate in namespace.iterdir() if candidate.name != "skills"
        )
        if namespace_extras:
            raise EvaluationError(
                "Skill installer added unexpected agent configuration: "
                + ", ".join(namespace_extras)
            )
    lock_path = project / "skills-lock.json"
    if lock_path.exists() and (lock_path.is_symlink() or not lock_path.is_file()):
        raise EvaluationError("Skill installer created an unsafe skills-lock.json")

    committed = {
        artifact.name
        for collection in manifest.collections.values()
        if collection.distribution == "committed"
        for artifact in collection.artifacts
    } | {"google-guides-index"}
    local = {
        artifact.name
        for collection in manifest.collections.values()
        if collection.distribution == "local-only"
        for artifact in collection.artifacts
    }
    if selected is None:
        expected = committed | (local if include_local else set())
    else:
        expected = set(selected)
    install_root = project / (".agents/skills" if agent == "codex" else ".claude/skills")
    if install_root.is_symlink():
        raise EvaluationError("Skill installer created a symlinked skills root")
    install_entries = list(install_root.iterdir()) if install_root.is_dir() else []
    unsafe_entries = sorted(
        path.name for path in install_entries if path.is_symlink() or not path.is_dir()
    )
    if unsafe_entries:
        raise EvaluationError(
            "Skill installer created unsafe skill entries: " + ", ".join(unsafe_entries)
        )
    actual = {
        path.name for path in install_entries if (path / "SKILL.md").is_file()
    }
    missing = sorted(name for name in expected if not (install_root / name / "SKILL.md").is_file())
    if missing:
        raise EvaluationError(f"Installer omitted expected skills: {', '.join(missing)}")
    extras = sorted(actual - expected)
    if extras:
        raise EvaluationError(f"Installer added undeclared skills: {', '.join(extras)}")

    installed_skill_sha256: dict[str, str] = {}
    for name in sorted(expected):
        source_root = (
            manifest.root_for("committed") if name in committed else manifest.root_for("local-only")
        )
        source_hashes = checked_tree_hashes(source_root / name, f"Generated skill {name}")
        installed_hashes = checked_tree_hashes(
            install_root / name, f"Installed skill {name}"
        )
        if source_hashes != installed_hashes:
            raise EvaluationError(f"Installed copy does not match generated skill: {name}")
        installed_skill_sha256[name] = _canonical_digest(installed_hashes)
    visible_install_root = EVAL_SANDBOX_PROJECT / (
        ".agents/skills" if agent == "codex" else ".claude/skills"
    )
    installed_budget = metadata_budget(
        [install_root / name for name in sorted(expected)],
        install_root=visible_install_root.as_posix(),
    )
    if (
        agent == "codex"
        and int(installed_budget["codex_list_chars"]) > CODEX_FALLBACK_METADATA_CHARS
    ):
        raise EvaluationError(
            "Installed Codex skill metadata exceeds the fallback budget at the "
            f"agent-visible root {visible_install_root}: "
            f"{installed_budget['codex_list_chars']} > {CODEX_FALLBACK_METADATA_CHARS}"
        )
    return {
        "commands": commands,
        "installed_skills": sorted(expected),
        "hashes_verified": True,
        "installed_skill_sha256": installed_skill_sha256,
        "installed_pack_sha256": _canonical_digest(installed_skill_sha256),
        "agent_visible_install_root": visible_install_root.as_posix(),
        "installed_metadata_budget": installed_budget,
    }


def _summary(records: list[dict[str, object]]) -> dict[str, object]:
    completed = [record for record in records if record.get("status") == "completed"]
    correct = sum(record.get("trigger_correct") is True for record in completed)
    rubric_earned = sum(int(record.get("rubric_earned", 0)) for record in completed)
    rubric_total = sum(int(record.get("rubric_total", 0)) for record in completed)
    claim_violations = sum(len(record.get("forbidden_claims_found", [])) for record in completed)
    positives = [
        record
        for record in completed
        if record.get("polarity") == "positive" and record.get("expected_skills")
    ]
    negatives = [record for record in completed if record.get("polarity") == "negative"]
    controls = [record for record in completed if record.get("stage") == "controls"]
    direct = [
        record
        for record in completed
        if record.get("stage") == "smoke"
        and record.get("profile") == "all"
        and record.get("expected_skills") != ["google-guides-index"]
    ]
    broad = [
        record
        for record in completed
        if record.get("stage") == "index-experiment" and record.get("profile") == "all"
    ]

    def ratio(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    positive_correct = sum(
        record.get("expected_loaded", record.get("trigger_correct")) is True
        for record in positives
    )
    negative_correct = sum(
        record.get("forbidden_avoided", record.get("trigger_correct")) is True
        for record in negatives
    )
    control_correct = sum(record.get("trigger_correct") is True for record in controls)
    direct_exact = sum(record.get("trigger_correct") is True for record in direct)
    direct_steals = sum(
        "google-guides-index" in record.get("observed_skills", []) for record in direct
    )
    direct_with_unexpected = sum(
        bool(record.get("unexpected_loaded_skills", [])) for record in direct
    )
    direct_unexpected_loads = sum(
        len(record.get("unexpected_loaded_skills", [])) for record in direct
    )
    broad_loaded = sum(
        "google-guides-index" in record.get("observed_skills", []) for record in broad
    )
    return {
        "runs": len(records),
        "completed": len(completed),
        "failed_processes": sum(record.get("status") == "failed" for record in records),
        "infrastructure_errors": sum(
            record.get("status") == "infrastructure-error" for record in records
        ),
        "successful_processes": sum(record.get("exit_code") == 0 for record in completed),
        "trigger_correct": correct,
        "trigger_accuracy": round(correct / len(completed), 4) if completed else None,
        "rubric_earned": rubric_earned,
        "rubric_total": rubric_total,
        "rubric_score": round(rubric_earned / rubric_total, 4) if rubric_total else None,
        "forbidden_claim_violations": claim_violations,
        "positive_runs": len(positives),
        "positive_correct": positive_correct,
        "positive_recall": ratio(positive_correct, len(positives)),
        "negative_runs": len(negatives),
        "negative_correct": negative_correct,
        "near_miss_specificity": ratio(negative_correct, len(negatives)),
        "explicit_control_runs": len(controls),
        "explicit_control_correct": control_correct,
        "explicit_control_accuracy": ratio(control_correct, len(controls)),
        "direct_prompt_runs": len(direct),
        "direct_prompt_exact": direct_exact,
        "direct_prompt_exact_rate": ratio(direct_exact, len(direct)),
        "direct_index_steals": direct_steals,
        "direct_index_steal_rate": ratio(direct_steals, len(direct)),
        "direct_prompts_with_unexpected": direct_with_unexpected,
        "direct_unexpected_skill_loads": direct_unexpected_loads,
        "index_broad_runs": len(broad),
        "index_broad_loaded": broad_loaded,
        "index_broad_recall": ratio(broad_loaded, len(broad)),
    }


def _index_comparisons(records: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, object, object], dict[str, dict[str, object]]] = {}
    for record in records:
        if record.get("status") != "completed" or record.get("stage") != "index-experiment":
            continue
        key = (record.get("agent"), record.get("case_id"), record.get("repeat"))
        grouped.setdefault(key, {})[str(record.get("profile"))] = record
    comparisons: list[dict[str, object]] = []
    for (agent, case_id, repeat), pair in sorted(grouped.items()):
        without_index = pair.get("all-no-index")
        with_index = pair.get("all")
        if not without_index or not with_index:
            continue
        comparisons.append(
            {
                "agent": agent,
                "case_id": case_id,
                "repeat": repeat,
                "index_loaded": "google-guides-index"
                in with_index.get("observed_skills", []),
                "without_index_rubric": int(without_index.get("rubric_earned", 0)),
                "with_index_rubric": int(with_index.get("rubric_earned", 0)),
                "rubric_total": int(with_index.get("rubric_total", 0)),
                "rubric_delta": int(with_index.get("rubric_earned", 0))
                - int(without_index.get("rubric_earned", 0)),
            }
        )
    return comparisons


def _quality_comparisons(records: list[dict[str, object]], profile: str) -> list[dict[str, object]]:
    grouped: dict[tuple[object, object, object], dict[str, dict[str, object]]] = {}
    for record in records:
        if record.get("status") != "completed":
            continue
        key = (record.get("agent"), record.get("case_id"), record.get("repeat"))
        grouped.setdefault(key, {})[str(record.get("profile"))] = record
    comparisons: list[dict[str, object]] = []
    for (agent, case_id, repeat), pair in sorted(grouped.items()):
        baseline = pair.get("baseline")
        skilled = pair.get(profile)
        if not baseline or not skilled:
            continue
        baseline_score = int(baseline.get("rubric_earned", 0))
        skilled_score = int(skilled.get("rubric_earned", 0))
        baseline_violations = len(baseline.get("forbidden_claims_found", []))
        skilled_violations = len(skilled.get("forbidden_claims_found", []))
        comparisons.append(
            {
                "agent": agent,
                "case_id": case_id,
                "repeat": repeat,
                "baseline_score": baseline_score,
                "skilled_score": skilled_score,
                "rubric_total": int(skilled.get("rubric_total", 0)),
                "delta": skilled_score - baseline_score,
                "baseline_forbidden_claims": baseline_violations,
                "skilled_forbidden_claims": skilled_violations,
                "fidelity_delta": (skilled_score - skilled_violations)
                - (baseline_score - baseline_violations),
            }
        )
    return comparisons


def _markdown_report(report: dict[str, object]) -> str:
    summary = report["summary"]
    identity = report.get("corpus_identity", {})
    project_git = identity.get("project_git", {}) if isinstance(identity, dict) else {}
    lines = [
        "# Agent Skills Evaluation Run",
        "",
        f"- Mode: `{report['mode']}`",
        f"- Created: `{report['created_at']}`",
        f"- Runs: {summary['runs']}",
        f"- Completed: {summary['completed']}",
        f"- Trigger accuracy: {summary['trigger_accuracy']}",
        f"- Rubric score: {summary['rubric_score']}",
        f"- Positive recall: {summary.get('positive_recall')}",
        f"- Near-miss specificity: {summary.get('near_miss_specificity')}",
        f"- Explicit-control accuracy: {summary.get('explicit_control_accuracy')}",
        f"- Direct-prompt exact rate: {summary.get('direct_prompt_exact_rate')}",
        f"- Direct index-steal rate: {summary.get('direct_index_steal_rate')}",
        f"- Broad index recall: {summary.get('index_broad_recall')}",
        f"- Manifest SHA-256: `{identity.get('manifest_sha256', 'unknown')}`",
        f"- Project commit: `{project_git.get('commit', 'unknown')}`",
        f"- Project dirty: `{project_git.get('dirty', 'unknown')}`",
        "",
        "| Agent | Profile | Case | Run | Loaded | Claimed | Trigger | Rubric | Exit |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | ---: |",
    ]
    for record in report["records"]:
        loaded = ", ".join(record.get("loaded_skills", [])) or "none"
        claimed = record.get("claimed_skill") or "none"
        trigger = record.get("trigger_correct")
        rubric = f"{record.get('rubric_earned', 0)}/{record.get('rubric_total', 0)}"
        lines.append(
            f"| {record['agent']} | {record['profile']} | {record['case_id']} | "
            f"{record['repeat']} | {loaded} | {claimed} | {trigger} | {rubric} | "
            f"{record.get('exit_code', '-')} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def run_evaluation(
    manifest: Manifest,
    cases: list[EvalCase],
    *,
    mode: str,
    agents: list[str],
    profile: str,
    repeat: int = 1,
    include_local: bool = False,
    timeout: int = 180,
    max_budget_usd: float = 0.25,
    models: dict[str, str] | None = None,
    dry_run: bool = False,
    keep_raw: bool = False,
    results_root: Path | None = None,
    accept_credential_risk: bool = False,
) -> tuple[dict[str, object], Path]:
    """Run each case in a new project and each agent in a fresh process/home."""

    if mode not in {"triggers", "quality"}:
        raise EvaluationError("Evaluation mode must be triggers or quality")
    if not agents or set(agents) - set(SUPPORTED_AGENTS):
        raise EvaluationError(f"Agents must be selected from {SUPPORTED_AGENTS}")
    if profile not in SUPPORTED_PROFILES:
        raise EvaluationError(f"Profile must be selected from {SUPPORTED_PROFILES}")
    if repeat < 1:
        raise EvaluationError("Repeat must be positive")
    if timeout < 1:
        raise EvaluationError("Timeout must be positive")
    if not math.isfinite(max_budget_usd) or max_budget_usd <= 0:
        raise EvaluationError("Claude budget must be finite and positive")
    if not dry_run:
        if not accept_credential_risk:
            raise EvaluationError(
                "Live evaluations require explicit acceptance of disposable credential risk"
            )
        missing_models = sorted(set(agents) - set(models or {}))
        if missing_models:
            raise EvaluationError(
                "Live evaluations require an explicit model for every agent: "
                + ", ".join(missing_models)
            )
    if include_local and not dry_run:
        raise EvaluationError(
            "Live hosted-agent evaluation of local-only derived material is disabled; "
            "use plan mode and offline boundary tests"
        )
    if not dry_run:
        _preflight_live(agents)

    local_skills = {
        artifact.name
        for collection in manifest.collections.values()
        if collection.distribution == "local-only"
        for artifact in collection.artifacts
    }
    requested_local = sorted(
        local_skills.intersection(
            skill for case in cases for skill in case.candidate_skills
        )
    )
    if requested_local and not include_local:
        raise EvaluationError(
            "Local-only evaluation cases require --include-local: "
            + ", ".join(requested_local)
        )

    serialized_cases = [asdict(case) for case in cases]
    corpus_identity = {
        "generator_version": __version__,
        "manifest_sha256": hashlib.sha256(manifest.path.read_bytes()).hexdigest(),
        "case_set_sha256": _canonical_digest(serialized_cases),
        "project_git": _project_git_state(manifest.project_root),
    }

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    results_base = results_root or manifest.project_root / "evals" / "results"
    if not results_base.is_absolute():
        results_base = manifest.project_root / results_base
    if include_local:
        safe_results = (manifest.project_root / "evals" / "results").resolve()
        resolved_results = results_base.resolve()
        try:
            resolved_results.relative_to(safe_results)
        except ValueError as exc:
            raise EvaluationError(
                "Local-only evaluations must remain under the ignored evals/results directory"
            ) from exc
        ignored_probe = safe_results / ".google-guides-local-boundary"
        ignored = subprocess.run(
            git_command("check-ignore", "--quiet", "--", str(ignored_probe)),
            cwd=manifest.project_root,
            env=git_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
        if ignored.returncode:
            raise EvaluationError(
                "Local-only evaluation output is not covered by the repository ignore policy"
            )
    root = results_base.resolve() / timestamp
    suffix = 1
    while root.exists():
        root = root.with_name(f"{timestamp}-{suffix}")
        suffix += 1
    root.mkdir(parents=True, mode=0o700)
    npx_home = None if dry_run else root / ".npx-home"
    records_path = root / "records.jsonl"
    records_path.touch(mode=0o600)

    known_skills = {
        artifact.name
        for collection in manifest.collections.values()
        for artifact in collection.artifacts
    } | {"google-guides-index"}
    if profile == "index-ab":
        profiles = ("all-no-index", "all")
    else:
        profiles = ("baseline", profile) if mode == "quality" else (profile,)
    records: list[dict[str, object]] = []

    def checkpoint(record: dict[str, object]) -> None:
        records.append(record)
        with records_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")

    for case in cases:
        for agent in agents:
            for run_number in range(1, repeat + 1):
                for current_profile in profiles:
                    record_id = f"{agent}-{current_profile}-{case.id}-{run_number}"
                    if current_profile == "baseline":
                        evaluated_expected: tuple[str, ...] = ()
                        evaluated_forbidden = case.candidate_skills
                    else:
                        evaluated_expected, evaluated_forbidden = case.expectations_for(
                            current_profile
                        )
                    if (
                        current_profile == "all"
                        and case.stage == "smoke"
                        and evaluated_expected != ("google-guides-index",)
                    ):
                        # Direct smoke prompts are exact-routing probes. Loading a broad router or
                        # an unrelated guide alongside the intended skill is a specificity miss.
                        evaluated_forbidden = tuple(
                            sorted(known_skills - set(evaluated_expected))
                        )
                    record: dict[str, object] = {
                        "id": record_id,
                        "agent": agent,
                        "profile": current_profile,
                        "case_id": case.id,
                        "stage": case.stage,
                        "split": case.split,
                        "polarity": case.polarity,
                        "repeat": run_number,
                        "case_expected_skills": list(case.expected_skills),
                        "case_forbidden_skills": list(case.forbidden_skills),
                        "expected_skills": list(evaluated_expected),
                        "forbidden_skills": list(evaluated_forbidden),
                        "requested_model": (models or {}).get(agent),
                        **corpus_identity,
                    }
                    if dry_run:
                        record.update({"status": "planned", "trigger_correct": None})
                        checkpoint(record)
                        continue
                    run_home = tempfile.TemporaryDirectory(
                        prefix=f"google-guides-eval-{record_id}-"
                    )
                    isolation_root = Path(run_home.name)
                    workspace = isolation_root / "w"
                    raw_dir = isolation_root / "o"
                    persistent_raw = root / "raw" / record_id
                    try:
                        _prepare_workspace(workspace)
                        install_run = _install_profile(
                            manifest,
                            workspace,
                            agent,
                            current_profile,
                            case,
                            include_local=include_local,
                            timeout=timeout,
                            npx_home=npx_home,
                        )
                        (workspace / "skills-lock.json").unlink(missing_ok=True)
                        invocation = _run_agent(
                            agent,
                            workspace,
                            _evaluation_prompt(case, agent),
                            raw_dir,
                            timeout=timeout,
                            max_budget_usd=max_budget_usd,
                            model=(models or {}).get(agent),
                            isolation_root=isolation_root,
                        )
                    except (EvaluationError, OSError) as exc:
                        raw_path = None
                        if keep_raw and raw_dir.is_dir():
                            persistent_raw.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(raw_dir, persistent_raw)
                            raw_path = persistent_raw.relative_to(root).as_posix()
                        record.update(
                            {
                                "status": "infrastructure-error",
                                "trigger_correct": None,
                                "error": str(exc),
                                "raw_path": raw_path,
                            }
                        )
                        checkpoint(record)
                        run_home.cleanup()
                        continue
                    metadata = trace_metadata(str(invocation["trace"]))
                    loaded, claimed, visible = parse_trace(
                        str(invocation.pop("trace")),
                        str(invocation["final_output"]),
                        known_skills,
                    )
                    final_output = str(invocation.pop("final_output"))
                    earned, total = score_output(final_output, case.rubric)
                    claim_violations = forbidden_claims(final_output, case.forbidden_claims)
                    observed = set(loaded)
                    evidence = "trace"
                    installed_skills = set(install_run["installed_skills"])
                    if agent == "codex" and claimed and claimed in installed_skills:
                        # Codex 0.147 has no stable Skill tool event in JSONL. A path read is
                        # authoritative when present; otherwise the requested terminal marker is
                        # an explicit proxy that quality rubrics can cross-check.
                        observed.add(claimed)
                        if claimed not in loaded:
                            evidence = "self-report-proxy"
                    elif agent == "codex" and claimed:
                        evidence = "unverified-self-report"
                    effective_expected = set(evaluated_expected)
                    effective_forbidden = set(evaluated_forbidden)
                    expected_loaded = effective_expected.issubset(observed)
                    forbidden_avoided = not effective_forbidden.intersection(observed)
                    trigger_correct = expected_loaded and forbidden_avoided
                    terminal_status = str(metadata.get("terminal_status") or "").lower()
                    run_succeeded = invocation["exit_code"] == 0 and not (
                        terminal_status == "failed"
                        or terminal_status == "error"
                        or terminal_status.startswith("error_")
                    )
                    raw_path = None
                    if keep_raw:
                        raw_dir.mkdir(parents=True, exist_ok=True)
                        persistent_raw.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(raw_dir, persistent_raw)
                        raw_path = persistent_raw.relative_to(root).as_posix()
                    run_home.cleanup()
                    record.update(
                        {
                            "status": "completed" if run_succeeded else "failed",
                            "install_commands": install_run["commands"],
                            "installed_skills": install_run["installed_skills"],
                            "install_hashes_verified": install_run["hashes_verified"],
                            "installed_skill_sha256": install_run.get(
                                "installed_skill_sha256", {}
                            ),
                            "installed_pack_sha256": install_run.get(
                                "installed_pack_sha256"
                            ),
                            "agent_visible_install_root": install_run.get(
                                "agent_visible_install_root"
                            ),
                            "installed_metadata_budget": install_run.get(
                                "installed_metadata_budget"
                            ),
                            "loaded_skills": sorted(loaded),
                            "visible_skills": sorted(visible),
                            "observed_skills": sorted(observed),
                            "observation_evidence": evidence,
                            "claimed_skill": claimed,
                            "expected_loaded": expected_loaded,
                            "forbidden_avoided": forbidden_avoided,
                            "unexpected_loaded_skills": sorted(
                                observed - effective_expected
                            ),
                            "trigger_correct": trigger_correct,
                            "rubric_earned": earned,
                            "rubric_total": total,
                            "forbidden_claims_found": claim_violations,
                            "final_output": final_output,
                            "raw_path": raw_path,
                            **metadata,
                            **invocation,
                        }
                    )
                    checkpoint(record)

    tool_versions = {
        "codex": None
        if dry_run
        else _version(["codex", "--version"], home=npx_home),
        "claude-code": None
        if dry_run
        else _version(["claude", "--version"], home=npx_home),
        "skills": None
        if dry_run
        else _version(
            ["npx", "--yes", SKILLS_CLI_PACKAGE, "--version"],
            home=npx_home,
        ),
    }
    if npx_home is not None:
        shutil.rmtree(npx_home, ignore_errors=True)

    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "created_at": datetime.now(UTC).isoformat(),
        "dry_run": dry_run,
        "agents": agents,
        "profile": profile,
        "repeat": repeat,
        "execution_plan": {
            "processes": len(cases) * len(agents) * repeat * len(profiles),
            "claude_calls": (
                len(cases) * repeat * len(profiles) if "claude-code" in agents else 0
            ),
            "claude_soft_cap_sum_usd": round(
                len(cases)
                * repeat
                * len(profiles)
                * max_budget_usd
                * (1 if "claude-code" in agents else 0),
                4,
            ),
        },
        "raw_traces_kept": keep_raw,
        "corpus_identity": corpus_identity,
        "requested_models": models or {},
        "tool_versions": tool_versions,
        "cases": serialized_cases,
        "records": records,
        "summary": _summary(records),
    }
    if mode == "quality":
        report["quality_comparisons"] = (
            [] if profile == "index-ab" else _quality_comparisons(records, profile)
        )
    if profile == "index-ab":
        report["index_comparisons"] = _index_comparisons(records)
    (root / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (root / "report.md").write_text(_markdown_report(report), encoding="utf-8")
    return report, root
