"""Git invocation defaults for an untrusted reusable source cache."""

from __future__ import annotations

import configparser
import os
from pathlib import Path


def command(*args: str) -> list[str]:
    return [
        "git",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        *args,
    ]


def environment(checkout: Path | None = None) -> dict[str, str]:
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
    git_dir = checkout / ".git"
    return (
        git_dir.is_dir()
        and not git_dir.is_symlink()
        and not any(path.is_symlink() for path in git_dir.rglob("*"))
    )


def repository_config_problem(
    checkout: Path, expected_url: str, default_branch: str
) -> str | None:
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

    expected_sections = {
        "core",
        'remote "origin"',
        f'branch "{default_branch.lower()}"',
    }
    for section in parser.sections():
        normalized_section = section.lower()
        if normalized_section not in expected_sections:
            return f"forbidden section [{section}] in .git/config"
        values = {key.lower(): value.strip() for key, value in parser.items(section)}
        if normalized_section == "core":
            allowed = {
                "repositoryformatversion": {"0", "1"},
                "filemode": {"true", "false"},
                "bare": {"false"},
                "logallrefupdates": {"true"},
                "ignorecase": {"true", "false"},
                "precomposeunicode": {"true", "false"},
            }
            required = {"repositoryformatversion", "bare"}
        elif normalized_section == 'remote "origin"':
            accepted_urls = {expected_url, expected_url.removesuffix(".git")}
            allowed = {
                "url": accepted_urls,
                "fetch": {
                    "+refs/heads/*:refs/remotes/origin/*",
                    f"+refs/heads/{default_branch}:refs/remotes/origin/{default_branch}",
                },
                "promisor": {"true"},
                "partialclonefilter": {"blob:none"},
            }
            required = {"url", "fetch"}
        else:
            allowed = {
                "remote": {"origin"},
                "merge": {f"refs/heads/{default_branch}"},
            }
            required = {"remote", "merge"}
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            return f"forbidden key {normalized_section}.{unknown[0]} in .git/config"
        missing = sorted(required - set(values))
        if missing:
            return f"missing key {normalized_section}.{missing[0]} in .git/config"
        for key, value in values.items():
            if value not in allowed[key]:
                return f"unsafe value for {normalized_section}.{key} in .git/config"
    if "core" not in {section.lower() for section in parser.sections()}:
        return "missing [core] section in .git/config"
    return None
