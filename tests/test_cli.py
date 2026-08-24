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
    committed = SimpleNamespace(distribution="committed")
    local = SimpleNamespace(distribution="local-only")

    def artifacts(include_local: bool) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        values = [(committed, SimpleNamespace(name="public-guide"))]
        if include_local:
            values.append((local, SimpleNamespace(name="restricted-guide")))
        return values

    value = SimpleNamespace(
        project_root=tmp_path,
        collections={cli.SWE_BOOK_COLLECTION_ID: local},
        artifacts=artifacts,
        license_for=lambda _collection: SimpleNamespace(
            name="Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International",
            spdx="CC-BY-NC-ND-4.0",
            url="https://creativecommons.org/licenses/by-nc-nd/4.0/",
            warning=None,
        ),
    )
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

    def fake_install(
        manifest: object,
        project: Path,
        agents: list[str],
        skills: list[str] | None = None,
        copy: bool = False,
        dry_run: bool = False,
    ) -> list[list[str]]:
        captured.update(
            manifest=manifest,
            project=project,
            agents=agents,
            skills=skills,
            copy=copy,
            dry_run=dry_run,
        )
        return [["npx", "--yes", "skills@1.5.23", "add", "skills"]]

    monkeypatch.setattr(cli, "install", fake_install)
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])
    assert cli.main(["install", "--project", str(tmp_path), "--dry-run"]) == 0
    assert captured["manifest"] is fake_manifest
    assert captured["agents"] == ["codex", "claude-code"]
    assert captured["skills"] == ["public-guide"]
    assert captured["copy"] is False
    assert captured["dry_run"] is True
    assert "skills@1.5.23" in capsys.readouterr().out


def test_user_install_routes_swe_book_skills_to_links(
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

    def fake_link_install(
        manifest: object,
        agents: list[str],
        skills: list[str] | None = None,
        *,
        include_local: bool = False,
        dry_run: bool = False,
        project: Path | None = None,
    ) -> list[SimpleNamespace]:
        captured.update(
            manifest=manifest,
            agents=agents,
            skills=skills,
            include_local=include_local,
            dry_run=dry_run,
            project=project,
        )
        return [action]

    monkeypatch.setattr(cli, "install_links", fake_link_install)

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
        "skills": ["public-guide", "restricted-guide"],
        "include_local": True,
        "dry_run": True,
        "project": None,
    }
    assert "[SWE-book]" in capsys.readouterr().out


def test_user_install_rejects_copy(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])

    assert cli.main(["install", "--copy", "--dry-run"]) == 2


def test_project_install_rejects_missing_target_before_generation(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "build",
        lambda *_args, **_kwargs: pytest.fail("build must follow project validation"),
    )

    assert (
        cli.main(
            [
                "install",
                "--project",
                str(tmp_path / "missing"),
                "--include-swe-book",
                "--accept-swe-book-license",
            ]
        )
        == 2
    )
    assert "Install project does not exist" in capsys.readouterr().err


def test_project_install_routes_swe_book_skills_to_links(
    fake_manifest: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_links: dict[str, object] = {}
    captured_public: dict[str, object] = {}
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])

    def fake_public_install(
        manifest: object,
        project: Path,
        agents: list[str],
        **kwargs: object,
    ) -> list[list[str]]:
        captured_public.update(
            manifest=manifest,
            project=project,
            agents=agents,
            **kwargs,
        )
        return []

    monkeypatch.setattr(cli, "install", fake_public_install)

    def fake_link_install(
        manifest: object,
        agents: list[str],
        skills: list[str] | None = None,
        **kwargs: object,
    ) -> list[object]:
        captured_links.update(manifest=manifest, agents=agents, skills=skills, **kwargs)
        return []

    monkeypatch.setattr(cli, "install_links", fake_link_install)

    assert (
        cli.main(
            [
                "install",
                "--project",
                str(tmp_path),
                "--include-swe-book",
                "--copy",
                "--dry-run",
            ]
        )
        == 0
    )
    assert captured_public["skills"] == ["public-guide"]
    assert captured_public["copy"] is True
    assert captured_links["project"] == tmp_path
    assert captured_links["skills"] == ["restricted-guide"]
    assert captured_links["include_local"] is True


def test_swe_book_install_generates_before_linking(
    fake_manifest: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        cli,
        "build",
        lambda manifest, **kwargs: calls.append(("build", (manifest, kwargs))) or [1],
    )
    monkeypatch.setattr(
        cli,
        "write_metrics",
        lambda manifest, include_local=False: (
            calls.append(("metrics", (manifest, include_local))) or ()
        ),
    )
    monkeypatch.setattr(cli, "validate", lambda _manifest, include_local=False: [])
    monkeypatch.setattr(
        cli,
        "install_links",
        lambda manifest, agents, **kwargs: (
            calls.append(("install", (manifest, agents, kwargs))) or []
        ),
    )

    assert (
        cli.main(
            [
                "install",
                "--include-swe-book",
                "--accept-swe-book-license",
                "--agent",
                "codex",
            ]
        )
        == 0
    )
    assert [name for name, _value in calls] == ["build", "metrics", "install"]
    build_call = calls[0][1]
    assert isinstance(build_call, tuple)
    assert build_call[1] == {
        "collection_ids": [cli.SWE_BOOK_COLLECTION_ID],
        "include_local": True,
    }


def test_selected_swe_book_install_builds_collection_and_links_selection(
    fake_manifest: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    committed = SimpleNamespace(distribution="committed")
    local = fake_manifest.collections[cli.SWE_BOOK_COLLECTION_ID]
    local_names = {"restricted-guide", "unselected-restricted-guide"}
    built: set[str] = set()
    linked: list[str] = []

    def artifacts(include_local: bool) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        values = [(committed, SimpleNamespace(name="public-guide"))]
        if include_local:
            values.extend((local, SimpleNamespace(name=name)) for name in sorted(local_names))
        return values

    fake_manifest.artifacts = artifacts

    def fake_build(
        _manifest: object,
        *,
        collection_ids: list[str],
        include_local: bool,
        artifact_names: list[str] | None = None,
    ) -> list[object]:
        del collection_ids, include_local
        built.update(local_names if artifact_names is None else artifact_names)
        return [object() for _name in built]

    def fake_validate(
        _manifest: object,
        include_local: bool = False,
    ) -> list[ValidationIssue]:
        missing = local_names - built if include_local else set()
        return [
            ValidationIssue("error", f".generated/skills/{name}", "Skill not built")
            for name in sorted(missing)
        ]

    monkeypatch.setattr(cli, "build", fake_build)
    monkeypatch.setattr(cli, "write_metrics", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(cli, "validate", fake_validate)
    monkeypatch.setattr(
        cli,
        "install_links",
        lambda _manifest, _agents, skills=None, **_kwargs: linked.extend(skills or []) or [],
    )

    assert (
        cli.main(
            [
                "install",
                "--include-swe-book",
                "--accept-swe-book-license",
                "--skill",
                "restricted-guide",
                "--agent",
                "codex",
            ]
        )
        == 0
    )
    assert built == local_names
    assert linked == ["restricted-guide"]


def test_swe_book_install_requires_license_acceptance_before_building(
    fake_manifest: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli,
        "build",
        lambda *_args, **_kwargs: pytest.fail("build must follow license acceptance"),
    )

    assert cli.main(["install", "--include-swe-book", "--agent", "codex"]) == 2
    error = capsys.readouterr().err
    assert "requires license acceptance" in error
    assert "--accept-swe-book-license" in error


def test_swe_book_skill_selection_requires_include_flag(
    fake_manifest: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["install", "--skill", "restricted-guide", "--dry-run"]) == 2
    assert "require --include-swe-book" in capsys.readouterr().err


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
