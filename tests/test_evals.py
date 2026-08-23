"""Tests for the offline-safe Agent Skills evaluation harness."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from google_guide_skills import cli
from google_guide_skills import evals as eval_module
from google_guide_skills.errors import EvaluationError
from google_guide_skills.evals import (
    EvalCase,
    _evaluation_prompt,
    _filesystem_sandbox_command,
    _final_from_claude_trace,
    _index_comparisons,
    _install_profile,
    _isolated_agent_env,
    _markdown_report,
    _preflight_live,
    _quality_comparisons,
    _run_agent,
    _summary,
    _version,
    build_agent_command,
    forbidden_claims,
    load_cases,
    parse_trace,
    run_evaluation,
    score_output,
    select_cases,
    trace_metadata,
)
from google_guide_skills.models import (
    Artifact,
    Collection,
    LicenseInfo,
    Manifest,
    Repository,
)


def _artifact(name: str) -> Artifact:
    return Artifact(
        name=name,
        title=name.replace("-", " ").title(),
        description=f"Use {name} for its narrowly defined test purpose.",
        tags=("test",),
        layout="inline",
        inputs=(f"{name}.md",),
    )


@pytest.fixture
def manifest(tmp_path: Path) -> Manifest:
    """A complete manifest with committed and local-only skill distributions."""
    license_info = LicenseInfo(
        spdx="Apache-2.0",
        name="Apache License 2.0",
        url="https://example.test/license",
        attribution="Example",
        audited="2026-08-22",
        allow_committed_output=True,
    )
    alpha = _artifact("alpha-style")
    beta = _artifact("beta-review")
    local = _artifact("local-testing")
    value = Manifest(
        path=tmp_path / "corpus.yaml",
        schema_version=1,
        canonical_python=platform.python_version(),
        generated_roots={"committed": "skills", "local_only": ".generated/skills"},
        repositories={
            "example": Repository(
                id="example",
                url="https://example.test/repository.git",
                revision="0" * 40,
                default_branch="main",
                license=license_info,
            )
        },
        collections={
            "committed": Collection(
                id="committed",
                repository="example",
                distribution="committed",
                description="Committed fixtures",
                artifacts=(alpha, beta),
            ),
            "restricted": Collection(
                id="restricted",
                repository="example",
                distribution="local-only",
                description="Local fixtures",
                artifacts=(local,),
                license_override=license_info,
            ),
        },
    )
    value.path.write_text("schema_version: 1\n", encoding="utf-8")
    for distribution, names in (
        ("committed", ("alpha-style", "beta-review", "google-guides-index")),
        ("local-only", ("local-testing",)),
    ):
        for name in names:
            skill = value.root_for(distribution) / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    return value


def _write_cases(path: Path, data: object) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _case(
    case_id: str = "alpha-positive",
    *,
    expected: tuple[str, ...] = ("alpha-style",),
    forbidden: tuple[str, ...] = (),
    rubric: tuple[tuple[str, ...], ...] = ((r"snake.case",),),
) -> EvalCase:
    return EvalCase(
        id=case_id,
        stage="representative",
        split="validation",
        prompt="Review this example.",
        expected_skills=expected,
        forbidden_skills=forbidden,
        rubric=rubric,
    )


def test_load_cases_expands_representative_defaults(manifest: Manifest, tmp_path: Path) -> None:
    path = _write_cases(
        tmp_path / "cases.yaml",
        {
            "schema_version": 1,
            "smoke": [
                {
                    "id": "smoke-alpha",
                    "prompt": "  Apply alpha style.  ",
                    "expected": ["alpha-style"],
                    "rubric": [[r"alpha|first"], [r"style"]],
                    "forbidden_claims": [r"must always", r"invented\s+policy"],
                }
            ],
            "local_smoke": [
                {
                    "id": "smoke-local",
                    "prompt": "Use the local fixture.",
                    "expected": ["local-testing"],
                }
            ],
            "representative": [
                {
                    "skill": "beta-review",
                    "positive": [{"id": "beta-pos", "split": "train", "prompt": "Review beta."}],
                    "negative": [{"id": "beta-neg", "prompt": "Do an unrelated task."}],
                }
            ],
        },
    )

    cases = load_cases(manifest, path)

    assert [case.id for case in cases] == [
        "smoke-alpha",
        "smoke-local",
        "beta-pos",
        "beta-neg",
    ]
    assert cases[0].prompt == "Apply alpha style."
    assert cases[0].rubric == ((r"alpha|first",), (r"style",))
    assert cases[0].forbidden_claims == (r"must always", r"invented\s+policy")
    assert cases[1].stage == "local-smoke"
    assert cases[2].stage == "representative"
    assert cases[2].split == "train"
    assert cases[2].expected_skills == ("beta-review",)
    assert cases[2].forbidden_skills == ()
    assert cases[3].split == "validation"
    assert cases[3].expected_skills == ()
    assert cases[3].forbidden_skills == ("beta-review",)


def test_load_cases_expands_controls_and_profile_specific_index_expectations(
    manifest: Manifest, tmp_path: Path
) -> None:
    path = _write_cases(
        tmp_path / "index-cases.yaml",
        {
            "schema_version": 1,
            "explicit_controls": {
                "prompt_template": "{invocation}\nState which skill you used.",
            },
            "smoke": [
                {
                    "id": "smoke-alpha",
                    "prompt": "Apply alpha.",
                    "expected": ["alpha-style"],
                }
            ],
            "index_experiment": {
                "forbid_index_on_direct_smoke": True,
                "cases": [
                    {
                        "id": "broad",
                        "prompt": "Route this broad task.",
                        "expected": ["google-guides-index"],
                        "profiles": {
                            "all-no-index": {
                                "expected": [],
                                "forbidden": ["google-guides-index"],
                            }
                        },
                    }
                ],
            },
        },
    )

    cases = load_cases(manifest, path)
    by_id = {case.id: case for case in cases}

    control = by_id["control-alpha-style"]
    assert _evaluation_prompt(control, "codex").startswith("$alpha-style\n")
    assert _evaluation_prompt(control, "claude-code").startswith("/alpha-style\n")
    assert by_id["smoke-alpha"].expectations_for("all") == (
        ("alpha-style",),
        ("google-guides-index",),
    )
    assert by_id["broad"].expectations_for("all-no-index") == (
        (),
        ("google-guides-index",),
    )


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "schema_version"),
        ({"schema_version": 1, "smoke": []}, "non-empty smoke"),
        (
            {"schema_version": 1, "smoke": [{"id": "BAD", "prompt": "x"}]},
            "lowercase letters",
        ),
        (
            {"schema_version": 1, "smoke": [{"id": "valid", "prompt": " "}]},
            "non-empty string",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x", "split": "test"}],
            },
            "train or validation",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x", "expected": "alpha-style"}],
            },
            "list of non-empty strings",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x", "rubric": [["("]]}],
            },
            "invalid regex",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x", "forbidden_claims": ["("]}],
            },
            "forbidden_claims has an invalid regex",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x"}],
                "representative": {},
            },
            "representative must be a list",
        ),
        (
            {
                "schema_version": 1,
                "smoke": [{"id": "valid", "prompt": "x"}],
                "explicit_controls": {"prompt_template": "Please invoke {invocation}."},
            },
            "must begin with",
        ),
    ],
)
def test_load_cases_rejects_invalid_shapes(
    manifest: Manifest, tmp_path: Path, data: object, message: str
) -> None:
    path = _write_cases(tmp_path / "invalid.yaml", data)

    with pytest.raises(EvaluationError, match=message):
        load_cases(manifest, path)


def test_load_cases_wraps_unhashable_yaml_keys(manifest: Manifest, tmp_path: Path) -> None:
    path = tmp_path / "unhashable-cases.yaml"
    path.write_text("? [a, b]\n: c\n", encoding="utf-8")

    with pytest.raises(EvaluationError, match="hashable scalars"):
        load_cases(manifest, path)


@pytest.mark.parametrize(
    ("smoke", "message"),
    [
        (
            [
                {"id": "duplicate", "prompt": "one"},
                {"id": "duplicate", "prompt": "two"},
            ],
            "Duplicate evaluation case id",
        ),
        (
            [{"id": "unknown", "prompt": "x", "expected": ["missing-skill"]}],
            "references unknown skills",
        ),
        (
            [
                {
                    "id": "overlap",
                    "prompt": "x",
                    "expected": ["alpha-style"],
                    "forbidden": ["alpha-style"],
                }
            ],
            "both expects and forbids",
        ),
    ],
)
def test_load_cases_checks_cross_case_invariants(
    manifest: Manifest, tmp_path: Path, smoke: list[dict[str, object]], message: str
) -> None:
    path = _write_cases(tmp_path / "invalid-invariants.yaml", {"schema_version": 1, "smoke": smoke})

    with pytest.raises(EvaluationError, match=message):
        load_cases(manifest, path)


def test_load_cases_wraps_io_and_yaml_errors(manifest: Manifest, tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="Cannot read evaluation cases"):
        load_cases(manifest, tmp_path / "missing.yaml")

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("smoke: [\n", encoding="utf-8")
    with pytest.raises(EvaluationError, match="Invalid evaluation YAML"):
        load_cases(manifest, malformed)


def test_select_cases_combines_filters_rubrics_and_limit() -> None:
    cases = [
        _case("smoke-train", rubric=()),
        EvalCase(
            id="representative-train",
            stage="representative",
            split="train",
            prompt="one",
            expected_skills=("alpha-style",),
            forbidden_skills=(),
            rubric=(("one",),),
        ),
        _case("representative-validation"),
    ]
    cases[0] = EvalCase(**{**cases[0].__dict__, "stage": "smoke", "split": "train"})

    selected = select_cases(
        cases,
        stages=["representative"],
        splits=["train", "validation"],
        case_ids=["representative-train", "representative-validation"],
        require_rubric=True,
        limit=1,
    )

    assert [case.id for case in selected] == ["representative-train"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"case_ids": ["absent"]}, "Unknown or filtered"),
        ({"limit": 0}, "limit must be positive"),
        ({"stages": ["missing"]}, "No evaluation cases"),
        ({"require_rubric": True}, "No evaluation cases"),
    ],
)
def test_select_cases_rejects_bad_or_empty_selections(
    kwargs: dict[str, object], message: str
) -> None:
    with pytest.raises(EvaluationError, match=message):
        select_cases([_case(rubric=())], **kwargs)


def test_parse_trace_separates_inventory_loads_and_last_self_report() -> None:
    trace = "\n".join(
        [
            "not-json",
            json.dumps(
                {
                    "type": "system",
                    "subtype": "init",
                    "skills": [
                        {"name": "alpha-style"},
                        "beta-review",
                        {"name": "unknown"},
                    ],
                }
            ),
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "tool-beta",
                                "name": "Skill",
                                "input": {"skill": "beta-review"},
                            }
                        ]
                    }
                }
            ),
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "tool-beta",
                                "content": "loaded",
                            }
                        ]
                    }
                }
            ),
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "read-alpha",
                                "name": "Read",
                                "input": {"file_path": ".claude/skills/alpha-style/SKILL.md"},
                            },
                            {
                                "type": "tool_result",
                                "tool_use_id": "read-alpha",
                                "content": "guide",
                            },
                        ]
                    }
                }
            ),
            "Read .agents/skills/alpha-style/SKILL.md and .claude\\skills\\beta-review\\SKILL.md",
        ]
    )

    loaded, claimed, visible = parse_trace(
        trace,
        "EVAL_SKILL: none\nEVAL_SKILL: ALPHA-STYLE",
        {"alpha-style", "beta-review"},
    )

    assert loaded == {"alpha-style", "beta-review"}
    assert claimed == "alpha-style"
    assert visible == {"alpha-style", "beta-review"}


def test_parse_trace_requires_successful_claude_tool_results() -> None:
    trace = "\n".join(
        [
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_use",
                                "id": "failed-skill",
                                "name": "Skill",
                                "input": {"skill": "alpha-style"},
                            },
                            {
                                "type": "tool_use",
                                "id": "unfinished-read",
                                "name": "Read",
                                "input": {"file_path": ".claude/skills/beta-review/SKILL.md"},
                            },
                        ]
                    }
                }
            ),
            json.dumps(
                {
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "failed-skill",
                                "is_error": True,
                                "content": "not installed",
                            }
                        ]
                    }
                }
            ),
        ]
    )

    loaded, _claimed, _visible = parse_trace(trace, "", {"alpha-style", "beta-review"})

    assert loaded == set()


def test_parse_trace_normalizes_none_marker_and_ignores_unknowns() -> None:
    loaded, claimed, visible = parse_trace(
        '{"name":"Skill","input":{"skill":"unknown"}}',
        "Answer. EVAL_SKILL: none",
        {"alpha-style"},
    )

    assert loaded == set()
    assert claimed is None
    assert visible == set()


def test_parse_trace_does_not_treat_plain_path_mentions_as_skill_loads() -> None:
    loaded, _claimed, _visible = parse_trace(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": "I could read .agents/skills/alpha-style/SKILL.md",
                },
            }
        ),
        "",
        {"alpha-style"},
    )

    assert loaded == set()


def test_score_output_supports_regex_alternatives_case_and_newlines() -> None:
    rubric = ((r"snake.case", r"lowercase.*underscore"), (r"mutable\s+default",), (r"absent",))

    assert score_output("Use SNAKE_CASE. Avoid a mutable\ndefault.", rubric) == (2, 3)
    assert score_output("anything", ()) == (0, 0)


def test_forbidden_claims_returns_the_matching_patterns_in_manifest_order() -> None:
    patterns = (r"must always", r"invented\s+policy", r"never matches")

    assert forbidden_claims("This MUST ALWAYS be an invented\npolicy.", patterns) == [
        r"must always",
        r"invented\s+policy",
    ]


def test_trace_metadata_normalizes_codex_claude_and_budget_events() -> None:
    trace = "\n".join(
        [
            "Skill descriptions were shortened to fit the metadata budget.",
            "not-json",
            json.dumps({"type": "system", "subtype": "init", "model": "claude-test"}),
            json.dumps({"type": "turn.completed", "usage": {"input_tokens": 12}}),
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "usage": {"input_tokens": 20},
                    "total_cost_usd": 0.012,
                    "is_error": False,
                }
            ),
            json.dumps({"type": "turn.failed"}),
        ]
    )

    assert trace_metadata(trace) == {
        "usage": {"input_tokens": 20},
        "cost_usd": 0.012,
        "terminal_status": "failed",
        "resolved_model": "claude-test",
        "skill_budget_warning": True,
    }
    assert trace_metadata('{"type":"result","is_error":true}') == {
        "usage": None,
        "cost_usd": None,
        "terminal_status": "error",
        "resolved_model": None,
        "skill_budget_warning": False,
    }
    assert (
        trace_metadata(
            json.dumps(
                {
                    "type": "result",
                    "is_error": True,
                    "subtype": "error_max_budget_usd",
                    "result": "provider budget exhausted",
                }
            )
        )["terminal_error"]
        == "provider budget exhausted"
    )


def test_build_codex_command_is_ephemeral_read_only_and_model_pinned(tmp_path: Path) -> None:
    output = tmp_path / "final.txt"
    command = build_agent_command(
        "codex",
        tmp_path,
        "review prompt",
        output,
        max_budget_usd=1.0,
        model="gpt-test",
    )

    assert command[:3] == ["codex", "exec", "--ephemeral"]
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--strict-config" in command
    assert command[command.index("-c") + 1] == "shell_environment_policy.inherit=none"
    assert command[command.index("--output-last-message") + 1] == str(output)
    assert command[command.index("-C") + 1] == str(tmp_path)
    assert command[-3:] == ["--model", "gpt-test", "review prompt"]


def test_build_claude_command_disables_mutating_tools_and_external_configuration(
    tmp_path: Path,
) -> None:
    command = build_agent_command(
        "claude-code",
        tmp_path,
        "review prompt",
        tmp_path / "unused.txt",
        max_budget_usd=0.125,
    )

    assert command[0] == "claude"
    assert "--no-session-persistence" in command
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert command[command.index("--setting-sources") + 1] == "project"
    assert "--strict-mcp-config" in command
    assert command[command.index("--mcp-config") + 1] == '{"mcpServers":{}}'
    assert "--no-chrome" in command
    assert command[command.index("--tools") + 1] == "Skill,Read,Glob,Grep"
    assert command[command.index("--max-budget-usd") + 1] == "0.125"
    assert command[-1] == "review prompt"


def test_build_agent_command_rejects_unknown_agent(tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="Unsupported evaluation agent"):
        build_agent_command("unknown", tmp_path, "prompt", tmp_path / "out", max_budget_usd=1.0)


def test_isolated_agent_env_uses_only_disposable_codex_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "isolated"
    target.mkdir()
    monkeypatch.setenv("SENTINEL_SECRET", "must-not-leak")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-key-must-not-win")
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "disposable-key")

    env = _isolated_agent_env("codex", target)

    assert env["CODEX_HOME"] == str(target / "codex")
    assert env["OPENAI_API_KEY"] == "disposable-key"
    assert not (target / "codex/auth.json").exists()
    assert env["HOME"] == str(target / "home")
    assert "SENTINEL_SECRET" not in env


def test_isolated_agent_env_supports_claude_api_key_without_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "isolated"
    target.mkdir()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-key-must-not-win")
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY", "disposable-key")

    env = _isolated_agent_env("claude-code", target)

    assert env["CLAUDE_CONFIG_DIR"] == str(target / "claude")
    assert env["ANTHROPIC_API_KEY"] == "disposable-key"
    assert not (target / "claude/.credentials.json").exists()


def test_isolated_agent_env_can_publish_only_short_sandbox_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / ("very-long-host-path-" * 4)
    target.mkdir()
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "disposable-key")

    env = _isolated_agent_env("codex", target, visible_root=Path("/h"))

    assert env["HOME"] == "/h/home"
    assert env["CODEX_HOME"] == "/h/codex"
    assert (target / "home").is_dir()
    assert (target / "codex").is_dir()


def test_prepare_workspace_initializes_one_fresh_git_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "ambient-template"
    (template / "hooks").mkdir(parents=True)
    (template / "hooks" / "injected").write_text("ambient\n", encoding="utf-8")
    config = tmp_path / "ambient-gitconfig"
    config.write_text(f"[init]\n\ttemplateDir = {template.as_posix()}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    workspace = tmp_path / "workspace"
    eval_module._prepare_workspace(workspace)

    assert (workspace / ".git").is_dir()
    assert not (workspace / ".git" / "hooks" / "injected").exists()
    branch = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=workspace,
        text=True,
        capture_output=True,
        check=True,
    )
    assert branch.stdout.strip() == "main"
    with pytest.raises(FileExistsError):
        eval_module._prepare_workspace(workspace)


def test_run_agent_passes_minimal_env_and_deletes_temporary_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/fake")
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "provider-key")
    monkeypatch.setenv("SENTINEL_SECRET", "must-not-leak")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-auth-file"))
    seen_home: list[Path] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        env = kwargs["env"]
        assert isinstance(env, dict)
        assert env["OPENAI_API_KEY"] == "provider-key"
        assert "SENTINEL_SECRET" not in env
        assert env["HOME"] == "/h/home"
        assert env["CODEX_HOME"] == "/h/codex"
        bind_pairs = [
            (Path(command[index + 1]), command[index + 2])
            for index, value in enumerate(command)
            if value == "--bind"
        ]
        state_root = next(source for source, target in bind_pairs if target == "/h")
        assert (state_root / "home").is_dir()
        assert (state_root / "codex").is_dir()
        seen_home.append(state_root)
        (tmp_path / "raw-isolated/final.txt").write_text("answer provider-key", encoding="utf-8")
        return subprocess.CompletedProcess(
            command, 0, stdout='{"leak":"provider-key"}\n', stderr="provider-key"
        )

    monkeypatch.setattr(eval_module.subprocess, "run", fake_run)
    result = _run_agent(
        "codex",
        tmp_path,
        "prompt",
        tmp_path / "raw-isolated",
        timeout=5,
        max_budget_usd=0.25,
        model="test-model",
    )

    assert result["exit_code"] == 0
    assert "provider-key" not in str(result)
    assert "[REDACTED_EVAL_KEY]" in str(result)
    assert result["stderr_excerpt"] == "[REDACTED_EVAL_KEY]"
    assert seen_home
    assert not seen_home[0].exists()


@pytest.mark.parametrize(
    ("agent", "env_name", "config_name"),
    [
        ("codex", "GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "CODEX_HOME"),
        (
            "claude-code",
            "GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY",
            "CLAUDE_CONFIG_DIR",
        ),
    ],
)
def test_isolated_agent_env_requires_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    agent: str,
    env_name: str,
    config_name: str,
) -> None:
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    monkeypatch.delenv(env_name, raising=False)
    monkeypatch.setenv(config_name, str(tmp_path / "missing"))

    with pytest.raises(EvaluationError, match="requires a disposable key"):
        _isolated_agent_env(agent, temporary)


def test_live_preflight_checks_every_binary_and_disposable_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = {"npx", "bwrap", "codex", "claude"}
    monkeypatch.setattr(
        eval_module.shutil,
        "which",
        lambda binary: f"/bin/{binary}" if binary in available else None,
    )
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_OPENAI_API_KEY", "codex-key")
    monkeypatch.setenv("GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY", "claude-key")

    _preflight_live(["codex", "claude-code"])

    available.remove("claude")
    with pytest.raises(EvaluationError, match="agent CLI is not installed: claude"):
        _preflight_live(["claude-code"])
    available.add("claude")
    monkeypatch.delenv("GOOGLE_GUIDES_EVAL_ANTHROPIC_API_KEY")
    with pytest.raises(EvaluationError, match="requires a disposable key"):
        _preflight_live(["claude-code"])


def test_live_preflight_requires_npx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: None)

    with pytest.raises(EvaluationError, match="npx is required"):
        _preflight_live(["codex"])


def test_filesystem_sandbox_hides_sibling_canary_from_agent_run(tmp_path: Path) -> None:
    if shutil.which("bwrap") is None:
        pytest.skip("bubblewrap is not installed")
    isolation_root = tmp_path / "isolated-run"
    project = isolation_root / "project"
    project.mkdir(parents=True)
    canary = tmp_path / "outer-secret"
    canary.write_text("must stay hidden", encoding="utf-8")
    visible = project / "visible"
    visible.write_text("inside", encoding="utf-8")

    command = _filesystem_sandbox_command(
        "claude-code",
        [
            "sh",
            "-c",
            f"test -f /w/{visible.name} && test ! -e {canary} && "
            f"test ! -e {Path(__file__).resolve().parents[1] / 'corpus.yaml'}",
        ],
        project,
        isolation_root,
    )
    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0, completed.stderr
    assert command[command.index("--chdir") + 1] == "/w"
    bind_pairs = [
        (command[index + 1], command[index + 2])
        for index, value in enumerate(command)
        if value == "--bind"
    ]
    assert (str(project.resolve()), "/w") in bind_pairs


def test_final_from_claude_trace_uses_last_result_event() -> None:
    trace = "\n".join(
        [
            "not-json",
            json.dumps({"type": "result", "result": "first"}),
            json.dumps({"type": "assistant", "result": "ignored"}),
            json.dumps({"type": "result", "result": "last"}),
        ]
    )

    assert _final_from_claude_trace(trace) == "last"


def test_run_agent_records_codex_trace_and_final_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/fake")
    monkeypatch.setattr(eval_module, "_isolated_agent_env", lambda _agent, _path, **_kwargs: {})
    ticks = iter((10.0, 11.2345))
    monkeypatch.setattr(eval_module.time, "monotonic", lambda: next(ticks))

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command[command.index("--output-last-message") + 1] == "/o/final.txt"
        assert command[command.index("-C") + 1] == "/w"
        (tmp_path / "raw/final.txt").write_text(
            "Final answer. EVAL_SKILL: alpha-style", encoding="utf-8"
        )
        return subprocess.CompletedProcess(command, 0, stdout='{"type":"done"}\n', stderr="")

    monkeypatch.setattr(eval_module.subprocess, "run", fake_run)

    result = _run_agent(
        "codex",
        tmp_path,
        "prompt",
        tmp_path / "raw",
        timeout=5,
        max_budget_usd=0.25,
        model=None,
    )

    assert result["exit_code"] == 0
    assert result["duration_seconds"] == 1.235
    assert result["final_output"] == "Final answer. EVAL_SKILL: alpha-style"
    assert result["trace"] == '{"type":"done"}\n'
    assert (tmp_path / "raw/trace.jsonl").read_text(encoding="utf-8") == result["trace"]


def test_run_agent_extracts_claude_final_from_canned_trace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace = json.dumps({"type": "result", "result": "Claude answer"}) + "\n"
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/fake")
    monkeypatch.setattr(eval_module, "_isolated_agent_env", lambda _agent, _path, **_kwargs: {})
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 0, stdout=trace, stderr="warning"
        ),
    )

    result = _run_agent(
        "claude-code",
        tmp_path,
        "prompt",
        tmp_path / "raw-claude",
        timeout=5,
        max_budget_usd=0.25,
        model="claude-test",
    )

    assert result["final_output"] == "Claude answer"
    assert result["stderr_excerpt"] == "warning"
    assert (tmp_path / "raw-claude/final.txt").read_text(encoding="utf-8") == "Claude answer"
    assert (tmp_path / "raw-claude/stderr.txt").read_text(encoding="utf-8") == "warning"


def test_run_agent_normalizes_timeout_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/fake")
    monkeypatch.setattr(eval_module, "_isolated_agent_env", lambda _agent, _path, **_kwargs: {})

    def timeout(command: list[str], **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(command, 1, output=b'{"partial":true}\n', stderr=b"late")

    monkeypatch.setattr(eval_module.subprocess, "run", timeout)

    result = _run_agent(
        "codex",
        tmp_path,
        "prompt",
        tmp_path / "raw-timeout",
        timeout=1,
        max_budget_usd=0.25,
        model=None,
    )

    assert result["exit_code"] == 124
    assert result["trace"] == '{"partial":true}\n'
    assert result["final_output"] == ""
    assert result["stderr_excerpt"] == "late"
    assert (tmp_path / "raw-timeout/stderr.txt").read_text(encoding="utf-8") == "late"


def test_run_agent_rejects_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: None)

    with pytest.raises(EvaluationError, match="Required agent CLI"):
        _run_agent(
            "codex",
            tmp_path,
            "prompt",
            tmp_path / "raw",
            timeout=1,
            max_budget_usd=0.25,
            model=None,
        )


def test_version_normalizes_stdout_stderr_and_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, stdout="tool 1.2\nextra", stderr=""
        ),
    )
    assert _version(["tool", "--version"]) == "tool 1.2"

    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, stdout="", stderr="oops\n"),
    )
    assert _version(["tool", "--version"]) == "oops"

    def missing(*_args: object, **_kwargs: object) -> None:
        raise OSError("missing")

    monkeypatch.setattr(eval_module.subprocess, "run", missing)
    assert _version(["missing"]) is None


def _fake_profile_installer(
    manifest: Manifest,
    captured: dict[str, object],
    *,
    corrupt: bool = False,
    extra: bool = False,
):
    def install_commands(
        _manifest: Manifest,
        project: Path,
        agents: list[str],
        *,
        skills: list[str] | None,
        copy: bool,
    ) -> list[list[str]]:
        captured.update(
            {
                "agents": agents,
                "skills": skills,
                "copy": copy,
            }
        )
        available = ["alpha-style", "beta-review", "google-guides-index"]
        names = available if skills is None else skills
        install_root = project / (".agents/skills" if agents == ["codex"] else ".claude/skills")
        for name in names:
            shutil.copytree(manifest.root_for("committed") / name, install_root / name)
        if corrupt and names:
            (install_root / names[0] / "SKILL.md").write_text("corrupt", encoding="utf-8")
        if extra:
            rogue = install_root / "rogue-skill"
            rogue.mkdir()
        return [["npx", "fake-install"]]

    return install_commands


@pytest.mark.parametrize(
    ("profile", "expected_selection", "expected_installed"),
    [
        (
            "single",
            ["alpha-style", "beta-review"],
            ["alpha-style", "beta-review"],
        ),
        ("index", ["google-guides-index"], ["google-guides-index"]),
        ("all-no-index", ["alpha-style", "beta-review"], ["alpha-style", "beta-review"]),
        ("all", None, ["alpha-style", "beta-review", "google-guides-index"]),
    ],
)
def test_install_profile_selects_and_verifies_exact_skill_copies(
    manifest: Manifest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    expected_selection: list[str] | None,
    expected_installed: list[str],
) -> None:
    project = tmp_path / f"project-{profile}"
    project.mkdir()
    captured: dict[str, object] = {}
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")
    monkeypatch.setattr(
        eval_module, "install_commands", _fake_profile_installer(manifest, captured)
    )
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    result = _install_profile(
        manifest,
        project,
        "codex",
        profile,
        _case(forbidden=("beta-review",)),
        timeout=10,
    )

    assert captured["skills"] == expected_selection
    assert captured["copy"] is True
    assert result["installed_skills"] == expected_installed
    assert result["hashes_verified"] is True
    assert set(result["installed_skill_sha256"]) == set(expected_installed)
    assert len(result["installed_pack_sha256"]) == 64
    assert result["agent_visible_install_root"] == "/w/.agents/skills"
    budget = result["installed_metadata_budget"]
    assert isinstance(budget, dict)
    assert budget["reference_install_root"] == "/w/.agents/skills"
    assert budget["codex_list_chars"] <= budget["codex_fallback_limit_chars"]


def test_install_profile_baseline_never_checks_or_invokes_npx(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        eval_module.shutil,
        "which",
        lambda _binary: pytest.fail("baseline must not inspect npx"),
    )

    assert _install_profile(
        manifest,
        tmp_path,
        "codex",
        "baseline",
        _case(),
        timeout=1,
    ) == {
        "commands": [],
        "installed_skills": [],
        "hashes_verified": True,
        "installed_skill_sha256": {},
        "installed_pack_sha256": eval_module._canonical_digest({}),
    }


def test_install_profile_rejects_missing_npx_and_invalid_profiles(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: None)
    with pytest.raises(EvaluationError, match="npx is required"):
        _install_profile(
            manifest,
            tmp_path,
            "codex",
            "all",
            _case(),
            timeout=1,
        )

    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")
    with pytest.raises(EvaluationError, match="Unsupported evaluation profile"):
        _install_profile(
            manifest,
            tmp_path,
            "codex",
            "bad",
            _case(),
            timeout=1,
        )
    with pytest.raises(EvaluationError, match="no candidate skill"):
        _install_profile(
            manifest,
            tmp_path,
            "codex",
            "single",
            _case(expected=(), rubric=()),
            timeout=1,
        )


def test_install_profile_detects_failed_install_and_hash_mismatch(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")
    project = tmp_path / "failed"
    project.mkdir()
    monkeypatch.setattr(eval_module, "install_commands", lambda *_args, **_kwargs: [["npx"]])
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(
            command, 1, stdout="install output", stderr="install error"
        ),
    )
    with pytest.raises(EvaluationError, match="Skill installation failed"):
        _install_profile(
            manifest,
            project,
            "codex",
            "index",
            _case(),
            timeout=1,
        )

    mismatch = tmp_path / "mismatch"
    mismatch.mkdir()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        eval_module,
        "install_commands",
        _fake_profile_installer(manifest, captured, corrupt=True),
    )
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )
    with pytest.raises(EvaluationError, match="Installed copy does not match"):
        _install_profile(
            manifest,
            mismatch,
            "codex",
            "index",
            _case(),
            timeout=1,
        )

    extra_project = tmp_path / "extra"
    extra_project.mkdir()
    monkeypatch.setattr(
        eval_module,
        "install_commands",
        _fake_profile_installer(manifest, captured, extra=True),
    )
    with pytest.raises(EvaluationError, match="undeclared skills"):
        _install_profile(
            manifest,
            extra_project,
            "codex",
            "index",
            _case(),
            timeout=1,
        )


def test_install_profile_rejects_symlinks_and_project_configuration(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")
    monkeypatch.setattr(
        eval_module.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    symlink_project = tmp_path / "symlink-install"
    symlink_project.mkdir()

    def symlink_installer(
        _manifest: Manifest,
        project: Path,
        _agents: list[str],
        **_kwargs: object,
    ) -> list[list[str]]:
        install_root = project / ".agents" / "skills"
        install_root.mkdir(parents=True)
        (install_root / "google-guides-index").symlink_to(
            manifest.root_for("committed") / "google-guides-index",
            target_is_directory=True,
        )
        return [["npx", "fake-install"]]

    monkeypatch.setattr(eval_module, "install_commands", symlink_installer)
    with pytest.raises(EvaluationError, match="unsafe skill entries"):
        _install_profile(
            manifest,
            symlink_project,
            "codex",
            "index",
            _case(),
            timeout=1,
        )

    configured_project = tmp_path / "configured-install"
    configured_project.mkdir()

    def configured_installer(
        _manifest: Manifest,
        project: Path,
        _agents: list[str],
        **_kwargs: object,
    ) -> list[list[str]]:
        shutil.copytree(
            manifest.root_for("committed") / "google-guides-index",
            project / ".agents" / "skills" / "google-guides-index",
        )
        (project / "AGENTS.md").write_text("injected instructions\n", encoding="utf-8")
        return [["npx", "fake-install"]]

    monkeypatch.setattr(eval_module, "install_commands", configured_installer)
    with pytest.raises(EvaluationError, match="unexpected project files: AGENTS.md"):
        _install_profile(
            manifest,
            configured_project,
            "codex",
            "index",
            _case(),
            timeout=1,
        )


def test_install_profile_rejects_empty_directory_git_drift(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "git-drift"
    (project / ".git").mkdir(parents=True)
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")

    def drift_installer(
        _manifest: Manifest,
        _target: Path,
        agents: list[str],
        *,
        skills: list[str] | None,
        copy: bool,
    ) -> list[list[str]]:
        assert agents == ["codex"]
        assert skills == ["google-guides-index"]
        assert copy is True
        return [["npx", "fake-install"]]

    def run_installer(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        shutil.copytree(
            manifest.root_for("committed") / "google-guides-index",
            project / ".agents/skills/google-guides-index",
        )
        (project / ".git/added-directory").mkdir()
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(eval_module, "install_commands", drift_installer)
    monkeypatch.setattr(eval_module.subprocess, "run", run_installer)

    with pytest.raises(EvaluationError, match="modified evaluation Git metadata"):
        _install_profile(
            manifest,
            project,
            "codex",
            "index",
            _case(),
            timeout=1,
        )


def test_install_profile_reports_timeout(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module.shutil, "which", lambda _binary: "/bin/npx")
    monkeypatch.setattr(eval_module, "install_commands", lambda *_args, **_kwargs: [["npx"]])

    def timeout(command: list[str], **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr(eval_module.subprocess, "run", timeout)
    with pytest.raises(EvaluationError, match="installation timed out"):
        _install_profile(
            manifest,
            tmp_path,
            "codex",
            "index",
            _case(),
            timeout=1,
        )


def test_summary_and_quality_comparisons_normalize_completed_records() -> None:
    records: list[dict[str, object]] = [
        {"status": "planned", "exit_code": None},
        {
            "status": "completed",
            "agent": "codex",
            "profile": "baseline",
            "case_id": "alpha",
            "repeat": 1,
            "exit_code": 0,
            "trigger_correct": True,
            "rubric_earned": 1,
            "rubric_total": 2,
        },
        {
            "status": "completed",
            "agent": "codex",
            "profile": "single",
            "case_id": "alpha",
            "repeat": 1,
            "exit_code": 3,
            "trigger_correct": False,
            "rubric_earned": 2,
            "rubric_total": 2,
        },
    ]

    assert _summary(records) == {
        "runs": 3,
        "completed": 2,
        "failed_processes": 0,
        "infrastructure_errors": 0,
        "successful_processes": 1,
        "trigger_correct": 1,
        "trigger_accuracy": 0.5,
        "rubric_earned": 3,
        "rubric_total": 4,
        "rubric_score": 0.75,
        "forbidden_claim_violations": 0,
        "positive_runs": 0,
        "positive_correct": 0,
        "positive_recall": None,
        "negative_runs": 0,
        "negative_correct": 0,
        "near_miss_specificity": None,
        "explicit_control_runs": 0,
        "explicit_control_correct": 0,
        "explicit_control_accuracy": None,
        "direct_prompt_runs": 0,
        "direct_prompt_exact": 0,
        "direct_prompt_exact_rate": None,
        "direct_index_steals": 0,
        "direct_index_steal_rate": None,
        "direct_prompts_with_unexpected": 0,
        "direct_unexpected_skill_loads": 0,
        "index_broad_runs": 0,
        "index_broad_loaded": 0,
        "index_broad_recall": None,
    }
    assert _quality_comparisons(records, "single") == [
        {
            "agent": "codex",
            "case_id": "alpha",
            "repeat": 1,
            "baseline_score": 1,
            "skilled_score": 2,
            "rubric_total": 2,
            "delta": 1,
            "baseline_forbidden_claims": 0,
            "skilled_forbidden_claims": 0,
            "fidelity_delta": 1,
        }
    ]

    index_records = [
        {
            "status": "completed",
            "stage": "index-experiment",
            "agent": "codex",
            "profile": "all-no-index",
            "case_id": "broad",
            "repeat": 1,
            "rubric_earned": 1,
            "rubric_total": 2,
            "observed_skills": ["alpha-style"],
        },
        {
            "status": "completed",
            "stage": "index-experiment",
            "agent": "codex",
            "profile": "all",
            "case_id": "broad",
            "repeat": 1,
            "rubric_earned": 2,
            "rubric_total": 2,
            "observed_skills": ["google-guides-index"],
        },
    ]
    assert _index_comparisons(index_records) == [
        {
            "agent": "codex",
            "case_id": "broad",
            "repeat": 1,
            "index_loaded": True,
            "without_index_rubric": 1,
            "with_index_rubric": 2,
            "rubric_total": 2,
            "rubric_delta": 1,
        }
    ]


def test_markdown_report_normalizes_missing_observations() -> None:
    report: dict[str, object] = {
        "mode": "triggers",
        "created_at": "2026-08-22T00:00:00+00:00",
        "summary": {
            "runs": 1,
            "completed": 0,
            "trigger_accuracy": None,
            "rubric_score": None,
        },
        "records": [
            {
                "agent": "codex",
                "profile": "all",
                "case_id": "alpha",
                "repeat": 1,
                "trigger_correct": None,
            }
        ],
    }

    markdown = _markdown_report(report)

    assert "| codex | all | alpha | 1 | none | none | None | 0/0 | - |" in markdown
    assert markdown.endswith("\n")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"mode": "bad"}, "mode must be"),
        ({"agents": []}, "Agents must be"),
        ({"agents": ["other"]}, "Agents must be"),
        ({"profile": "baseline"}, "Profile must be"),
        ({"repeat": 0}, "Repeat must be positive"),
        ({"timeout": 0}, "Timeout must be positive"),
        ({"max_budget_usd": 0}, "budget must be finite and positive"),
        ({"max_budget_usd": float("nan")}, "budget must be finite and positive"),
        ({"max_budget_usd": float("inf")}, "budget must be finite and positive"),
        ({"max_budget_usd": float("-inf")}, "budget must be finite and positive"),
    ],
)
def test_run_evaluation_validates_configuration_before_any_calls(
    manifest: Manifest, tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    kwargs: dict[str, object] = {
        "mode": "triggers",
        "agents": ["codex"],
        "profile": "single",
        "repeat": 1,
        "timeout": 1,
        "max_budget_usd": 0.25,
        "dry_run": True,
        "results_root": tmp_path / "results",
    }
    kwargs.update(overrides)

    with pytest.raises(EvaluationError, match=message):
        run_evaluation(manifest, [_case()], **kwargs)


def test_live_evaluation_requires_explicit_models(manifest: Manifest, tmp_path: Path) -> None:
    with pytest.raises(EvaluationError, match="explicit model"):
        run_evaluation(
            manifest,
            [_case()],
            mode="triggers",
            agents=["codex"],
            profile="single",
            dry_run=False,
            accept_credential_risk=True,
            results_root=tmp_path / "results",
        )


def test_local_only_evaluations_stay_ignored_and_never_run_hosted(
    manifest: Manifest, tmp_path: Path
) -> None:
    (manifest.project_root / ".gitignore").write_text("evals/results/\n", encoding="utf-8")
    subprocess.run(["git", "init", "--quiet"], cwd=manifest.project_root, check=True)
    local_case = _case("local-case", expected=("local-testing",), rubric=())
    with pytest.raises(EvaluationError, match="require --include-swe-book"):
        run_evaluation(
            manifest,
            [local_case],
            mode="triggers",
            agents=["codex"],
            profile="single",
            dry_run=True,
        )
    with pytest.raises(EvaluationError, match="must remain under"):
        run_evaluation(
            manifest,
            [local_case],
            mode="triggers",
            agents=["codex"],
            profile="single",
            include_local=True,
            dry_run=True,
            results_root=tmp_path / "outside-results",
        )
    report, output = run_evaluation(
        manifest,
        [local_case],
        mode="triggers",
        agents=["codex"],
        profile="single",
        include_local=True,
        dry_run=True,
    )
    assert report["summary"]["runs"] == 1
    assert output.resolve().is_relative_to((manifest.project_root / "evals" / "results").resolve())
    with pytest.raises(EvaluationError, match="hosted-agent evaluation"):
        run_evaluation(
            manifest,
            [local_case],
            mode="triggers",
            agents=["codex"],
            profile="single",
            include_local=True,
            dry_run=False,
            models={"codex": "test-model"},
            accept_credential_risk=True,
        )


def test_relative_results_root_is_resolved_from_project(
    manifest: Manifest,
) -> None:
    _report, output = run_evaluation(
        manifest,
        [_case()],
        mode="triggers",
        agents=["codex"],
        profile="single",
        dry_run=True,
        results_root=Path("reports/relative-eval"),
    )

    assert output.is_relative_to(manifest.project_root / "reports" / "relative-eval")


def test_trigger_plan_only_creates_normalized_report_without_live_helpers(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("_prepare_workspace", "_install_profile", "_run_agent", "_version"):
        monkeypatch.setattr(
            eval_module,
            name,
            lambda *_args, _name=name, **_kwargs: pytest.fail(
                f"dry run called live helper {_name}"
            ),
        )

    report, output = run_evaluation(
        manifest,
        [_case()],
        mode="triggers",
        agents=["codex", "claude-code"],
        profile="all",
        repeat=2,
        dry_run=True,
        results_root=tmp_path / "results",
    )

    assert report["dry_run"] is True
    assert len(report["corpus_identity"]["manifest_sha256"]) == 64
    assert len(report["corpus_identity"]["case_set_sha256"]) == 64
    assert report["records"][0]["manifest_sha256"] == report["corpus_identity"]["manifest_sha256"]
    assert report["summary"] == {
        "runs": 4,
        "completed": 0,
        "failed_processes": 0,
        "infrastructure_errors": 0,
        "successful_processes": 0,
        "trigger_correct": 0,
        "trigger_accuracy": None,
        "rubric_earned": 0,
        "rubric_total": 0,
        "rubric_score": None,
        "forbidden_claim_violations": 0,
        "positive_runs": 0,
        "positive_correct": 0,
        "positive_recall": None,
        "negative_runs": 0,
        "negative_correct": 0,
        "near_miss_specificity": None,
        "explicit_control_runs": 0,
        "explicit_control_correct": 0,
        "explicit_control_accuracy": None,
        "direct_prompt_runs": 0,
        "direct_prompt_exact": 0,
        "direct_prompt_exact_rate": None,
        "direct_index_steals": 0,
        "direct_index_steal_rate": None,
        "direct_prompts_with_unexpected": 0,
        "direct_unexpected_skill_loads": 0,
        "index_broad_runs": 0,
        "index_broad_loaded": 0,
        "index_broad_recall": None,
    }
    assert {record["status"] for record in report["records"]} == {"planned"}
    assert report["tool_versions"] == {"codex": None, "claude-code": None, "skills": None}
    persisted = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert persisted["cases"][0]["expected_skills"] == ["alpha-style"]
    assert (output / "report.md").is_file()
    assert not (output / "workspaces").exists()


def test_quality_plan_includes_baseline_and_requested_profile(
    manifest: Manifest, tmp_path: Path
) -> None:
    report, _output = run_evaluation(
        manifest,
        [_case()],
        mode="quality",
        agents=["codex"],
        profile="single",
        dry_run=True,
        results_root=tmp_path / "quality-results",
    )

    assert [record["profile"] for record in report["records"]] == ["baseline", "single"]
    assert report["quality_comparisons"] == []


def test_index_ab_plan_pairs_full_pack_with_no_index_profile(
    manifest: Manifest, tmp_path: Path
) -> None:
    case = EvalCase(
        id="broad",
        stage="index-experiment",
        split="validation",
        prompt="Route a broad request.",
        expected_skills=("google-guides-index",),
        forbidden_skills=(),
        profile_expectations=(("all-no-index", (), ("google-guides-index",)),),
    )

    report, _output = run_evaluation(
        manifest,
        [case],
        mode="quality",
        agents=["codex"],
        profile="index-ab",
        dry_run=True,
        results_root=tmp_path / "index-plan",
    )

    assert [record["profile"] for record in report["records"]] == [
        "all-no-index",
        "all",
    ]
    assert report["records"][0]["expected_skills"] == []
    assert report["records"][1]["expected_skills"] == ["google-guides-index"]
    assert report["index_comparisons"] == []


def test_live_evaluation_uses_canned_trace_and_removes_raw_workspace(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    prepared: list[Path] = []

    def prepare(path: Path) -> None:
        path.mkdir(parents=True)
        prepared.append(path)

    def run_agent(
        _agent: str,
        workspace: Path,
        prompt: str,
        raw_dir: Path,
        *,
        timeout: int,
        max_budget_usd: float,
        model: str | None,
        isolation_root: Path | None = None,
    ) -> dict[str, object]:
        assert workspace.name == "w"
        assert timeout == 180
        assert max_budget_usd == 0.25
        assert model == "test-model"
        assert isolation_root == workspace.parent
        raw_dir.mkdir(parents=True)
        assert "Do not edit files" in prompt
        assert "EVAL_SKILL" in prompt
        return {
            "command": ["codex", "fake"],
            "duration_seconds": 0.5,
            "exit_code": 0,
            "final_output": "Use snake_case. EVAL_SKILL: alpha-style",
            "trace": json.dumps(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": "sed .agents/skills/alpha-style/SKILL.md",
                        "exit_code": 0,
                    },
                }
            ),
        }

    monkeypatch.setattr(eval_module, "_prepare_workspace", prepare)

    def install_profile(
        _manifest: Manifest,
        workspace: Path,
        agent: str,
        profile: str,
        _case_value: EvalCase,
        *,
        timeout: int,
        npx_home: Path | None = None,
    ) -> dict[str, object]:
        assert workspace.name == "w"
        assert agent == "codex"
        assert profile == "single"
        assert timeout == 180
        assert npx_home is not None
        return {
            "commands": [["npx", "fake"]],
            "installed_skills": ["alpha-style"],
            "hashes_verified": True,
        }

    monkeypatch.setattr(eval_module, "_install_profile", install_profile)
    monkeypatch.setattr(eval_module, "_run_agent", run_agent)
    monkeypatch.setattr(eval_module, "_version", lambda command, **_kwargs: f"{command[0]} test")

    report, output = run_evaluation(
        manifest,
        [_case()],
        mode="triggers",
        agents=["codex"],
        profile="single",
        models={"codex": "test-model"},
        accept_credential_risk=True,
        dry_run=False,
        keep_raw=False,
        results_root=tmp_path / "live-results",
    )

    record = report["records"][0]
    assert record["loaded_skills"] == ["alpha-style"]
    assert record["claimed_skill"] == "alpha-style"
    assert record["observed_skills"] == ["alpha-style"]
    assert record["observation_evidence"] == "trace"
    assert record["trigger_correct"] is True
    assert record["rubric_earned"] == 1
    assert report["summary"]["trigger_accuracy"] == 1.0
    assert prepared
    assert not prepared[0].exists()
    assert not (output / "raw" / record["id"]).exists()


def test_full_pack_direct_smoke_reports_unexpected_skill_as_routing_failure(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    monkeypatch.setattr(eval_module, "_prepare_workspace", lambda path: path.mkdir(parents=True))
    monkeypatch.setattr(
        eval_module,
        "_install_profile",
        lambda *_args, **_kwargs: {
            "commands": [],
            "installed_skills": [
                "alpha-style",
                "beta-review",
                "google-guides-index",
            ],
            "hashes_verified": True,
        },
    )
    trace = "\n".join(
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": f"sed .agents/skills/{skill}/SKILL.md",
                    "exit_code": 0,
                },
            }
        )
        for skill in ("alpha-style", "beta-review")
    )
    monkeypatch.setattr(
        eval_module,
        "_run_agent",
        lambda *_args, **_kwargs: {
            "command": ["codex", "fake"],
            "duration_seconds": 0.1,
            "exit_code": 0,
            "final_output": "EVAL_SKILL: alpha-style",
            "trace": trace,
        },
    )
    monkeypatch.setattr(eval_module, "_version", lambda _command, **_kwargs: "test")
    case = EvalCase(
        id="smoke-alpha",
        stage="smoke",
        split="validation",
        prompt="Apply alpha style.",
        expected_skills=("alpha-style",),
        forbidden_skills=(),
    )

    report, _output = run_evaluation(
        manifest,
        [case],
        mode="triggers",
        agents=["codex"],
        profile="all",
        dry_run=False,
        models={"codex": "test-model"},
        accept_credential_risk=True,
        results_root=tmp_path / "exact-routing-results",
    )

    record = report["records"][0]
    assert record["expected_loaded"] is True
    assert record["forbidden_avoided"] is False
    assert record["unexpected_loaded_skills"] == ["beta-review"]
    assert record["trigger_correct"] is False
    assert report["summary"]["direct_prompt_exact_rate"] == 0.0
    assert report["summary"]["direct_prompts_with_unexpected"] == 1
    assert report["summary"]["direct_unexpected_skill_loads"] == 1


def test_codex_claim_for_known_but_uninstalled_skill_is_not_counted(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    monkeypatch.setattr(eval_module, "_prepare_workspace", lambda path: path.mkdir(parents=True))
    monkeypatch.setattr(
        eval_module,
        "_install_profile",
        lambda *_args, **_kwargs: {
            "commands": [],
            "installed_skills": ["google-guides-index"],
            "hashes_verified": True,
        },
    )
    monkeypatch.setattr(
        eval_module,
        "_run_agent",
        lambda *_args, **_kwargs: {
            "command": ["codex", "fake"],
            "duration_seconds": 0.1,
            "exit_code": 0,
            "final_output": "EVAL_SKILL: alpha-style",
            "trace": '{"type":"turn.completed"}',
        },
    )
    monkeypatch.setattr(eval_module, "_version", lambda _command, **_kwargs: "test")

    report, _output = run_evaluation(
        manifest,
        [_case()],
        mode="triggers",
        agents=["codex"],
        profile="index",
        dry_run=False,
        models={"codex": "test-model"},
        accept_credential_risk=True,
        keep_raw=True,
        results_root=tmp_path / "proxy-results",
    )

    record = report["records"][0]
    assert record["claimed_skill"] == "alpha-style"
    assert record["observed_skills"] == []
    assert record["observation_evidence"] == "unverified-self-report"
    assert record["trigger_correct"] is False


def test_failed_agent_process_is_excluded_from_accuracy(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    monkeypatch.setattr(eval_module, "_prepare_workspace", lambda path: path.mkdir(parents=True))
    monkeypatch.setattr(
        eval_module,
        "_install_profile",
        lambda *_args, **_kwargs: {
            "commands": [],
            "installed_skills": ["alpha-style"],
            "hashes_verified": True,
        },
    )
    monkeypatch.setattr(
        eval_module,
        "_run_agent",
        lambda *_args, **_kwargs: {
            "command": ["codex", "fake"],
            "duration_seconds": 0.1,
            "exit_code": 1,
            "final_output": "EVAL_SKILL: alpha-style",
            "trace": json.dumps({"type": "turn.failed"}),
        },
    )
    monkeypatch.setattr(eval_module, "_version", lambda _command, **_kwargs: "test")

    report, _output = run_evaluation(
        manifest,
        [_case()],
        mode="triggers",
        agents=["codex"],
        profile="single",
        dry_run=False,
        models={"codex": "test-model"},
        accept_credential_risk=True,
        keep_raw=True,
        results_root=tmp_path / "failed-results",
    )

    assert report["records"][0]["status"] == "failed"
    assert report["summary"]["completed"] == 0
    assert report["summary"]["trigger_accuracy"] is None


def test_infrastructure_errors_are_checkpointed_and_do_not_abort_matrix(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    monkeypatch.setattr(
        eval_module,
        "_prepare_workspace",
        lambda _path: (_ for _ in ()).throw(EvaluationError("fixture failure")),
    )
    monkeypatch.setattr(eval_module, "_version", lambda _command, **_kwargs: "test")

    report, output = run_evaluation(
        manifest,
        [_case("first"), _case("second")],
        mode="triggers",
        agents=["codex"],
        profile="single",
        dry_run=False,
        models={"codex": "test-model"},
        accept_credential_risk=True,
        results_root=tmp_path / "checkpoint-results",
    )

    assert report["summary"]["infrastructure_errors"] == 2
    assert [record["status"] for record in report["records"]] == [
        "infrastructure-error",
        "infrastructure-error",
    ]
    lines = (output / "records.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["error"] == "fixture failure" for line in lines)


def test_quality_live_report_compares_canned_baseline_and_skilled_outputs(
    manifest: Manifest, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(eval_module, "_preflight_live", lambda _agents: None)
    monkeypatch.setattr(eval_module, "_prepare_workspace", lambda path: path.mkdir(parents=True))
    monkeypatch.setattr(
        eval_module,
        "_install_profile",
        lambda *_args, **_kwargs: {
            "commands": [],
            "installed_skills": ["alpha-style"] if _args[3] == "single" else [],
            "hashes_verified": True,
        },
    )
    run_profiles = iter((False, True))

    def run_agent(
        _agent: str,
        workspace: Path,
        _prompt: str,
        raw_dir: Path,
        **_kwargs: object,
    ) -> dict[str, object]:
        raw_dir.mkdir(parents=True)
        assert workspace.name == "w"
        skilled = next(run_profiles)
        return {
            "command": ["codex", "fake"],
            "duration_seconds": 0.1,
            "exit_code": 0,
            "final_output": (
                "Use snake_case. EVAL_SKILL: alpha-style" if skilled else "No style advice."
            ),
            "trace": (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "sed .agents/skills/alpha-style/SKILL.md",
                            "exit_code": 0,
                        },
                    }
                )
                if skilled
                else '{"type":"done"}'
            ),
        }

    monkeypatch.setattr(eval_module, "_run_agent", run_agent)
    monkeypatch.setattr(eval_module, "_version", lambda _command, **_kwargs: "test")

    report, _output = run_evaluation(
        manifest,
        [_case()],
        mode="quality",
        agents=["codex"],
        profile="single",
        models={"codex": "test-model"},
        accept_credential_risk=True,
        dry_run=False,
        keep_raw=True,
        results_root=tmp_path / "quality-live",
    )

    assert report["quality_comparisons"] == [
        {
            "agent": "codex",
            "case_id": "alpha-positive",
            "repeat": 1,
            "baseline_score": 0,
            "skilled_score": 1,
            "rubric_total": 1,
            "delta": 1,
            "baseline_forbidden_claims": 0,
            "skilled_forbidden_claims": 0,
            "fidelity_delta": 1,
        }
    ]
    baseline, skilled = report["records"]
    assert baseline["trigger_correct"] is True
    assert skilled["trigger_correct"] is True
    assert baseline["raw_path"].startswith("raw/")


def _patch_cli_eval(
    monkeypatch: pytest.MonkeyPatch,
    manifest: Manifest,
    output: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    selected: dict[str, object] = {}
    invoked: dict[str, object] = {}
    output.mkdir(parents=True)
    case = _case()
    monkeypatch.setattr(cli, "_manifest", lambda _path: manifest)
    monkeypatch.setattr(cli, "load_cases", lambda _manifest: [case])

    def select(cases: list[EvalCase], **kwargs: object) -> list[EvalCase]:
        selected.update(kwargs)
        return cases

    def run(
        _manifest: Manifest, cases: list[EvalCase], **kwargs: object
    ) -> tuple[dict[str, object], Path]:
        invoked.update(kwargs)
        assert cases == [case]
        return {"summary": {"runs": 1}}, output

    monkeypatch.setattr(cli, "select_cases", select)
    monkeypatch.setattr(cli, "run_evaluation", run)
    return selected, invoked


def test_cli_eval_defaults_to_plan_only_smoke_for_both_agents(
    manifest: Manifest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = manifest.project_root / "evals/results/plan"
    selected, invoked = _patch_cli_eval(monkeypatch, manifest, output)

    result = cli.main(["eval", "triggers", "--results-root", str(tmp_path / "requested")])

    assert result == 0
    assert selected["stages"] == ["smoke"]
    assert selected["require_rubric"] is False
    assert invoked["agents"] == ["codex", "claude-code"]
    assert invoked["profile"] == "all"
    assert invoked["dry_run"] is True
    assert invoked["models"] == {}
    assert "evals/results/plan" in capsys.readouterr().out


def test_cli_quality_defaults_to_representative_rubrics_and_passes_options(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = manifest.project_root / "evals/results/quality"
    selected, invoked = _patch_cli_eval(monkeypatch, manifest, output)

    result = cli.main(
        [
            "eval",
            "quality",
            "--agent",
            "codex",
            "--profile",
            "single",
            "--repeat",
            "3",
            "--codex-model",
            "gpt-test",
            "--keep-raw",
        ]
    )

    assert result == 0
    assert selected["stages"] == ["representative"]
    assert selected["require_rubric"] is True
    assert invoked["agents"] == ["codex"]
    assert invoked["repeat"] == 3
    assert invoked["models"] == {"codex": "gpt-test"}
    assert invoked["keep_raw"] is True
    assert invoked["dry_run"] is True


def test_cli_live_eval_requires_explicit_cost_acknowledgement(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        cli,
        "run_evaluation",
        lambda *_args, **_kwargs: pytest.fail("unacknowledged live eval must not run"),
    )

    result = cli.main(["eval", "triggers", "--live"])

    assert result == 2
    assert "Live evaluations require --accept-cost" in capsys.readouterr().err


def test_cli_live_eval_requires_credential_risk_acknowledgement(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        cli,
        "run_evaluation",
        lambda *_args, **_kwargs: pytest.fail("unacknowledged live eval must not run"),
    )

    result = cli.main(["eval", "triggers", "--live", "--accept-cost"])

    assert result == 2
    assert "--accept-credential-risk" in capsys.readouterr().err


def test_cli_cost_acknowledgement_enables_live_mode(
    manifest: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = manifest.project_root / "evals/results/live"
    _selected, invoked = _patch_cli_eval(monkeypatch, manifest, output)

    result = cli.main(
        [
            "eval",
            "triggers",
            "--agent",
            "codex",
            "--live",
            "--accept-cost",
            "--accept-credential-risk",
            "--codex-model",
            "gpt-test",
            "--max-budget-usd",
            "0.5",
        ]
    )

    assert result == 0
    assert invoked["dry_run"] is False
    assert invoked["accept_credential_risk"] is True
    assert invoked["models"] == {"codex": "gpt-test"}
    assert invoked["max_budget_usd"] == 0.5


def test_cli_live_claude_requires_explicit_soft_cap(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_manifest", lambda _path: manifest)
    monkeypatch.setattr(
        cli,
        "run_evaluation",
        lambda *_args, **_kwargs: pytest.fail("missing cap must fail before evaluation"),
    )

    result = cli.main(
        [
            "eval",
            "triggers",
            "--agent",
            "claude-code",
            "--claude-model",
            "claude-test",
            "--live",
            "--accept-cost",
            "--accept-credential-risk",
        ]
    )

    assert result == 2
    assert "explicit --max-budget-usd" in capsys.readouterr().err


def test_cli_index_ab_preflight_reports_both_profile_calls(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = manifest.project_root / "evals/results/index-ab"
    _patch_cli_eval(monkeypatch, manifest, output)

    result = cli.main(
        [
            "eval",
            "triggers",
            "--agent",
            "claude-code",
            "--profile",
            "index-ab",
            "--live",
            "--accept-cost",
            "--accept-credential-risk",
            "--claude-model",
            "claude-test",
            "--max-budget-usd",
            "0.5",
        ]
    )

    assert result == 0
    output_text = capsys.readouterr().out
    assert "Executing 2 isolated process(es)" in output_text
    assert "Claude soft-cap sum $1.00" in output_text


@pytest.mark.parametrize("failure_key", ["failed_processes", "infrastructure_errors"])
def test_cli_live_eval_returns_failure_for_nonpassing_run(
    manifest: Manifest,
    monkeypatch: pytest.MonkeyPatch,
    failure_key: str,
) -> None:
    output = manifest.project_root / "evals/results/failed-live"
    output.mkdir(parents=True)
    case = _case()
    monkeypatch.setattr(cli, "_manifest", lambda _path: manifest)
    monkeypatch.setattr(cli, "load_cases", lambda _manifest: [case])
    monkeypatch.setattr(cli, "select_cases", lambda cases, **_kwargs: cases)
    monkeypatch.setattr(
        cli,
        "run_evaluation",
        lambda *_args, **_kwargs: (
            {
                "summary": {
                    "runs": 1,
                    "failed_processes": int(failure_key == "failed_processes"),
                    "infrastructure_errors": int(failure_key == "infrastructure_errors"),
                }
            },
            output,
        ),
    )

    result = cli.main(
        [
            "eval",
            "triggers",
            "--agent",
            "codex",
            "--live",
            "--accept-cost",
            "--accept-credential-risk",
            "--codex-model",
            "gpt-test",
        ]
    )

    assert result == 1
