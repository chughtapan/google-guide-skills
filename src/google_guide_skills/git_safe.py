"""Git invocation defaults for an untrusted reusable source cache."""

from __future__ import annotations

import configparser
import os
from pathlib import Path


def command(*args: str) -> list[str]:
    """Build a Git command with hooks and filesystem monitoring disabled."""
    return [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        *args,
    ]


def environment(checkout: Path | None = None) -> dict[str, str]:
    """Build a minimal Git environment isolated from user configuration."""
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
    }
    env = {key: value for key, value in os.environ.items() if key in allowed}
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    if checkout is not None:
        env["GIT_DIR"] = str((checkout / ".git").resolve())
        env["GIT_WORK_TREE"] = str(checkout.resolve())
    return env


def git_dir_is_safe(checkout: Path) -> bool:
    """Return whether the checkout has a real, symlink-free .git directory."""
    git_dir = checkout / ".git"
    return (
        git_dir.is_dir()
        and not git_dir.is_symlink()
        and not any(path.is_symlink() for path in git_dir.rglob("*"))
    )


def _config_policy(
    section: str, expected_url: str, default_branch: str
) -> tuple[dict[str, set[str]], set[str]] | None:
    if section == "core":
        return (
            {
                "repositoryformatversion": {"0", "1"},
                "filemode": {"true", "false"},
                "bare": {"false"},
                "logallrefupdates": {"true"},
                "ignorecase": {"true", "false"},
                "precomposeunicode": {"true", "false"},
            },
            {"repositoryformatversion", "bare"},
        )
    if section == 'remote "origin"':
        return (
            {
                "url": {expected_url, expected_url.removesuffix(".git")},
                "fetch": {
                    "+refs/heads/*:refs/remotes/origin/*",
                    f"+refs/heads/{default_branch}:refs/remotes/origin/{default_branch}",
                },
                "promisor": {"true"},
                "partialclonefilter": {"blob:none"},
            },
            {"url", "fetch"},
        )
    if section == f'branch "{default_branch.lower()}"':
        return (
            {"remote": {"origin"}, "merge": {f"refs/heads/{default_branch}"}},
            {"remote", "merge"},
        )
    return None


def _section_problem(
    parser: configparser.ConfigParser,
    section: str,
    expected_url: str,
    default_branch: str,
) -> str | None:
    normalized = section.lower()
    policy = _config_policy(normalized, expected_url, default_branch)
    if policy is None:
        return f"forbidden section [{section}] in .git/config"
    allowed, required = policy
    values = {key.lower(): value.strip() for key, value in parser.items(section)}
    unknown = sorted(set(values) - set(allowed))
    if unknown:
        return f"forbidden key {normalized}.{unknown[0]} in .git/config"
    missing = sorted(required - set(values))
    if missing:
        return f"missing key {normalized}.{missing[0]} in .git/config"
    for key, value in values.items():
        if value not in allowed[key]:
            return f"unsafe value for {normalized}.{key} in .git/config"
    return None


def repository_config_problem(checkout: Path, expected_url: str, default_branch: str) -> str | None:
    """Return why an untrusted checkout's local config is unsafe, if anything."""
    config_path = checkout / ".git" / "config"
    if config_path.is_symlink() or not config_path.is_file():
        return "missing or symlinked .git/config"
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        with config_path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
    except (OSError, UnicodeError, configparser.Error) as exc:
        return f"unreadable .git/config: {exc}"
    if parser.defaults():
        return "DEFAULT entries are forbidden in .git/config"
    for section in parser.sections():
        problem = _section_problem(parser, section, expected_url, default_branch)
        if problem:
            return problem
    if "core" not in {section.lower() for section in parser.sections()}:
        return "missing [core] section in .git/config"
    return None
