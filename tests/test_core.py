"""Hermetic tests for the generator's non-evaluation core."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import platform
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from google_guide_skills import builder, catalog, installer, manifest, metrics, sources, validation
from google_guide_skills.convert import markup_to_markdown, source_to_markdown
from google_guide_skills.errors import (
    BuildError,
    GoogleGuideSkillsError,
    ManifestError,
    SourceError,
)
from google_guide_skills.models import Artifact, Manifest, SourcePathPolicy


def _license(
    *,
    spdx: str = "CC-BY-4.0",
    evidence_path: str | None = "LICENSE",
    evidence_glob: str | None = None,
    evidence_contains: str | None = None,
    warning: str | None = None,
) -> dict[str, str]:
    result = {
        "spdx": spdx,
        "name": spdx,
        "url": f"https://example.test/licenses/{spdx}",
        "attribution": "Example Authors",
        "audited": "2026-08-22",
        "allow_committed_output": spdx != "CC-BY-NC-ND-4.0",
    }
    if evidence_path is not None:
        result["evidence_path"] = evidence_path
    if evidence_glob is not None:
        result["evidence_glob"] = evidence_glob
    if evidence_contains is not None:
        result["evidence_contains"] = evidence_contains
    if warning is not None:
        result["warning"] = warning
    return result


def _manifest_data(revision: str = "a" * 40) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generator": {"python": platform.python_version()},
        "generated_roots": {
            "committed": "skills",
            "local_only": ".generated/skills",
        },
        "repositories": {
            "example-repo": {
                "url": "https://example.test/example-repo.git",
                "revision": revision,
                "default_branch": "main",
                "license": _license(),
            }
        },
        "collections": {
            "public-guides": {
                "repository": "example-repo",
                "distribution": "committed",
                "description": "Redistributable guide fixtures.",
                "artifacts": [
                    {
                        "name": "public-guide",
                        "title": "Public Guide",
                        "description": "Use when applying the public guide.",
                        "tags": ["public", "style"],
                        "layout": "inline",
                        "inputs": ["guide.md"],
                    }
                ],
            },
            "restricted-guides": {
                "repository": "example-repo",
                "distribution": "local-only",
                "description": "Restricted local fixtures.",
                "license_override": _license(
                    spdx="CC-BY-NC-ND-4.0",
                    evidence_path=None,
                    evidence_glob="restricted/*.html",
                    evidence_contains="CC BY-NC-ND 4.0",
                    warning="Do not redistribute generated output.",
                ),
                "artifacts": [
                    {
                        "name": "restricted-guide",
                        "title": "Restricted Guide",
                        "description": "Use privately when consulting the restricted guide.",
                        "tags": ["restricted"],
                        "layout": "references",
                        "inputs": ["restricted/*.html"],
                    }
                ],
            },
        },
        "catalog_only": [
            {
                "id": "web-only-guide",
                "title": "Web-only Guide",
                "url": "https://example.test/web-guide",
                "license": "CC-BY-4.0",
                "status": "snapshot-pending",
                "reason": "A reproducible snapshot has not been implemented.",
                "tags": ["web"],
            }
        ],
    }


def _write_manifest(project: Path, data: dict[str, object]) -> Manifest:
    project.mkdir(parents=True, exist_ok=True)
    (project / "LICENSE").write_bytes(
        (Path(__file__).parents[1] / "LICENSE").read_bytes()
    )
    path = project / "corpus.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return manifest.load_manifest(path)


def _git(path: Path, *args: str) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            "user.email=tests@example.test",
            "-c",
            "user.name=Test Author",
            *args,
        ],
        cwd=path,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _init_git(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--quiet")


@pytest.fixture
def built_project(tmp_path: Path) -> tuple[Manifest, Path]:
    checkout = tmp_path / ".cache" / "sources" / "example-repo"
    _init_git(checkout)
    (checkout / "LICENSE").write_text("Example license text\n", encoding="utf-8")
    (checkout / "guide.md").write_text("# Upstream\n\nKeep this text verbatim.\n", encoding="utf-8")
    restricted = checkout / "restricted"
    restricted.mkdir()
    (restricted / "chapter.html").write_text(
        "<!-- CC BY-NC-ND 4.0 --><main><h1>Chapter</h1><p>Private text.</p></main>",
        encoding="utf-8",
    )
    collision_dir = checkout / "a"
    collision_dir.mkdir()
    (collision_dir / "b.md").write_text("nested\n", encoding="utf-8")
    (checkout / "a--b.md").write_text("flat\n", encoding="utf-8")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "--quiet", "-m", "fixture")
    _git(checkout, "remote", "add", "origin", "https://example.test/example-repo.git")
    revision = _git(checkout, "rev-parse", "HEAD")
    loaded = _write_manifest(tmp_path, _manifest_data(revision))
    return loaded, checkout


@pytest.fixture
def generated_project(built_project: tuple[Manifest, Path]) -> Manifest:
    loaded, _checkout = built_project
    (loaded.project_root / ".gitignore").write_text(".cache/\n.generated/\n", encoding="utf-8")
    _init_git(loaded.project_root)
    builder.build(loaded, include_local=True, sync_first=False)
    catalog.write_catalog(loaded)
    return loaded


class _WordEncoding:
    def encode(self, text: str) -> list[str]:
        return text.split()


def test_find_project_root_walks_parents_and_rejects_missing(tmp_path: Path) -> None:
    (tmp_path / "corpus.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    nested = tmp_path / "one" / "two"
    nested.mkdir(parents=True)

    assert manifest.find_project_root(nested) == tmp_path
    with pytest.raises(ManifestError, match="Could not find corpus.yaml"):
        manifest.find_project_root(tmp_path.parent / "definitely-not-a-project")


def test_load_manifest_builds_typed_model_and_resolves_policy_roots(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path, _manifest_data())

    assert loaded.schema_version == 1
    assert loaded.root_for("committed") == tmp_path / "skills"
    assert loaded.root_for("local-only") == tmp_path / ".generated" / "skills"
    assert [artifact.name for _, artifact in loaded.artifacts(include_local=False)] == [
        "public-guide"
    ]
    assert {artifact.name for _, artifact in loaded.artifacts()} == {
        "public-guide",
    }
    assert {artifact.name for _, artifact in loaded.artifacts(include_local=True)} == {
        "public-guide",
        "restricted-guide",
    }
    with pytest.raises(ManifestError, match="Unknown distribution"):
        loaded.root_for("commited")
    restricted = loaded.collections["restricted-guides"]
    assert loaded.license_for(restricted).spdx == "CC-BY-NC-ND-4.0"
    assert loaded.repositories["example-repo"].license.to_dict()["evidence_path"] == "LICENSE"


@pytest.mark.parametrize(
    ("root", "message"),
    [
        ("/absolute", "unsafe path"),
        ("../outside", "unsafe path"),
        ("~/elsewhere", "unsafe path"),
    ],
)
def test_manifest_rejects_unsafe_generated_roots(tmp_path: Path, root: str, message: str) -> None:
    data = _manifest_data()
    data["generated_roots"]["committed"] = root  # type: ignore[index]

    with pytest.raises(ManifestError, match=message):
        _write_manifest(tmp_path, data)


def test_manifest_rejects_unsafe_inputs_and_equal_roots(tmp_path: Path) -> None:
    unsafe = _manifest_data()
    unsafe["collections"]["public-guides"]["artifacts"][0]["inputs"] = ["../secret"]  # type: ignore[index]
    with pytest.raises(ManifestError, match="unsafe path"):
        _write_manifest(tmp_path / "unsafe", unsafe)

    equal = _manifest_data()
    equal["generated_roots"]["local_only"] = "skills"  # type: ignore[index]
    with pytest.raises(ManifestError, match="must differ"):
        _write_manifest(tmp_path / "equal", equal)

    alternate = _manifest_data()
    alternate["generated_roots"]["local_only"] = "private-skills"  # type: ignore[index]
    with pytest.raises(ManifestError, match="fixed security boundary"):
        _write_manifest(tmp_path / "alternate", alternate)


def test_manifest_rejects_unsafe_license_evidence_paths(tmp_path: Path) -> None:
    for field in ("evidence_path", "evidence_glob"):
        data = _manifest_data()
        data["repositories"]["example-repo"]["license"][field] = "../secret"  # type: ignore[index]
        with pytest.raises(ManifestError, match="unsafe path"):
            _write_manifest(tmp_path / field, data)


def test_manifest_requires_concrete_license_evidence(tmp_path: Path) -> None:
    missing = _manifest_data()
    license_data = missing["repositories"]["example-repo"]["license"]  # type: ignore[index]
    del license_data["evidence_path"]  # type: ignore[index]
    with pytest.raises(ManifestError, match="evidence_path or evidence_glob"):
        _write_manifest(tmp_path / "missing", missing)

    orphaned = _manifest_data()
    license_data = orphaned["repositories"]["example-repo"]["license"]  # type: ignore[index]
    license_data["evidence_contains"] = "notice"  # type: ignore[index]
    with pytest.raises(ManifestError, match="requires evidence_glob"):
        _write_manifest(tmp_path / "orphaned", orphaned)


def test_manifest_normalizes_nested_mapping_errors(tmp_path: Path) -> None:
    for key, value in (
        ("generated_roots", []),
        ("repositories", []),
        ("collections", []),
    ):
        data = _manifest_data()
        data[key] = value
        with pytest.raises(ManifestError, match="must be a mapping"):
            _write_manifest(tmp_path / key, data)


def test_manifest_rejects_invalid_schema_revision_and_repository_reference(tmp_path: Path) -> None:
    bad_schema = _manifest_data()
    bad_schema["schema_version"] = 2
    with pytest.raises(ManifestError, match="Unsupported schema_version"):
        _write_manifest(tmp_path / "schema", bad_schema)

    floating_runtime = _manifest_data()
    floating_runtime["generator"]["python"] = "3.13"  # type: ignore[index]
    with pytest.raises(ManifestError, match="exact Python 3 version"):
        _write_manifest(tmp_path / "runtime", floating_runtime)

    bad_revision = _manifest_data(revision="short")
    with pytest.raises(ManifestError, match="full 40-character"):
        _write_manifest(tmp_path / "revision", bad_revision)

    unknown_repo = _manifest_data()
    unknown_repo["collections"]["public-guides"]["repository"] = "missing"  # type: ignore[index]
    with pytest.raises(ManifestError, match="unknown repository"):
        _write_manifest(tmp_path / "unknown", unknown_repo)


def test_manifest_rejects_duplicate_skills_and_invalid_agent_skill_fields(tmp_path: Path) -> None:
    duplicate = _manifest_data()
    duplicate["collections"]["restricted-guides"]["artifacts"][0]["name"] = "public-guide"  # type: ignore[index]
    with pytest.raises(ManifestError, match="Duplicate skill name"):
        _write_manifest(tmp_path / "duplicate", duplicate)

    bad_name = _manifest_data()
    bad_name["collections"]["public-guides"]["artifacts"][0]["name"] = "Bad_Name"  # type: ignore[index]
    with pytest.raises(ManifestError, match="naming rules"):
        _write_manifest(tmp_path / "name", bad_name)

    long_description = _manifest_data()
    long_description["collections"]["public-guides"]["artifacts"][0]["description"] = (  # type: ignore[index]
        "x" * 1025
    )
    with pytest.raises(ManifestError, match="exceeds 1024"):
        _write_manifest(tmp_path / "description", long_description)


def test_manifest_rejects_invalid_distribution_layout_and_local_license(tmp_path: Path) -> None:
    bad_distribution = _manifest_data()
    bad_distribution["collections"]["public-guides"]["distribution"] = "private"  # type: ignore[index]
    with pytest.raises(ManifestError, match="distribution"):
        _write_manifest(tmp_path / "distribution", bad_distribution)

    bad_layout = _manifest_data()
    bad_layout["collections"]["public-guides"]["artifacts"][0]["layout"] = "split"  # type: ignore[index]
    with pytest.raises(ManifestError, match="layout"):
        _write_manifest(tmp_path / "layout", bad_layout)

    missing_override = _manifest_data()
    del missing_override["collections"]["restricted-guides"]["license_override"]  # type: ignore[index]
    with pytest.raises(ManifestError, match="no explicit license_override"):
        _write_manifest(tmp_path / "override", missing_override)

    restricted_commit = _manifest_data()
    restricted_commit["collections"]["restricted-guides"]["distribution"] = "committed"  # type: ignore[index]
    with pytest.raises(ManifestError, match="cannot use committed distribution"):
        _write_manifest(tmp_path / "restricted-commit", restricted_commit)


def test_manifest_wraps_yaml_and_mapping_errors(tmp_path: Path) -> None:
    invalid_yaml = tmp_path / "invalid.yaml"
    invalid_yaml.write_text("schema_version: [\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="Invalid YAML"):
        manifest.load_manifest(invalid_yaml)

    non_mapping = tmp_path / "list.yaml"
    non_mapping.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="corpus must be a mapping"):
        manifest.load_manifest(non_mapping)

    duplicate = tmp_path / "duplicate.yaml"
    duplicate.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="Duplicate YAML mapping key"):
        manifest.load_manifest(duplicate)

    unhashable = tmp_path / "unhashable.yaml"
    unhashable.write_text("? [a, b]\n: c\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="hashable scalars"):
        manifest.load_manifest(unhashable)


def test_manifest_rejects_aliases_for_protected_repository_urls(tmp_path: Path) -> None:
    data = _manifest_data()
    repository = data["repositories"].pop("example-repo")  # type: ignore[union-attr]
    repository["url"] = "https://github.com/abseil/abseil.github.io"  # type: ignore[index]
    data["repositories"]["abseil"] = repository  # type: ignore[index]
    for collection in data["collections"].values():  # type: ignore[union-attr]
        collection["repository"] = "abseil"

    with pytest.raises(ManifestError, match="canonical protected source"):
        _write_manifest(tmp_path, data)

    alternate_id = _manifest_data()
    repository = alternate_id["repositories"].pop("example-repo")  # type: ignore[union-attr]
    repository["url"] = "https://github.com/abseil/abseil.github.io"  # type: ignore[index]
    alternate_id["repositories"]["abseil-copy"] = repository  # type: ignore[index]
    for collection in alternate_id["collections"].values():  # type: ignore[union-attr]
        collection["repository"] = "abseil-copy"

    with pytest.raises(ManifestError, match="under repository id 'abseil'"):
        _write_manifest(tmp_path / "alternate-id", alternate_id)


def test_source_to_markdown_preserves_markdown_and_adds_final_newline(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    path.write_text("# Heading\n\nExact prose.", encoding="utf-8")

    converted, mode = source_to_markdown(path)

    assert converted == "# Heading\n\nExact prose.\n"
    assert mode == "identity"


def test_markup_to_markdown_selects_main_and_removes_noncontent() -> None:
    html = """
    <html><body><nav>Navigation</nav><main><h1>Title</h1><p>A&nbsp;B</p>
    <script>danger()</script><style>.x { color: red }</style><noscript>fallback</noscript>
    </main></body></html>
    """

    converted = markup_to_markdown(html)

    assert converted.startswith("# Title")
    assert "A B" in converted
    assert "Navigation" not in converted
    assert "danger" not in converted
    assert "color: red" not in converted
    assert converted.endswith("\n")


def test_source_to_markdown_uses_xml_mode(tmp_path: Path) -> None:
    path = tmp_path / "guide.xml"
    path.write_text("<document><h1>XML Title</h1><p>Text</p></document>", encoding="utf-8")

    converted, mode = source_to_markdown(path)

    assert mode == "xml-to-markdown"
    assert "# XML Title" in converted
    assert "Text" in converted


def test_build_skill_writes_content_license_and_exact_provenance(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, checkout = built_project
    collection = loaded.collections["public-guides"]
    artifact = collection.artifacts[0]

    result = builder.build_skill(loaded, collection, artifact)

    assert result.path == loaded.project_root / "skills" / "public-guide"
    assert result.source_files == ("guide.md",)
    skill_text = (result.path / "SKILL.md").read_text(encoding="utf-8")
    assert "name: public-guide" in skill_text
    assert "Keep this text verbatim." in skill_text
    assert "[source metadata](references/source.json)" in skill_text
    license_text = (result.path / "references" / "LICENSE.txt").read_text(encoding="utf-8")
    assert "Example license text" in license_text
    provenance = json.loads(
        (result.path / "references" / "source.json").read_text(encoding="utf-8")
    )
    assert provenance["distribution"] == "committed"
    assert provenance["repository"]["revision"] == _git(checkout, "rev-parse", "HEAD")
    assert provenance["inputs"] == [
        {
            "conversion": "identity",
            "path": "guide.md",
            "sha256": hashlib.sha256((checkout / "guide.md").read_bytes()).hexdigest(),
        }
    ]
    assert provenance["generator_runtime"]["python"] == loaded.canonical_python
    assert provenance["wrapper_license"]["spdx"] == "Apache-2.0"
    wrapper = result.path / provenance["wrapper_license"]["path"]
    assert hashlib.sha256(wrapper.read_bytes()).hexdigest() == provenance[
        "wrapper_license"
    ]["sha256"]


def test_build_skill_keeps_restricted_material_in_local_root(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    collection = loaded.collections["restricted-guides"]

    result = builder.build_skill(loaded, collection, collection.artifacts[0])

    assert result.distribution == "local-only"
    assert result.path == loaded.project_root / ".generated" / "skills" / "restricted-guide"
    assert not (loaded.project_root / "skills" / "restricted-guide").exists()
    skill_text = (result.path / "SKILL.md").read_text(encoding="utf-8")
    assert "[restricted/chapter.html](references/restricted--chapter.md)" in skill_text
    reference = result.path / "references" / "restricted--chapter.md"
    assert "Private text." in reference.read_text(encoding="utf-8")
    license_text = (result.path / "references" / "LICENSE.txt").read_text(encoding="utf-8")
    assert "WARNING: Do not redistribute generated output." in license_text

    committed = replace(collection, distribution="committed")
    with pytest.raises(BuildError, match="forbids committed generated output"):
        builder.build_skill(loaded, committed, committed.artifacts[0])


@pytest.mark.parametrize("missing_name", ["source.json", "LICENSE.txt"])
def test_validation_requires_generated_provenance_and_license(
    generated_project: Manifest, missing_name: str
) -> None:
    missing = generated_project.root_for("committed") / "public-guide" / "references" / missing_name
    missing.unlink()

    issues = validation.validate(generated_project)

    assert any(issue.severity == "error" and issue.path.endswith(missing_name) for issue in issues)


def test_build_skill_is_deterministic_and_protects_unmanaged_directories(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    collection = loaded.collections["public-guides"]
    artifact = collection.artifacts[0]
    first = builder.build_skill(loaded, collection, artifact)
    snapshot = {
        path.relative_to(first.path).as_posix(): path.read_bytes()
        for path in first.path.rglob("*")
        if path.is_file()
    }

    second = builder.build_skill(loaded, collection, artifact)
    assert snapshot == {
        path.relative_to(second.path).as_posix(): path.read_bytes()
        for path in second.path.rglob("*")
        if path.is_file()
    }

    shutil.rmtree(second.path)
    second.path.mkdir(parents=True)
    (second.path / "personal.txt").write_text("do not overwrite\n", encoding="utf-8")
    with pytest.raises(BuildError, match="unrecognized directory"):
        builder.build_skill(loaded, collection, artifact)
    assert (second.path / "personal.txt").read_text(encoding="utf-8") == "do not overwrite\n"


def test_build_fails_closed_when_license_evidence_disappears(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, checkout = built_project
    (checkout / "LICENSE").unlink()

    collection = loaded.collections["public-guides"]
    with pytest.raises(BuildError, match="[Mm]issing license evidence"):
        builder.build_skill(loaded, collection, collection.artifacts[0])


def test_build_fails_closed_when_file_level_notice_disappears(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, checkout = built_project
    (checkout / "restricted" / "chapter.html").write_text(
        "<main><p>The notice is gone.</p></main>", encoding="utf-8"
    )

    collection = loaded.collections["restricted-guides"]
    with pytest.raises(BuildError, match="differs from the pinned revision"):
        builder.build_skill(loaded, collection, collection.artifacts[0])


def test_build_rejects_dirty_inputs_and_escaping_license_symlinks(
    built_project: tuple[Manifest, Path], tmp_path: Path
) -> None:
    loaded, checkout = built_project
    collection = loaded.collections["public-guides"]
    (checkout / "guide.md").write_text("dirty local text\n", encoding="utf-8")
    with pytest.raises(BuildError, match="differs from the pinned revision"):
        builder.build_skill(loaded, collection, collection.artifacts[0])

    _git(checkout, "restore", "guide.md")
    (checkout / "LICENSE").unlink()
    outside = tmp_path / "outside-license"
    outside.write_text("host secret\n", encoding="utf-8")
    (checkout / "LICENSE").symlink_to(outside)
    with pytest.raises(BuildError, match="escapes the pinned checkout"):
        builder.build_skill(loaded, collection, collection.artifacts[0])


def test_build_rejects_a_symlinked_source_checkout(
    built_project: tuple[Manifest, Path], tmp_path: Path
) -> None:
    loaded, checkout = built_project
    outside = tmp_path / "outside-checkout"
    checkout.rename(outside)
    checkout.symlink_to(outside, target_is_directory=True)
    collection = loaded.collections["public-guides"]

    with pytest.raises(BuildError, match="Source checkout may not contain symlinks"):
        builder.build_skill(loaded, collection, collection.artifacts[0])


def test_build_enforces_source_path_distribution_policies(
    built_project: tuple[Manifest, Path]
) -> None:
    loaded, checkout = built_project
    guarded = replace(
        loaded,
        source_path_policies=(
            SourcePathPolicy(
                repository="example-repo",
                pattern="restricted/**",
                required_distribution="local-only",
                reason="Restricted fixture",
            ),
        ),
    )
    public = guarded.collections["public-guides"]
    moved = replace(public.artifacts[0], inputs=("restricted/chapter.html",))
    with pytest.raises(BuildError, match="requires local-only output"):
        builder.build_skill(guarded, public, moved)

    catalog_only = replace(
        guarded,
        source_path_policies=(
            SourcePathPolicy(
                repository="example-repo",
                pattern="restricted/chapter.html",
                required_distribution="catalog-only",
                reason="Composite license fixture",
            ),
        ),
    )
    with pytest.raises(BuildError, match="catalog-only"):
        builder.build_skill(catalog_only, public, moved)

    protected = checkout / "resources" / "swe-book" / "html"
    protected.mkdir(parents=True)
    (protected / "ch01.html").write_text("<main>restricted</main>\n", encoding="utf-8")
    (checkout / "Rguide.md").write_text("# Composite license\n", encoding="utf-8")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "--quiet", "-m", "add protected-path fixtures")
    revision = _git(checkout, "rev-parse", "HEAD")
    repository = replace(loaded.repositories["example-repo"], revision=revision)
    unconfigured = replace(
        loaded,
        repositories={"example-repo": repository},
        source_path_policies=(),
    )
    with pytest.raises(BuildError, match="requires local-only output"):
        builder.build_skill(
            unconfigured,
            public,
            replace(public.artifacts[0], inputs=("resources/swe-book/html/ch01.html",)),
        )
    with pytest.raises(BuildError, match="catalog-only"):
        builder.build_skill(
            unconfigured,
            public,
            replace(public.artifacts[0], inputs=("Rguide.md",)),
        )


def test_build_rejects_wrong_revision_missing_input_and_reference_collision(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    collection = loaded.collections["public-guides"]
    wrong_repo = replace(loaded.repositories["example-repo"], revision="b" * 40)
    wrong_manifest = replace(
        loaded, repositories={**loaded.repositories, "example-repo": wrong_repo}
    )
    with pytest.raises(BuildError, match="expected pinned"):
        builder.build_skill(wrong_manifest, collection, collection.artifacts[0])

    missing = replace(collection.artifacts[0], inputs=("does-not-exist.md",))
    with pytest.raises(BuildError, match="matched no files"):
        builder.build_skill(loaded, collection, missing)

    collision = Artifact(
        name="collision-guide",
        title="Collision Guide",
        description="Use to test reference collisions.",
        tags=(),
        layout="references",
        inputs=("a/b.md", "a--b.md"),
    )
    with pytest.raises(BuildError, match="reference filename collision"):
        builder.build_skill(loaded, collection, collision)


def test_build_selection_enforces_distribution_and_routes_sync(
    built_project: tuple[Manifest, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded, _checkout = built_project
    synced: list[list[str]] = []
    monkeypatch.setattr(builder, "sync", lambda _manifest, ids: synced.append(ids) or [])

    wrong_runtime = replace(loaded, canonical_python="3.99.0")
    with pytest.raises(BuildError, match="Canonical generation requires Python"):
        builder.build(wrong_runtime, sync_first=True)
    assert synced == []

    results = builder.build(loaded, include_local=False, sync_first=True)
    assert [result.name for result in results] == ["public-guide"]
    assert synced == [["example-repo"]]

    with pytest.raises(BuildError, match="local-only policy"):
        builder.build(
            loaded,
            artifact_names=["restricted-guide"],
            include_local=False,
            sync_first=False,
        )
    with pytest.raises(BuildError, match="Unknown collections"):
        builder.build(loaded, collection_ids=["missing"], sync_first=False)
    with pytest.raises(BuildError, match="Unknown artifacts"):
        builder.build(loaded, artifact_names=["missing"], sync_first=False)


def test_replacement_helper_rejects_targets_outside_declared_root(tmp_path: Path) -> None:
    output_root = tmp_path / "skills"
    staged = tmp_path / "staged"
    staged.mkdir()

    with pytest.raises(BuildError, match="outside"):
        builder._replace_generated_directory(staged, tmp_path / "elsewhere" / "skill", output_root)


def test_generated_output_roots_and_writers_reject_symlink_redirects(
    built_project: tuple[Manifest, Path], tmp_path: Path
) -> None:
    loaded, _checkout = built_project
    committed = loaded.root_for("committed")
    committed.mkdir(parents=True)
    local_parent = loaded.project_root / ".generated"
    local_parent.mkdir()
    loaded.root_for("local-only").symlink_to(committed, target_is_directory=True)
    restricted = loaded.collections["restricted-guides"]
    with pytest.raises(BuildError, match="symlink|same directory"):
        builder.build_skill(loaded, restricted, restricted.artifacts[0])

    loaded.root_for("local-only").unlink()
    outside = tmp_path / "outside-catalog"
    outside.mkdir()
    (loaded.project_root / "catalog").symlink_to(outside, target_is_directory=True)
    with pytest.raises(GoogleGuideSkillsError, match="symlink"):
        catalog.write_catalog(loaded)


def test_catalog_records_cover_committed_local_and_catalog_only(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    builder.build_skill(
        loaded,
        loaded.collections["public-guides"],
        loaded.collections["public-guides"].artifacts[0],
    )

    records = catalog.catalog_records(loaded)
    by_id = {record["id"]: record for record in records}

    assert list(by_id) == sorted(by_id)
    assert by_id["public-guide"]["generated"] is True
    assert by_id["public-guide"]["path"] == "skills/public-guide"
    assert by_id["restricted-guide"]["generated"] is False
    assert by_id["restricted-guide"]["distribution"] == "local-only"
    assert by_id["restricted-guide"]["license"] == "CC-BY-NC-ND-4.0"
    assert by_id["web-only-guide"]["distribution"] == "catalog-only"
    assert by_id["web-only-guide"]["status"] == "snapshot-pending"


def test_write_catalog_links_only_generated_committed_skills(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    builder.build(loaded, include_local=True, sync_first=False)

    json_path, markdown_path = catalog.write_catalog(loaded)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["source_manifest"] == "corpus.yaml"
    by_id = {record["id"]: record for record in payload["skills"]}
    assert by_id["restricted-guide"]["generated"] is False
    root_catalog = markdown_path.read_text(encoding="utf-8")
    assert "[`public-guide`](../skills/public-guide/SKILL.md)" in root_catalog
    assert "[`restricted-guide`]" not in root_catalog
    index_catalog = (
        loaded.project_root / "skills" / "google-guides-index" / "references" / "catalog.md"
    ).read_text(encoding="utf-8")
    assert "[`public-guide`](../../public-guide/SKILL.md)" in index_catalog
    assert "name: google-guides-index" in (
        loaded.project_root / "skills" / "google-guides-index" / "SKILL.md"
    ).read_text(encoding="utf-8")
    index_references = loaded.project_root / "skills/google-guides-index/references"
    index_provenance = json.loads(
        (index_references / "source.json").read_text(encoding="utf-8")
    )
    assert index_provenance["collection"] == "authored-index"
    assert hashlib.sha256((index_references / "LICENSE.txt").read_bytes()).hexdigest() == (
        index_provenance["license"]["sha256"]
    )


def test_metrics_count_text_files_and_gate_local_output(
    built_project: tuple[Manifest, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded, _checkout = built_project
    builder.build(loaded, include_local=True, sync_first=False)
    (loaded.project_root / "skills" / "public-guide" / "ignored.bin").write_bytes(b"binary")
    monkeypatch.setattr(metrics.tiktoken, "get_encoding", lambda _name: _WordEncoding())

    public = metrics.collect_metrics(loaded, include_local=False)
    all_output = metrics.collect_metrics(loaded, include_local=True)

    assert public["includes_local_only"] is False
    assert public["summary"]["skills"] == 1
    assert {skill["skill"] for skill in public["skills"]} == {"public-guide"}
    assert all_output["summary"]["skills"] == 2
    assert {skill["distribution"] for skill in all_output["skills"]} == {
        "committed",
        "local-only",
    }
    assert all(not record["path"].endswith("ignored.bin") for record in public["files"])
    public_skill = public["skills"][0]
    assert public_skill["metadata_tokens_o200k_base"] > 0
    assert public_skill["total_tokens_o200k_base"] == sum(
        record["tokens_o200k_base"] for record in public["files"]
    )
    license_files = [record for record in public["files"] if record["kind"] == "license"]
    assert {Path(record["path"]).name for record in license_files} == {
        "LICENSE.txt",
        "LICENSE-Generator-Apache-2.0.txt",
    }
    assert public_skill["license_tokens_o200k_base"] == sum(
        record["tokens_o200k_base"] for record in license_files
    )


def test_write_metrics_uses_catalog_or_ignored_output_by_policy(
    built_project: tuple[Manifest, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded, _checkout = built_project
    builder.build(loaded, include_local=True, sync_first=False)
    monkeypatch.setattr(metrics.tiktoken, "get_encoding", lambda _name: _WordEncoding())

    json_path, csv_path = metrics.write_metrics(loaded, include_local=False)
    local_json, local_csv = metrics.write_metrics(loaded, include_local=True)

    assert json_path == loaded.project_root / "catalog" / "tokens.json"
    assert csv_path == loaded.project_root / "catalog" / "tokens.csv"
    assert local_json == loaded.project_root / ".generated" / "metrics" / "tokens.json"
    assert local_csv == loaded.project_root / ".generated" / "metrics" / "tokens.csv"
    with csv_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    assert set(rows[0]) == {
        "path",
        "skill",
        "kind",
        "bytes",
        "lines",
        "words",
        "tokens_o200k_base",
    }


def test_validation_accepts_complete_generated_tree_and_optional_local_tree(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())

    public_issues = validation.validate(generated_project, include_local=False)
    all_issues = validation.validate(generated_project, include_local=True)

    assert not validation.has_errors(public_issues)
    assert not validation.has_errors(all_issues)


def test_validation_detects_unignored_and_tracked_local_only_output(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    local_skill = root / ".generated" / "skills" / "restricted-guide" / "SKILL.md"
    _git(root, "add", "-f", local_skill.relative_to(root).as_posix())

    tracked = validation.validate(generated_project, include_local=True)
    assert any("Local-only generated output is tracked" in issue.message for issue in tracked)

    (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    unignored = validation.validate(generated_project, include_local=True)
    assert any("local-only generated root is not ignored" in issue.message for issue in unignored)


def test_validation_does_not_trust_a_global_git_excludes_file(
    generated_project: Manifest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    (root / ".gitignore").write_text(".cache/\n", encoding="utf-8")
    excludes = tmp_path / "global-excludes"
    excludes.write_text(".generated/\n", encoding="utf-8")
    global_config = tmp_path / "global-gitconfig"
    global_config.write_text(
        f"[core]\n\texcludesFile = {excludes.as_posix()}\n", encoding="utf-8"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    ambient = subprocess.run(
        ["git", "check-ignore", "--quiet", ".generated/skills"],
        cwd=root,
        check=False,
    )
    assert ambient.returncode == 0

    issues = validation.validate(generated_project, include_local=True)

    assert any("local-only generated root is not ignored" in issue.message for issue in issues)


def test_validation_rejects_local_provenance_in_committed_root(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    source = root / ".generated" / "skills" / "restricted-guide"
    target = root / "skills" / "restricted-guide"
    shutil.copytree(source, target)

    issues = validation.validate(generated_project)

    messages = [issue.message for issue in issues]
    assert "Recorded distribution 'local-only' does not match 'committed'" in messages
    assert "Local-only source material appeared in the committed skills root" in messages
    assert "Skill belongs in local-only, not committed" in messages


def test_validation_rejects_disguised_local_provenance(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    source = root / ".generated" / "skills" / "restricted-guide"
    target = root / "skills" / "restricted-guide"
    shutil.copytree(source, target)
    provenance_path = target / "references" / "source.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["distribution"] = "committed"
    provenance["collection"] = "public-guides"
    provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

    messages = [issue.message for issue in validation.validate(generated_project)]
    assert "Skill belongs in local-only, not committed" in messages
    assert "Provenance collection does not own this artifact" in messages


def test_validation_rejects_stale_skills_and_mismatched_artifact_provenance(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    source = root / "skills" / "public-guide"
    stale = root / "skills" / "stale-guide"
    shutil.copytree(source, stale)
    stale_source = stale / "references" / "source.json"
    provenance = json.loads(stale_source.read_text(encoding="utf-8"))
    provenance["artifact"] = "different-guide"
    stale_source.write_text(json.dumps(provenance), encoding="utf-8")

    issues = validation.validate(generated_project)
    messages = [issue.message for issue in issues]

    assert "Unexpected generated skill not declared in corpus.yaml" in messages
    assert "Provenance artifact does not match the skill directory" in messages


def test_validation_reports_frontmatter_links_provenance_and_missing_skills(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    public_skill = root / "skills" / "public-guide" / "SKILL.md"
    public_skill.write_text(
        "---\nname: wrong-name\ndescription: useful\nextra: unsupported\n---\n"
        "Body with [missing metadata](references/missing.json).\n",
        encoding="utf-8",
    )
    provenance = root / "skills" / "public-guide" / "references" / "source.json"
    provenance.write_text("{not json}\n", encoding="utf-8")
    index_catalog = root / "skills" / "google-guides-index" / "references" / "catalog.md"
    index_catalog.write_text("[escape](../../../../outside.md)\n", encoding="utf-8")
    shutil.rmtree(root / "skills" / "google-guides-index")
    # Recreate the index with an escaping catalog link so both checks remain reachable.
    index_dir = root / "skills" / "google-guides-index"
    (index_dir / "references").mkdir(parents=True)
    (index_dir / "SKILL.md").write_text(catalog.render_index_skill(), encoding="utf-8")
    (index_dir / "references" / "catalog.md").write_text(
        "[escape](../../../../outside.md)\n", encoding="utf-8"
    )

    issues = validation.validate(generated_project)
    messages = [issue.message for issue in issues]

    assert "Frontmatter has unsupported fields: extra" in messages
    assert "Skill name 'wrong-name' does not match directory 'public-guide'" in messages
    assert "Broken local link: references/missing.json" in messages
    assert any(message.startswith("Invalid source metadata:") for message in messages)
    assert "Link escapes project root: ../../../../outside.md" in messages

    shutil.rmtree(root / "skills" / "public-guide")
    missing = validation.validate(generated_project)
    assert any(
        issue.path == "skills/public-guide" and issue.message == "Skill not built"
        for issue in missing
    )


def test_validation_reports_missing_skill_file_and_invalid_frontmatter(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    empty_dir = root / "skills" / "extra-directory"
    empty_dir.mkdir()
    skill = root / "skills" / "public-guide" / "SKILL.md"
    skill.write_text("not frontmatter\n", encoding="utf-8")

    issues = validation.validate(generated_project)

    assert any(
        issue.path == "skills/extra-directory" and issue.message == "Missing SKILL.md"
        for issue in issues
    )
    assert any(
        issue.path == "skills/public-guide/SKILL.md" and issue.message == "Missing YAML frontmatter"
        for issue in issues
    )


def test_sources_sync_repository_clones_fetches_and_checks_out_exact_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = _write_manifest(tmp_path, _manifest_data())
    repository = loaded.repositories["example-repo"]
    calls: list[tuple[list[str], Path | None]] = []

    def fake_run(args: list[str], cwd: Path | None = None) -> str:
        calls.append((args, cwd))
        if args == ["git", "init", "--quiet"]:
            assert cwd is not None
            (cwd / ".git").mkdir()
            return ""
        if args == ["git", "remote", "get-url", "origin"]:
            return repository.url
        if args == ["git", "status", "--porcelain"]:
            return ""
        if args == ["git", "rev-parse", "HEAD"]:
            return repository.revision
        return ""

    monkeypatch.setattr(sources, "_run", fake_run)
    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
    )

    result = sources.sync_repository(loaded, repository)

    assert result == tmp_path / ".cache" / "sources" / "example-repo"
    assert (["git", "init", "--quiet", "--template="], result) in calls
    assert (["git", "remote", "add", "origin", repository.url], result) in calls
    assert not any(call[0][:2] == ["git", "clone"] for call in calls)
    assert (["git", "fetch", "--depth", "1", "origin", repository.revision], result) in calls
    assert (["git", "checkout", "--detach", repository.revision], result) in calls


def test_sources_refuse_non_git_wrong_remote_and_dirty_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = _write_manifest(tmp_path, _manifest_data())
    repository = loaded.repositories["example-repo"]
    target = sources.checkout_path(loaded, repository.id)
    target.mkdir(parents=True)
    with pytest.raises(SourceError, match="non-git cache path"):
        sources.sync_repository(loaded, repository)

    (target / ".git").mkdir()
    monkeypatch.setattr(sources, "repository_config_problem", lambda *_args: None)
    monkeypatch.setattr(sources, "_remote_url", lambda _path: "https://evil.test/repo.git")
    with pytest.raises(SourceError, match="points to"):
        sources.sync_repository(loaded, repository)

    monkeypatch.setattr(sources, "_remote_url", lambda _path: repository.url.removesuffix(".git"))
    monkeypatch.setattr(
        sources.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(sources, "_run", lambda args, cwd=None: "dirty" if "status" in args else "")
    with pytest.raises(SourceError, match="local changes"):
        sources.sync_repository(loaded, repository)


def test_source_cache_rejects_replace_refs_and_disables_checkout_hooks(
    built_project: tuple[Manifest, Path]
) -> None:
    loaded, checkout = built_project
    repository = loaded.repositories["example-repo"]
    replacement_dir = checkout / ".git" / "refs" / "replace"
    replacement_dir.mkdir(parents=True)
    (replacement_dir / repository.revision).write_text(
        repository.revision + "\n", encoding="utf-8"
    )
    with pytest.raises(SourceError, match="replacement refs"):
        sources.sync_repository(loaded, repository)

    (replacement_dir / repository.revision).unlink()
    marker = loaded.project_root / "hook-ran"
    hook = checkout / ".git" / "hooks" / "post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {marker}\n", encoding="utf-8")
    hook.chmod(0o755)

    assert sources.sync_repository(loaded, repository) == checkout
    assert not marker.exists()

    outside = loaded.project_root / "outside-worktree"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("unchanged\n", encoding="utf-8")
    _git(checkout, "config", "core.worktree", str(outside))
    with pytest.raises(SourceError, match="unsafe local Git config.*core.worktree"):
        sources.sync_repository(loaded, repository)
    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"


def test_sources_run_wraps_process_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(2, ["git", "bad"], output="fatal fixture")

    monkeypatch.setattr(sources.subprocess, "run", fail)

    with pytest.raises(SourceError, match="fatal fixture"):
        sources._run(["git", "bad"])


def test_sources_sync_validates_ids_and_preserves_requested_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _manifest_data()
    data["repositories"]["second-repo"] = copy.deepcopy(  # type: ignore[index]
        data["repositories"]["example-repo"]  # type: ignore[index]
    )
    data["repositories"]["second-repo"]["url"] = "https://example.test/second.git"  # type: ignore[index]
    loaded = _write_manifest(tmp_path, data)
    seen: list[str] = []

    def fake_sync(current: Manifest, repository: object) -> Path:
        del current
        repo_id = repository.id  # type: ignore[attr-defined]
        seen.append(repo_id)
        return tmp_path / repo_id

    monkeypatch.setattr(sources, "sync_repository", fake_sync)

    results = sources.sync(loaded, ["second-repo", "example-repo"])
    assert seen == ["second-repo", "example-repo"]
    assert results == [tmp_path / "second-repo", tmp_path / "example-repo"]
    with pytest.raises(SourceError, match="Unknown repositories: missing"):
        sources.sync(loaded, ["missing"])


def test_install_commands_route_committed_and_local_skills(
    tmp_path: Path,
) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    loaded.root_for("local-only").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()

    committed = installer.install_commands(
        loaded,
        project,
        ["codex", "claude-code"],
        skills=["google-guides-index", "public-guide"],
        copy=True,
        global_install=True,
    )
    assert committed == [
        [
            "npx",
            "--yes",
            installer.SKILLS_CLI_PACKAGE,
            "add",
            str(loaded.root_for("committed")),
            "--agent",
            "codex",
            "--agent",
            "claude-code",
            "--skill",
            "google-guides-index",
            "--skill",
            "public-guide",
            "--yes",
            "--copy",
            "--global",
        ]
    ]

    project = loaded.project_root / "evals" / "results" / "consumer"
    project.mkdir(parents=True)
    both = installer.install_commands(
        loaded,
        project,
        ["codex"],
        skills=["public-guide", "restricted-guide"],
        include_local=True,
    )
    assert len(both) == 2
    assert str(loaded.root_for("committed")) in both[0]
    assert both[0][-3:-1] == ["--skill", "public-guide"]
    assert str(loaded.root_for("local-only")) in both[1]
    assert both[1][-3:-1] == ["--skill", "restricted-guide"]


def test_install_commands_validate_inputs_and_missing_roots(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()

    with pytest.raises(GoogleGuideSkillsError, match="at least one target"):
        installer.install_commands(loaded, project, [])
    with pytest.raises(GoogleGuideSkillsError, match="does not exist"):
        installer.install_commands(loaded, tmp_path / "missing", ["codex"])
    with pytest.raises(GoogleGuideSkillsError, match="unavailable"):
        installer.install_commands(
            loaded, project, ["codex"], skills=["restricted-guide"], include_local=False
        )
    safe_project = loaded.project_root / "evals" / "results" / "consumer"
    safe_project.mkdir(parents=True)
    with pytest.raises(GoogleGuideSkillsError, match="Generated skill root does not exist"):
        installer.install_commands(loaded, safe_project, ["codex"], include_local=True)


def test_install_commands_enumerate_manifest_allowlist(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()

    commands = installer.install_commands(loaded, project, ["codex"])

    assert commands[0][-5:] == [
        "--skill",
        "google-guides-index",
        "--skill",
        "public-guide",
        "--yes",
    ]


def test_install_all_routes_local_only_to_separate_safe_root(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    loaded.root_for("local-only").mkdir(parents=True)
    project = loaded.project_root / "evals" / "results" / "workspace"
    project.mkdir(parents=True)

    commands = installer.install_commands(
        loaded, project, ["codex"], skills=None, include_local=True, copy=True
    )

    assert len(commands) == 2
    assert commands[0][4] == str(loaded.root_for("committed"))
    assert commands[1][4] == str(loaded.root_for("local-only"))
    assert commands[0][-6:] == [
        "--skill",
        "google-guides-index",
        "--skill",
        "public-guide",
        "--yes",
        "--copy",
    ]
    assert commands[1][-4:] == ["--skill", "restricted-guide", "--yes", "--copy"]

    external = tmp_path / "external"
    external.mkdir()
    with pytest.raises(GoogleGuideSkillsError, match="only into ignored evaluation"):
        installer.install_commands(loaded, external, ["codex"], include_local=True)
    with pytest.raises(GoogleGuideSkillsError, match="does not export local-only"):
        installer.install(loaded, external, ["codex"], include_local=True, dry_run=True)
    with pytest.raises(GoogleGuideSkillsError, match="Global installation is disabled"):
        installer.install(loaded, external, ["codex"], global_install=True, dry_run=True)


def test_install_dry_run_and_execution_use_npx_without_network_in_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.setenv("SENTINEL_SECRET", "must-not-leak")
    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/usr/bin/npx")
    calls: list[tuple[list[str], Path]] = []

    def fake_run(
        command: list[str],
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        check: bool,
    ) -> None:
        assert check is True
        assert timeout == installer.INSTALL_TIMEOUT_SECONDS
        assert "SENTINEL_SECRET" not in env
        assert Path(env["HOME"]).is_dir()
        calls.append((command, cwd))

    monkeypatch.setattr(installer.subprocess, "run", fake_run)

    dry_commands = installer.install(loaded, project, ["codex"], dry_run=True)
    assert calls == []
    actual_commands = installer.install(loaded, project, ["codex"])
    assert actual_commands == dry_commands
    assert calls == [(actual_commands[0], project)]


def test_install_reports_missing_npx_and_process_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    with pytest.raises(GoogleGuideSkillsError, match="npx is required"):
        installer.install(loaded, project, ["codex"])

    monkeypatch.setattr(installer.shutil, "which", lambda _name: "/usr/bin/npx")

    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, ["npx"])

    monkeypatch.setattr(installer.subprocess, "run", fail)
    with pytest.raises(GoogleGuideSkillsError, match="Skill installation failed"):
        installer.install(loaded, project, ["codex"])
