"""Public non-evaluation CLI routing tests with all external work mocked."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from google_guide_skills import cli
from google_guide_skills.errors import ManifestError
from google_guide_skills.models import ValidationIssue


@pytest.fixture
def fake_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    value = SimpleNamespace(project_root=tmp_path)
    monkeypatch.setattr(cli, "_manifest", lambda _path: value)
    return value


def test_build_and_all_forward_include_local(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_calls: list[dict[str, object]] = []
    metric_calls: list[bool] = []
    sync_calls: list[object] = []
    built = SimpleNamespace(
        distribution="local-only",
        path=tmp_path / ".generated" / "skills" / "fixture",
    )
    monkeypatch.setattr(
        cli,
        "build",
        lambda _manifest, **kwargs: build_calls.append(kwargs) or [built],
    )
    monkeypatch.setattr(
        cli,
        "sync",
        lambda manifest, ids=None: sync_calls.append((manifest, ids)) or [],
    )
    monkeypatch.setattr(cli, "write_catalog", lambda _manifest: ())
    monkeypatch.setattr(cli, "assert_canonical_runtime", lambda _manifest: "3.13.7")
    monkeypatch.setattr(
        cli,
        "write_metrics",
        lambda _manifest, include_local=False: metric_calls.append(include_local) or (),
    )
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])

    assert cli.main(["build", "--include-swe-book", "--no-sync"]) == 0
    assert build_calls[-1]["include_local"] is True
    assert build_calls[-1]["sync_first"] is False
    assert metric_calls == [False, True]

    metric_calls.clear()
    assert cli.main(["all", "--include-swe-book"]) == 0
    assert sync_calls[-1][0] is fake_manifest
    assert build_calls[-1]["include_local"] is True
    assert build_calls[-1]["sync_first"] is False
    assert metric_calls == [False, True]


def test_validate_failure_exit_and_json_output(
    fake_manifest: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    issue = ValidationIssue("error", "skills/bad", "broken")
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [issue])

    assert cli.main(["validate", "--json"]) == 1
    assert '"message": "broken"' in capsys.readouterr().out


def test_install_uses_default_agents_for_project_install(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_install(manifest: object, project: Path, agents: list[str], **kwargs: object):
        captured.update(manifest=manifest, project=project, agents=agents, **kwargs)
        return [["npx", "--yes", "skills@1.5.23", "add", "skills"]]

    monkeypatch.setattr(cli, "install", fake_install)
    assert cli.main(["install", "--project", str(tmp_path), "--dry-run"]) == 0
    assert captured["manifest"] is fake_manifest
    assert captured["agents"] == ["codex", "claude-code"]
    assert captured["include_local"] is False
    assert captured["dry_run"] is True
    assert "skills@1.5.23" in capsys.readouterr().out


def test_self_install_routes_local_skills_to_user_links(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    action = SimpleNamespace(
        status="would-link",
        destination=tmp_path / ".codex/skills/restricted-guide",
        source=tmp_path / ".generated/skills/restricted-guide",
        distribution="local-only",
    )
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])

    def fake_user_install(
        manifest: object, agents: list[str], **kwargs: object
    ) -> list[SimpleNamespace]:
        captured.update(manifest=manifest, agents=agents, **kwargs)
        return [action]

    monkeypatch.setattr(cli, "install_user_links", fake_user_install)

    assert (
        cli.main(
            [
                "install",
                "--include-swe-book",
                "--agent",
                "codex",
                "--dry-run",
            ]
        )
        == 0
    )
    assert captured == {
        "manifest": fake_manifest,
        "agents": ["codex"],
        "skills": None,
        "include_local": True,
        "dry_run": True,
    }
    assert "[local-only]" in capsys.readouterr().out


def test_swe_book_install_rejects_copy_and_project_destinations(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])

    assert cli.main(["install", "--copy", "--dry-run"]) == 2
    assert (
        cli.main(
            ["install", "--include-swe-book", "--project", str(tmp_path), "--dry-run"]
        )
        == 2
    )


def test_swe_book_install_generates_before_linking(
    fake_manifest: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        cli,
        "build",
        lambda manifest, **kwargs: calls.append(("build", (manifest, kwargs))) or [1] * 8,
    )
    monkeypatch.setattr(
        cli,
        "write_metrics",
        lambda manifest, include_local=False: calls.append(
            ("metrics", (manifest, include_local))
        )
        or (),
    )
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])
    monkeypatch.setattr(
        cli,
        "install_user_links",
        lambda manifest, agents, **kwargs: calls.append(
            ("install", (manifest, agents, kwargs))
        )
        or [],
    )

    assert cli.main(["install", "--include-swe-book", "--agent", "codex"]) == 0
    assert [name for name, _value in calls] == ["build", "metrics", "install"]
    build_call = calls[0][1]
    assert isinstance(build_call, tuple)
    assert build_call[1] == {
        "collection_ids": ["software-engineering-at-google"],
        "include_local": True,
    }


def test_sync_catalog_metrics_and_handled_manifest_failure(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "catalog" / "catalog.json"
    output.parent.mkdir()
    monkeypatch.setattr(cli, "sync", lambda _manifest, _ids: [tmp_path / ".cache" / "source"])
    monkeypatch.setattr(cli, "write_catalog", lambda _manifest: (output,))
    monkeypatch.setattr(
        cli,
        "write_metrics",
        lambda _manifest, include_local=False: (output,),
    )

    assert cli.main(["sync"]) == 0
    assert cli.main(["catalog"]) == 0
    assert cli.main(["metrics", "--include-swe-book"]) == 0

    monkeypatch.setattr(cli, "_manifest", lambda _path: (_ for _ in ()).throw(ManifestError("bad")))
    assert cli.main(["catalog"]) == 2
