"""Hermetic tests for the generator's non-evaluation core."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from google_guide_skills import (
    builder,
    catalog,
    installer,
    manifest,
    metrics,
    path_policy,
    sources,
    validation,
)
from google_guide_skills.convert import markup_to_markdown, source_to_markdown
from google_guide_skills.errors import (
    BuildError,
    GoogleGuideSkillsError,
    ManifestError,
    SourceError,
)
from google_guide_skills.models import (
    Manifest,
    SourceExcerpt,
    SourcePathPolicy,
    SupplementalLicense,
)


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
        "schema_version": 2,
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
                        "inputs": ["guide.md"],
                        "excerpts": [
                            {
                                "input": "guide.md",
                                "heading": "Upstream",
                                "blocks": [0, 1, 2, 3],
                            }
                        ],
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
                        "inputs": ["restricted/chapter.html"],
                        "excerpts": [
                            {
                                "input": "restricted/chapter.html",
                                "heading": "Operational rule",
                                "blocks": [0, 1],
                            }
                        ],
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
    (project / "LICENSE").write_bytes((Path(__file__).parents[1] / "LICENSE").read_bytes())
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
    (checkout / "guide.md").write_text(
        "# Upstream\n\nKeep this text verbatim (see [??](#related-rule)). See "
        "[reference][missing], [shortcut], and `[Symbol.iterator]`.\n\n"
        "- parent\n\n    - child\n\n"
        "```markdown\n# example comment\n[example](relative.md)\n```\n\n"
        "[shortcut]: https://example.test\n",
        encoding="utf-8",
    )
    restricted = checkout / "restricted"
    restricted.mkdir()
    (restricted / "chapter.html").write_text(
        "<!-- CC BY-NC-ND 4.0 --><main><h1>Chapter</h1><h2>Historical topic</h2>"
        "<p>Historical text to omit.</p><h2>Operational rule</h2>"
        "<p>Apply the private rule to the current design.</p>"
        "<ul><li>Check the affected users.</li><li>Verify the result.</li></ul></main>",
        encoding="utf-8",
    )
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

    assert loaded.schema_version == 2
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

    wildcard = _manifest_data()
    wildcard["collections"]["public-guides"]["artifacts"][0]["inputs"] = ["*.md"]  # type: ignore[index]
    with pytest.raises(ManifestError, match="exact source files"):
        _write_manifest(tmp_path / "wildcard", wildcard)

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
    bad_schema["schema_version"] = 1
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


def test_manifest_rejects_invalid_distribution_excerpts_and_local_license(tmp_path: Path) -> None:
    bad_distribution = _manifest_data()
    bad_distribution["collections"]["public-guides"]["distribution"] = "private"  # type: ignore[index]
    with pytest.raises(ManifestError, match="distribution"):
        _write_manifest(tmp_path / "distribution", bad_distribution)

    missing_excerpts = _manifest_data()
    del missing_excerpts["collections"]["public-guides"]["artifacts"][0]["excerpts"]  # type: ignore[index]
    with pytest.raises(ManifestError, match="require source excerpts"):
        _write_manifest(tmp_path / "missing-excerpts", missing_excerpts)

    legacy_recipe = _manifest_data()
    legacy_recipe["collections"]["public-guides"]["artifacts"][0]["recipe"] = (  # type: ignore[index]
        "recipes/public-guide.md"
    )
    with pytest.raises(ManifestError, match="recipe is no longer supported"):
        _write_manifest(tmp_path / "legacy-recipe", legacy_recipe)

    unordered_blocks = _manifest_data()
    unordered_blocks["collections"]["restricted-guides"]["artifacts"][0]["excerpts"][0][  # type: ignore[index]
        "blocks"
    ] = [1, 0]
    with pytest.raises(ManifestError, match="strictly increasing"):
        _write_manifest(tmp_path / "unordered-blocks", unordered_blocks)

    duplicate_selector = _manifest_data()
    duplicate_selector["collections"]["public-guides"]["artifacts"][0]["excerpts"].append(  # type: ignore[index]
        {"input": "guide.md", "heading": " upstream ", "blocks": [0]}
    )
    with pytest.raises(ManifestError, match="duplicates an input and heading"):
        _write_manifest(tmp_path / "duplicate-selector", duplicate_selector)

    incomplete_excerpts = _manifest_data()
    incomplete_excerpts["collections"]["restricted-guides"]["artifacts"][0][  # type: ignore[index]
        "inputs"
    ].append("restricted/other.html")
    with pytest.raises(ManifestError, match="select from every input"):
        _write_manifest(tmp_path / "incomplete-excerpts", incomplete_excerpts)

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
    duplicate.write_text("schema_version: 2\nschema_version: 2\n", encoding="utf-8")
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


def test_source_to_markdown_preserves_google_styleguide_structure(tmp_path: Path) -> None:
    path = tmp_path / "guide.xml"
    path.write_text(
        '<GUIDE title="Guide"><CATEGORY title="Category">'
        '<STYLEPOINT title="Rule"><SUMMARY><p>Do this.</p></SUMMARY>'
        "<BODY><CODE_SNIPPET>good()</CODE_SNIPPET>"
        "<BAD_CODE_SNIPPET>bad()</BAD_CODE_SNIPPET></BODY>"
        "</STYLEPOINT></CATEGORY></GUIDE>",
        encoding="utf-8",
    )

    converted, mode = source_to_markdown(path)

    assert mode == "google-styleguide-xml-to-markdown"
    assert "# Guide" in converted
    assert "## Category" in converted
    assert "### Rule" in converted
    assert "Do this." in converted
    assert "good()" in converted
    assert "**Bad code:**" in converted
    assert "bad()" in converted


def test_sanitize_excerpt_preserves_inline_code() -> None:
    text = "Use `a[i][j]`, `items[key]`, and ``items[`key`]``."

    assert builder._sanitize_excerpt(text, {"key": "https://example.test"}) == text


def test_sanitize_excerpt_removes_reference_images() -> None:
    text = r"Use ![full][arch], ![collapsed][], ![shortcut], and \![literal][arch]."

    assert builder._sanitize_excerpt(text, {"arch": "https://example.test/a.png"}) == (
        r"Use full, collapsed, shortcut, and \![literal][arch]."
    )


def test_sanitize_excerpt_handles_code_inside_link_labels() -> None:
    text = "See [Test, `[ … ]`, and `[[ … ]]`](#tests) and [`format.Source`]."

    assert builder._sanitize_excerpt(
        text,
        {"`format.source`": "https://pkg.go.dev/go/format#Source"},
    ) == (
        "See Test, `[ … ]`, and `[[ … ]]` and "
        "[`format.Source`](https://pkg.go.dev/go/format#Source)."
    )


def test_sanitize_excerpt_handles_balanced_link_destinations() -> None:
    assert builder._sanitize_excerpt("See [label](guide_(old).md).") == "See label."
    assert builder._sanitize_excerpt("See ![diagram](images/a_(old).png).") == "See diagram."
    assert builder._sanitize_excerpt("See [multi-line\nlabel](#section).") == (
        "See multi-line\nlabel."
    )


def test_sanitize_excerpt_removes_unselected_cross_reference_clauses() -> None:
    text = (
        "Keep this rule.\n(See the example in [??](#missing-example)).\n"
        "Wrap the line, as explained in [??](#missing-details).\n"
        "Prefer small tests, as demonstrated in [Figure 11-2](#test-sizes).\n"
        "[Figure 11-3](#test-pyramid) depicts the intended test mix.\n"
        "Use whitespace, such as that shown in "
        "[A well-structured test](#example_well_structured).\n"
        "Prefer clarity. To illustrate, [A bad test](#example_bad) presents bad code.\n"
        "State tests are stable. [A brittle test](#example_brittle) illustrates a bad test.\n"
        "Use stubs for a specific state, such as "
        "[A stub example](#example_stub) that requires a response.\n"
        "As shown in the [example](#Example), the recommended order is stable.\n"
        "Keep indentation. (See the example in Section 4.1.2, K & R Style.)\n"
        "Use these tools (see [Figure 17-2](#tools)). For example, inspect a log.\n"
        "Use dicts (but see [Figure 1](#example)), and avoid arrays.\n"
        "Allow this in limited cases; see below for details.\n"
        "Feedback must be actionable. We'll look at an example of this feedback later in this "
        "chapter. By improving output, teams can act.\n"
        "Automate the change (see Case Study: Operation RoseHub). Preserve readability "
        "(see Style Guides and Rules).\n"
        "Feature flags help, which we explore further in Continuous Delivery.\n"
        "Approval matters. We'll cover approval in the next section. Keep reviewing.\n"
        "Critique works (we look at the details later in this chapter) because culture matters.\n"
        "Understand the rationale. See Style Guides and Rules. Apply it."
    )

    assert builder._sanitize_excerpt(text) == (
        "Keep this rule.\nWrap the line.\nPrefer small tests.\nUse whitespace.\nPrefer clarity.\n"
        "State tests are stable.\nUse stubs for a specific state.\n"
        "The recommended order is stable.\nKeep indentation.\n"
        "Use these tools. For example, inspect a log.\nUse dicts, and avoid arrays.\n"
        "Allow this in limited cases.\n"
        "Feedback must be actionable. By improving output, teams can act.\n"
        "Automate the change. Preserve readability.\n"
        "Feature flags help.\nApproval matters. Keep reviewing.\n"
        "Critique works because culture matters.\nUnderstand the rationale. Apply it."
    )


def test_sanitize_excerpt_rejects_unresolved_visual_reference() -> None:
    with pytest.raises(BuildError, match="guide.md.*unresolved source cross-reference"):
        builder._sanitize_excerpt(
            "Consult [Figure 1](#missing) before continuing.",
            context="guide.md heading 'Rule' block 0",
        )


def test_reference_links_ignore_fenced_examples() -> None:
    markdown = (
        "[Foo   Bar]: https://first.example.test\n"
        "[foo bar]: https://second.example.test\n"
        "    [indented]: https://example.test\n\n"
        "```markdown\n[fenced]: https://example.test\n```"
    )
    links = builder._reference_links(markdown)

    assert links == {"foo bar": "https://first.example.test"}
    assert builder._sanitize_excerpt(
        r"Use [Foo Bar], \[Foo Bar], and \[Label][Foo Bar].", links
    ) == (r"Use [Foo Bar](https://first.example.test), \[Foo Bar], and \[Label][Foo Bar].")


def test_section_blocks_honors_fence_length() -> None:
    markdown = """# Guide

## Rule

````markdown
```python
# code comment
```
````

Keep this sentence.

## Next rule

Not selected.
"""

    _title, _heading, blocks = builder._section_blocks(markdown, "Rule", "guide.md")

    assert blocks == (
        "````markdown\n```python\n# code comment\n```\n````",
        "Keep this sentence.",
    )


def test_section_blocks_keeps_indented_list_fences_together() -> None:
    markdown = """# Guide

## Rule

- Example:

    ```python
    value = 1

    # Still code.
    ```

Keep this sentence.
"""

    _title, _heading, blocks = builder._section_blocks(markdown, "Rule", "guide.md")

    assert blocks == (
        "- Example:",
        "    ```python\n    value = 1\n\n    # Still code.\n    ```",
        "Keep this sentence.",
    )


def test_sanitize_excerpt_preserves_fence_after_prose() -> None:
    text = "Intro.\n~~~markdown\n[example](relative.md)\n~~~"

    assert builder._sanitize_excerpt(text) == text


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
    assert "See reference, [shortcut](https://example.test), and `[Symbol.iterator]`." in skill_text
    assert "\n    - child\n" in skill_text
    assert "# example comment" in skill_text
    assert "[example](relative.md)" in skill_text
    assert "references/" not in skill_text
    license_text = (result.path / "LICENSE.txt").read_text(encoding="utf-8")
    assert "Example license text" in license_text
    provenance = json.loads((result.path / "source.json").read_text(encoding="utf-8"))
    assert provenance["distribution"] == "committed"
    assert provenance["repository"]["revision"] == _git(checkout, "rev-parse", "HEAD")
    assert provenance["inputs"] == [
        {
            "conversion": "identity",
            "path": "guide.md",
            "sha256": hashlib.sha256((checkout / "guide.md").read_bytes()).hexdigest(),
        }
    ]
    assert provenance["rendering"] == "source-excerpts"
    assert provenance["excerpts"] == [
        {"input": "guide.md", "heading": "Upstream", "blocks": [0, 1, 2, 3]}
    ]
    assert "recipe" not in provenance
    assert provenance["generator_runtime"]["python"] == loaded.canonical_python
    assert provenance["wrapper_license"]["spdx"] == "Apache-2.0"
    wrapper = result.path / provenance["wrapper_license"]["path"]
    assert (
        hashlib.sha256(wrapper.read_bytes()).hexdigest() == provenance["wrapper_license"]["sha256"]
    )


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
    assert "## Chapter" in skill_text
    assert "### Operational rule" in skill_text
    assert "Apply the private rule to the current design." in skill_text
    assert "Check the affected users." in skill_text
    assert "Verify the result." in skill_text
    assert "Historical text to omit." not in skill_text
    assert not (result.path / "references").exists()
    license_text = (result.path / "LICENSE.txt").read_text(encoding="utf-8")
    assert "WARNING: Do not redistribute generated output." in license_text

    committed = replace(collection, distribution="committed")
    with pytest.raises(BuildError, match="forbids committed generated output"):
        builder.build_skill(loaded, committed, committed.artifacts[0])


@pytest.mark.parametrize("missing_name", ["source.json", "LICENSE.txt"])
def test_validation_requires_generated_provenance_and_license(
    generated_project: Manifest, missing_name: str
) -> None:
    missing = generated_project.root_for("committed") / "public-guide" / missing_name
    missing.unlink()

    issues = validation.validate(generated_project)

    assert any(issue.severity == "error" and issue.path.endswith(missing_name) for issue in issues)


def test_validation_rejects_a_stale_supplemental_license(
    generated_project: Manifest,
) -> None:
    project_license = generated_project.project_root / "LICENSE"
    supplemental = SupplementalLicense(
        spdx="Apache-2.0",
        name="Apache License 2.0",
        url="https://www.apache.org/licenses/LICENSE-2.0",
        attribution="Test project contributors",
        scope="Code samples",
        license_file="LICENSE",
        evidence_contains="Keep this text verbatim.",
        sha256=hashlib.sha256(project_license.read_bytes()).hexdigest(),
    )
    collection = generated_project.collections["public-guides"]
    artifact = replace(collection.artifacts[0], supplemental_licenses=(supplemental,))
    collection = replace(collection, artifacts=(artifact,))
    loaded = replace(
        generated_project,
        collections={**generated_project.collections, collection.id: collection},
    )
    skill_dir = loaded.root_for("committed") / artifact.name
    supplemental_path = skill_dir / "LICENSE-Apache-2.0.txt"
    shutil.copyfile(project_license, supplemental_path)
    source_path = skill_dir / "source.json"
    provenance = json.loads(source_path.read_text(encoding="utf-8"))
    provenance["supplemental_licenses"] = [supplemental.to_dict()]
    source_path.write_text(json.dumps(provenance), encoding="utf-8")

    assert not any(
        "Supplemental source license" in issue.message for issue in validation.validate(loaded)
    )
    supplemental_path.write_text("changed\n", encoding="utf-8")

    assert any(
        issue.severity == "error" and "Supplemental source license" in issue.message
        for issue in validation.validate(loaded)
    )


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
    source = checkout / "restricted" / "chapter.html"
    source.write_text(
        source.read_text(encoding="utf-8").replace("CC BY-NC-ND 4.0", "notice removed"),
        encoding="utf-8",
    )
    _git(checkout, "add", source.relative_to(checkout).as_posix())
    _git(checkout, "commit", "--quiet", "-m", "remove file-level notice")
    repository = replace(
        loaded.repositories["example-repo"],
        revision=_git(checkout, "rev-parse", "HEAD"),
    )
    updated = replace(loaded, repositories={"example-repo": repository})

    collection = updated.collections["restricted-guides"]
    with pytest.raises(BuildError, match="lost the required license notice"):
        builder.build_skill(updated, collection, collection.artifacts[0])


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
    built_project: tuple[Manifest, Path],
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


def test_build_rejects_wrong_revision_missing_input_and_invalid_excerpt_selection(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, checkout = built_project
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

    restricted = loaded.collections["restricted-guides"]
    missing_heading = replace(
        restricted.artifacts[0],
        excerpts=(
            SourceExcerpt(
                input="restricted/chapter.html",
                heading="Missing heading",
                blocks=(0,),
            ),
        ),
    )
    with pytest.raises(BuildError, match="expected one heading 'Missing heading', found 0"):
        builder.build_skill(loaded, restricted, missing_heading)

    out_of_range = replace(
        restricted.artifacts[0],
        excerpts=(
            SourceExcerpt(
                input="restricted/chapter.html",
                heading="Operational rule",
                blocks=(99,),
            ),
        ),
    )
    with pytest.raises(BuildError, match=r"cannot select \[99\]"):
        builder.build_skill(loaded, restricted, out_of_range)

    chapter = checkout / "restricted/chapter.html"
    chapter.write_text(
        chapter.read_text(encoding="utf-8").replace(
            "</main>",
            "<h2>Operational rule</h2><p>Duplicate section.</p></main>",
        ),
        encoding="utf-8",
    )
    _git(checkout, "add", ".")
    _git(checkout, "commit", "--quiet", "-m", "duplicate heading")
    repository = replace(
        loaded.repositories["example-repo"],
        revision=_git(checkout, "rev-parse", "HEAD"),
    )
    duplicate_heading_manifest = replace(
        loaded,
        repositories={"example-repo": repository},
    )
    with pytest.raises(BuildError, match="expected one heading 'Operational rule', found 2"):
        builder.build_skill(
            duplicate_heading_manifest,
            restricted,
            restricted.artifacts[0],
        )


def test_full_build_prunes_only_recognized_stale_generated_skills(
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, _checkout = built_project
    local_root = loaded.root_for("local-only")
    stale = local_root / "retired-restricted-guide"
    marker = stale / "references/source.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(
        json.dumps(
            {
                "artifact": stale.name,
                "collection": "restricted-guides",
                "distribution": "local-only",
                "generated_by": "google-guide-skills/0.1.0.0",
            }
        ),
        encoding="utf-8",
    )
    manual = local_root / "manual-notes"
    manual.mkdir()

    builder.build(
        loaded,
        collection_ids=["restricted-guides"],
        include_local=True,
        sync_first=False,
    )

    assert not stale.exists()
    assert manual.is_dir()


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
    assert not (loaded.project_root / "skills" / "google-guides-index").exists()


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
    global_config.write_text(f"[core]\n\texcludesFile = {excludes.as_posix()}\n", encoding="utf-8")
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
    provenance_path = target / "source.json"
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
    stale_source = stale / "source.json"
    provenance = json.loads(stale_source.read_text(encoding="utf-8"))
    provenance["artifact"] = "different-guide"
    stale_source.write_text(json.dumps(provenance), encoding="utf-8")

    issues = validation.validate(generated_project)
    messages = [issue.message for issue in issues]

    assert "Unexpected generated skill not declared in corpus.yaml" in messages
    assert "Provenance artifact does not match the skill directory" in messages


def test_validation_rejects_legacy_recipe_provenance(generated_project: Manifest) -> None:
    root = generated_project.project_root
    source = root / "skills/public-guide/source.json"
    provenance = json.loads(source.read_text(encoding="utf-8"))
    provenance["recipe"] = {"path": "recipes/public-guide.md", "sha256": "0" * 64}
    source.write_text(json.dumps(provenance), encoding="utf-8")

    messages = [issue.message for issue in validation.validate(generated_project)]
    assert "Legacy recipe provenance is not allowed" in messages


def test_validation_reports_frontmatter_links_provenance_and_missing_skills(
    generated_project: Manifest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validation.tiktoken, "get_encoding", lambda _name: _WordEncoding())
    root = generated_project.project_root
    public_skill = root / "skills" / "public-guide" / "SKILL.md"
    public_skill.write_text(
        "---\nname: wrong-name\ndescription: useful\nextra: unsupported\n---\n"
        "Body with [missing metadata](references/missing.json) and "
        "[an escaping link](references/../../../../outside.md).\n"
        "![missing image](references/missing.png)\n"
        "`[inline code](references/ignored-inline.md)`\n"
        "````markdown\n```text\n[fenced](references/ignored-fence.md)\n```\n````\n",
        encoding="utf-8",
    )
    provenance = root / "skills" / "public-guide" / "source.json"
    provenance.write_text("{not json}\n", encoding="utf-8")
    issues = validation.validate(generated_project)
    messages = [issue.message for issue in issues]

    assert "Frontmatter has unsupported fields: extra" in messages
    assert "Skill name 'wrong-name' does not match directory 'public-guide'" in messages
    assert "Broken local link: references/missing.json" in messages
    assert "Broken local link: references/missing.png" in messages
    assert not any("ignored-" in message for message in messages)
    assert any(message.startswith("Invalid source metadata:") for message in messages)
    assert "Link escapes project root: references/../../../../outside.md" in messages

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
    built_project: tuple[Manifest, Path],
) -> None:
    loaded, checkout = built_project
    repository = loaded.repositories["example-repo"]
    replacement_dir = checkout / ".git" / "refs" / "replace"
    replacement_dir.mkdir(parents=True)
    (replacement_dir / repository.revision).write_text(repository.revision + "\n", encoding="utf-8")
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


def test_install_commands_route_committed_skills(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()

    commands = installer.install_commands(
        loaded,
        project,
        ["codex", "claude-code"],
        skills=["public-guide"],
        copy=True,
    )
    assert commands == [
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
            "public-guide",
            "--yes",
            "--copy",
        ]
    ]


def test_install_commands_validate_inputs_and_missing_roots(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    project = tmp_path / "consumer"
    project.mkdir()

    with pytest.raises(GoogleGuideSkillsError, match="Generated skill root does not exist"):
        installer.install_commands(loaded, project, ["codex"])

    loaded.root_for("committed").mkdir(parents=True)
    with pytest.raises(GoogleGuideSkillsError, match="at least one target"):
        installer.install_commands(loaded, project, [])
    with pytest.raises(GoogleGuideSkillsError, match="does not exist"):
        installer.install_commands(loaded, tmp_path / "missing", ["codex"])
    with pytest.raises(GoogleGuideSkillsError, match="unavailable"):
        installer.install_commands(loaded, project, ["codex"], skills=["restricted-guide"])


def test_checked_tree_hashes_tracks_directories_and_rejects_unsafe_paths(
    tmp_path: Path,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "empty").mkdir()

    assert path_policy.checked_tree_hashes(
        tree,
        context="Fixture tree",
        error_type=GoogleGuideSkillsError,
    ) == {"empty/": "directory"}

    with pytest.raises(GoogleGuideSkillsError, match="real directory"):
        path_policy.checked_tree_hashes(
            tmp_path / "missing",
            context="Fixture tree",
            error_type=GoogleGuideSkillsError,
        )

    outside = tmp_path / "outside"
    outside.mkdir()
    nested_link = tree / "link"
    nested_link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(GoogleGuideSkillsError, match="contains a symlink"):
        path_policy.checked_tree_hashes(
            tree,
            context="Fixture tree",
            error_type=GoogleGuideSkillsError,
        )
    nested_link.unlink()

    fifo = tree / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(GoogleGuideSkillsError, match="non-regular path"):
        path_policy.checked_tree_hashes(
            tree,
            context="Fixture tree",
            error_type=GoogleGuideSkillsError,
        )
    fifo.unlink()

    root_link = tmp_path / "tree-link"
    root_link.symlink_to(tree, target_is_directory=True)
    with pytest.raises(GoogleGuideSkillsError, match="real directory"):
        path_policy.checked_tree_hashes(
            root_link,
            context="Fixture tree",
            error_type=GoogleGuideSkillsError,
        )


def test_install_commands_enumerate_manifest_allowlist(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    loaded.root_for("committed").mkdir(parents=True)
    project = tmp_path / "consumer"
    project.mkdir()

    commands = installer.install_commands(loaded, project, ["codex"])

    assert commands[0][-3:] == [
        "--skill",
        "public-guide",
        "--yes",
    ]


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


def test_user_install_links_local_only_skills_without_copying_bytes(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    public = loaded.root_for("committed") / "public-guide"
    restricted = loaded.root_for("local-only") / "restricted-guide"
    for skill, text in ((public, "public\n"), (restricted, "restricted\n")):
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(text, encoding="utf-8")
    user_home = tmp_path / "user"

    planned = installer.install_links(
        loaded,
        ["codex"],
        skills=["public-guide", "restricted-guide"],
        include_local=True,
        dry_run=True,
        user_home=user_home,
    )
    assert [action.status for action in planned] == ["would-link", "would-link"]
    assert not (user_home / ".codex/skills").exists()

    actions = installer.install_links(
        loaded,
        ["codex"],
        skills=["public-guide", "restricted-guide"],
        include_local=True,
        user_home=user_home,
    )
    assert [action.status for action in actions] == ["linked", "linked"]
    public_link = user_home / ".codex/skills/public-guide"
    restricted_link = user_home / ".codex/skills/restricted-guide"
    assert public_link.is_symlink()
    assert public_link.resolve() == public.resolve()
    assert restricted_link.is_symlink()
    assert restricted_link.resolve() == restricted.resolve()
    assert ".generated/skills" in restricted_link.resolve().as_posix()

    repeated = installer.install_links(
        loaded,
        ["codex"],
        skills=["public-guide", "restricted-guide"],
        include_local=True,
        user_home=user_home,
    )
    assert [action.status for action in repeated] == [
        "already-linked",
        "already-linked",
    ]


def test_project_install_links_swe_book_skills_for_each_agent(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    source = loaded.root_for("local-only") / "restricted-guide"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("restricted\n", encoding="utf-8")
    project = tmp_path / "consumer"
    project.mkdir()

    actions = installer.install_links(
        loaded,
        ["codex", "claude-code"],
        skills=["restricted-guide"],
        include_local=True,
        project=project,
    )

    assert [action.status for action in actions] == ["linked", "linked"]
    codex_link = project / ".agents/skills/restricted-guide"
    claude_link = project / ".claude/skills/restricted-guide"
    assert codex_link.is_symlink()
    assert codex_link.resolve() == source.resolve()
    assert claude_link.is_symlink()
    assert claude_link.resolve() == source.resolve()


def test_project_install_rejects_skill_root_that_escapes_project(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    source = loaded.root_for("local-only") / "restricted-guide"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("restricted\n", encoding="utf-8")
    project = tmp_path / "consumer"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / ".agents").symlink_to(outside, target_is_directory=True)

    with pytest.raises(GoogleGuideSkillsError, match="escapes the project"):
        installer.install_links(
            loaded,
            ["codex"],
            skills=["restricted-guide"],
            include_local=True,
            project=project,
        )


def test_swe_book_license_acceptance_is_explicit(tmp_path: Path) -> None:
    data = _manifest_data()
    collections = data["collections"]
    assert isinstance(collections, dict)
    collections[installer.SWE_BOOK_COLLECTION_ID] = collections.pop("restricted-guides")
    loaded = _write_manifest(tmp_path / "generator", data)
    prompts: list[str] = []

    def accept(message: str) -> str:
        prompts.append(message)
        return "yes"

    accepted = installer.require_swe_book_license_acceptance(
        loaded,
        accepted=False,
        prompt=accept,
    )
    assert "CC-BY-NC-ND-4.0" in prompts[0]
    assert "https://example.test/licenses/CC-BY-NC-ND-4.0" in accepted
    assert "Do not redistribute generated output" in accepted

    with pytest.raises(GoogleGuideSkillsError, match="was not accepted"):
        installer.require_swe_book_license_acceptance(
            loaded,
            accepted=False,
            prompt=lambda _message: "no",
        )


def test_swe_book_dry_run_plans_missing_generated_source(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    project = tmp_path / "consumer"
    project.mkdir()

    actions = installer.install_links(
        loaded,
        ["codex"],
        skills=["restricted-guide"],
        include_local=True,
        dry_run=True,
        project=project,
    )

    assert actions[0].status == "would-link"
    assert actions[0].destination == project / ".agents/skills/restricted-guide"


def test_user_install_relinks_identical_copy_and_rejects_collisions(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    source = loaded.root_for("committed") / "public-guide"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("same\n", encoding="utf-8")
    user_home = tmp_path / "user"
    destination = user_home / ".codex/skills/public-guide"
    destination.mkdir(parents=True)
    (destination / "SKILL.md").write_text("same\n", encoding="utf-8")
    (source / "references").mkdir()
    (destination / "references").mkdir()

    planned = installer.install_links(
        loaded,
        ["codex"],
        skills=["public-guide"],
        dry_run=True,
        user_home=user_home,
    )
    assert planned[0].status == "would-relink"
    assert destination.is_dir()
    assert not destination.is_symlink()

    actions = installer.install_links(
        loaded,
        ["codex"],
        skills=["public-guide"],
        user_home=user_home,
    )
    assert actions[0].status == "relinked"
    assert destination.is_symlink()
    assert destination.resolve() == source.resolve()

    (source / "SKILL.md").write_text("updated\n", encoding="utf-8")
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "updated\n"

    destination.unlink()
    destination.mkdir()
    (destination / "SKILL.md").write_text("different\n", encoding="utf-8")
    with pytest.raises(GoogleGuideSkillsError, match="different content"):
        installer.install_links(
            loaded,
            ["codex"],
            skills=["public-guide"],
            user_home=user_home,
        )


def test_user_install_restores_identical_copy_when_relink_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    source = loaded.root_for("committed") / "public-guide"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("same\n", encoding="utf-8")
    user_home = tmp_path / "user"
    destination = user_home / ".codex/skills/public-guide"
    destination.mkdir(parents=True)
    (destination / "SKILL.md").write_text("same\n", encoding="utf-8")

    def fail_to_link(_path: Path, _target: Path, target_is_directory: bool = False) -> None:
        del target_is_directory
        raise OSError("fixture link failure")

    monkeypatch.setattr(Path, "symlink_to", fail_to_link)
    with pytest.raises(GoogleGuideSkillsError, match="fixture link failure"):
        installer.install_links(
            loaded,
            ["codex"],
            skills=["public-guide"],
            user_home=user_home,
        )

    assert destination.is_dir()
    assert not destination.is_symlink()
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == "same\n"


def test_user_install_requires_local_generation_and_explicit_opt_in(tmp_path: Path) -> None:
    loaded = _write_manifest(tmp_path / "generator", _manifest_data())
    with pytest.raises(GoogleGuideSkillsError, match="unavailable"):
        installer.install_links(
            loaded,
            ["codex"],
            skills=["restricted-guide"],
            user_home=tmp_path / "user",
        )
    with pytest.raises(GoogleGuideSkillsError, match="all --include-swe-book"):
        installer.install_links(
            loaded,
            ["codex"],
            skills=["restricted-guide"],
            include_local=True,
            user_home=tmp_path / "user",
        )
