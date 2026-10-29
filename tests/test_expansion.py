"""Public-source capture, conversion, pack selection, and install boundaries."""

from __future__ import annotations

import copy
import json
import platform
from dataclasses import replace

import pytest
from test_core import _git, _manifest_data, _write_manifest
from test_core import built_project as built_project

from google_guide_skills import builder, catalog, cli, evals, installer, snapshots, validation
from google_guide_skills.convert import source_to_markdown
from google_guide_skills.errors import (
    BuildError,
    EvaluationError,
    GoogleGuideSkillsError,
    ManifestError,
    SourceError,
)
from google_guide_skills.metrics import metadata_budget_records
from google_guide_skills.packs import select_skills

HTML = """<html><body><nav>Navigation to omit</nav>
<article class="devsite-article"><h1>Public guide</h1>
<devsite-key-takeaways-panel><h2>Page Summary</h2>AI summary</devsite-key-takeaways-panel>
<div class="devsite-article-body"><h2>Useful rule</h2><p>Keep the user's context.</p>
<aside>Keep substantive sidebars.</aside><pre>print("example")</pre>
<div class="nocontent">Feedback widget</div></div></article>
<p>Except as otherwise noted, the content of this page is licensed under the
<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>,
and code samples are licensed under the
<a href="https://www.apache.org/licenses/LICENSE-2.0">Apache 2.0 License</a>.</p>
</body></html>"""


def _web_data() -> dict:
    license_info = {
        "spdx": "CC-BY-4.0",
        "name": "Creative Commons Attribution 4.0 International",
        "url": snapshots.CC_URL,
        "attribution": "Example Authors",
        "audited": "2026-10-28",
        "allow_committed_output": True,
        "evidence_path": "LICENSE.txt",
        "code_samples_spdx": "Apache-2.0",
    }
    return {
        "schema_version": 3,
        "generator": {"python": platform.python_version()},
        "generated_roots": {"committed": "skills", "local_only": ".generated/skills"},
        "repositories": {},
        "web_sources": {
            "public-web": {
                "url": "https://developers.google.com/style/highlights",
                "license": license_info,
                "pages": [
                    {
                        "path": "guide.html",
                        "url": "https://developers.google.com/style/highlights",
                        "selector": "article.devsite-article",
                    }
                ],
            }
        },
        "collections": {
            "web-guides": {
                "web_source": "public-web",
                "distribution": "committed",
                "description": "Public docs",
                "artifacts": [
                    {
                        "name": "web-guide",
                        "title": "Public guide",
                        "description": "Use when applying the public documentation rule.",
                        "tags": ["documentation"],
                        "inputs": ["guide.html"],
                        "excerpts": [
                            {"input": "guide.html", "heading": "Useful rule", "blocks": [0, 1, 2]}
                        ],
                    }
                ],
            }
        },
        "packs": {"legacy": ["web-guide"], "documentation": ["web-guide"]},
    }


@pytest.fixture
def web_project(tmp_path, monkeypatch):
    manifest = _write_manifest(tmp_path, _web_data())
    _git(tmp_path, "init", "--quiet")
    (tmp_path / ".gitignore").write_text(".cache/\n.generated/\n")
    monkeypatch.setattr(snapshots, "_download", lambda url: (HTML.encode(), url))
    snapshots.refresh_snapshot(manifest, "public-web")
    return manifest


def test_web_build_is_offline_deterministic_and_traceable(web_project, monkeypatch):
    manifest = web_project
    monkeypatch.setattr(snapshots, "_download", lambda _: pytest.fail("Build must stay offline"))
    monkeypatch.setattr(builder, "sync", lambda *_: pytest.fail("No Git source to sync"))
    builder.build(manifest)
    skill = manifest.root_for("committed") / "web-guide"
    original = {p.name: p.read_bytes() for p in skill.iterdir()}
    builder.build(manifest, sync_first=False)
    assert original == {p.name: p.read_bytes() for p in skill.iterdir()}
    text = (skill / "SKILL.md").read_text()
    assert "Keep substantive sidebars." in text
    assert 'print("example")' in text
    assert not any(term in text for term in ("AI summary", "Feedback widget", "Navigation to omit"))
    provenance = json.loads((skill / "source.json").read_text())
    assert provenance["source_adapter"] == "google-docs"
    assert "repository" not in provenance
    assert provenance["license"]["code_samples_spdx"] == "Apache-2.0"
    assert not validation.has_errors(validation.validate(manifest))
    record = catalog.catalog_records(manifest)[0]
    assert record["revision"] == provenance["web_source"]["snapshot"]
    assert record["packs"] == ["legacy", "documentation"]
    assert record["code_samples_license"] == "Apache-2.0"
    provenance["web_source"]["snapshot"] = "0" * 64
    (skill / "source.json").write_text(json.dumps(provenance))
    assert any("Web provenance" in issue.message for issue in validation.validate(manifest))


def test_capture_excludes_browser_configuration_and_preserves_guide(tmp_path, monkeypatch):
    manifest = _write_manifest(tmp_path, _web_data())
    html = HTML.replace(
        "<body>",
        '<body><script>window.config = "browser-configuration-marker";</script>'
        "<style>.site-style-marker { color: red; }</style>"
        "<noscript>browser-fallback-marker</noscript>",
    )
    monkeypatch.setattr(snapshots, "_download", lambda url: (html.encode(), url))
    snapshots.refresh_snapshot(manifest, "public-web")
    source = manifest.web_sources["public-web"]
    bundle, _ = snapshots.verify_snapshot(manifest, source)
    captured = (bundle / "guide.html").read_text()
    for marker in ("browser-configuration-marker", "site-style-marker", "browser-fallback-marker"):
        assert marker not in captured
    assert snapshots.article_html(captured, source.pages[0].selector) == snapshots.article_html(
        HTML, source.pages[0].selector
    )
    assert snapshots.CC_URL in captured
    assert snapshots.APACHE_URL in captured


@pytest.mark.parametrize("target", ["guide.html", "licenses/guide.txt", "LICENSE.txt", "lock.json"])
def test_snapshot_tampering_fails_before_replacing_generated_output(web_project, target):
    manifest = web_project
    builder.build(manifest, sync_first=False)
    skill = manifest.root_for("committed") / "web-guide" / "SKILL.md"
    original = skill.read_bytes()
    bundle, _ = snapshots.verify_snapshot(manifest, manifest.web_sources["public-web"])
    path = bundle.parent.parent / "lock.json" if target == "lock.json" else bundle / target
    path.write_text("tampered")
    with pytest.raises(SourceError):
        builder.build(manifest, sync_first=False)
    assert skill.read_bytes() == original
    assert validation.has_errors(validation.validate(manifest))


def test_snapshot_refresh_is_atomic_and_keeps_prior_bundle(web_project, monkeypatch):
    manifest = web_project
    source = manifest.web_sources["public-web"]
    root = snapshots.snapshot_root(manifest, source)
    original_lock = (root / "lock.json").read_bytes()
    source2 = replace(
        source,
        pages=(
            *source.pages,
            replace(
                source.pages[0], path="second.html", url="https://developers.google.com/style/tone"
            ),
        ),
    )
    changed = replace(manifest, web_sources={source.id: source2})

    def download(url):
        if url.endswith("tone"):
            raise SourceError("network unavailable")
        return HTML.replace("user's", "reader's").encode(), url

    monkeypatch.setattr(snapshots, "_download", download)
    with pytest.raises(SourceError, match="network unavailable"):
        snapshots.refresh_snapshot(changed, source.id)
    assert (root / "lock.json").read_bytes() == original_lock
    snapshots.verify_snapshot(manifest, source)
    monkeypatch.setattr(snapshots, "_download", lambda url: (HTML.encode(), url))
    snapshots.refresh_snapshot(manifest, source.id)
    assert (root / "lock.json").read_bytes() == original_lock
    monkeypatch.setattr(
        snapshots, "_download", lambda url: (HTML.replace("user's", "reader's").encode(), url)
    )
    snapshots.refresh_snapshot(manifest, source.id)
    assert (root / "lock.json").read_bytes() != original_lock
    assert len(list((root / "snapshots").iterdir())) == 2


@pytest.mark.parametrize("change", ["license", "code-license", "selector", "title", "encoding"])
def test_capture_requires_license_and_one_article(tmp_path, monkeypatch, change):
    manifest = _write_manifest(tmp_path, _web_data())
    html = HTML
    if change == "license":
        html = html.replace(snapshots.CC_URL, "https://example.test/license")
    if change == "code-license":
        html = html.replace(snapshots.APACHE_URL, "https://example.test/code")
    if change == "selector":
        html += '<article class="devsite-article"><h1>Second</h1></article>'
    if change == "title":
        html = html.replace("<h1>Public guide</h1>", "")
    data = b"\xff" if change == "encoding" else html.encode()
    monkeypatch.setattr(snapshots, "_download", lambda url: (data, url))
    with pytest.raises(SourceError):
        snapshots.refresh_snapshot(manifest, "public-web")
    assert not (tmp_path / "sources").exists()


def test_snapshot_paths_and_changed_manifest_fail_closed(web_project, tmp_path):
    source = web_project.web_sources["public-web"]
    changed = replace(source, pages=(replace(source.pages[0], selector="main"),))
    with pytest.raises(SourceError, match="selector"):
        snapshots.verify_snapshot(web_project, changed)
    bundle, _ = snapshots.verify_snapshot(web_project, source)
    page = bundle / "guide.html"
    outside = tmp_path / "outside.html"
    outside.write_bytes(page.read_bytes())
    page.unlink()
    page.symlink_to(outside)
    with pytest.raises(SourceError, match="symlinks"):
        snapshots.verify_snapshot(web_project, source)
    with pytest.raises(SourceError, match="Unknown"):
        snapshots.refresh_snapshot(web_project, "unknown")
    with pytest.raises(SourceError, match="selector"):
        snapshots.article_html(HTML, "[")


@pytest.mark.parametrize(
    "url",
    [
        "http://developers.google.com/style/tone",
        "https://evil.test/style/tone",
        "https://developers.google.com@evil.test/style/tone",
        "https://sre.google/sre-book/",
        "https://developers.google.com:443/style/tone",
        "https://developers.google.com/style/../other",
        "https://developers.google.com/style/%2e%2e/other",
        "https://developers.google.com/style/tone?q=1",
        "https://developers.google.com/style/tone#section",
        "https://cloud.google.com/private/data",
    ],
)
def test_snapshot_url_boundary_rejects_nonpublic_sources(url):
    with pytest.raises(SourceError):
        snapshots.require_public_url(url)


@pytest.mark.parametrize(
    "case",
    [
        "version",
        "duplicate-page",
        "unsafe-page",
        "unknown-page",
        "both-sources",
        "private-web",
        "license-override",
        "wrong-license",
        "unknown-pack-skill",
        "duplicate-member",
        "missing-pack",
        "empty-pack",
        "unknown-adapter",
        "unassigned-skill",
    ],
)
def test_manifest_v3_rejects_ambiguous_or_unsafe_inputs(tmp_path, case):
    data = _web_data()
    source = data["web_sources"]["public-web"]
    collection = data["collections"]["web-guides"]
    if case == "version":
        data["schema_version"] = 2
    elif case == "duplicate-page":
        source["pages"].append(copy.deepcopy(source["pages"][0]))
    elif case == "unsafe-page":
        source["pages"][0]["path"] = "../escape.html"
    elif case == "unknown-page":
        collection["artifacts"][0]["inputs"] = ["other.html"]
    elif case == "both-sources":
        collection["repository"] = "example"
    elif case == "private-web":
        source["pages"][0]["url"] = "https://sre.google/sre-book/"
    elif case == "license-override":
        collection["license_override"] = copy.deepcopy(source["license"])
    elif case == "wrong-license":
        source["license"]["spdx"] = "CC-BY-NC-ND-4.0"
    elif case == "unknown-pack-skill":
        data["packs"]["legacy"] = ["unknown"]
    elif case == "duplicate-member":
        data["packs"]["legacy"].append("web-guide")
    elif case == "missing-pack":
        data["packs"].pop("legacy")
    elif case == "empty-pack":
        data["packs"]["legacy"] = []
    elif case == "unknown-adapter":
        data["repositories"] = _manifest_data("0" * 40)["repositories"]
        data["repositories"]["example-repo"]["adapter"] = "execute-template"
    elif case == "unassigned-skill":
        extra = copy.deepcopy(collection["artifacts"][0])
        extra["name"] = "unassigned"
        collection["artifacts"].append(extra)
    with pytest.raises(ManifestError):
        _write_manifest(tmp_path, data)


@pytest.mark.parametrize(
    "adapter,frontmatter",
    [
        ("aip", "state: draft"),
        ("aip", "state: reviewing"),
        ("dora", "title: Test\ndraft: true"),
        ("dora", "title: Test"),
        ("dora", "draft: false"),
        ("aip", "[broken"),
    ],
)
def test_source_frontmatter_cannot_import_drafts(tmp_path, adapter, frontmatter):
    path = tmp_path / "source.md"
    path.write_text(f"---\n{frontmatter}\n---\n# Title\n\nRule.\n")
    with pytest.raises(BuildError):
        source_to_markdown(path, adapter=adapter)


def test_book_adapter_retains_nested_headings_and_sidebars(tmp_path):
    path = tmp_path / "chapter.html"
    path.write_text(
        '<h2>Chapter 4</h2><section data-type="chapter"><h1>Design</h1>'
        "<section><h1>Requirements</h1><p>Specific requirement.</p>"
        "<aside><p>Useful sidebar.</p></aside></section></section>"
    )
    markdown, mode = source_to_markdown(path, adapter="html-book")
    assert markdown.startswith("# Design\n")
    assert "## Requirements" in markdown
    assert "Useful sidebar." in markdown
    assert "Chapter 4" not in markdown
    assert mode == "book-chapter-to-markdown"
    path.write_text('<section data-type="chapter"><h1>One</h1><h1>Two</h1></section>')
    with pytest.raises(BuildError):
        source_to_markdown(path, adapter="html-book")


def test_git_adapters_verify_extra_license_evidence_and_reject_templates(built_project):
    manifest, checkout = built_project
    path = checkout / "guide.md"
    path.write_text(
        "---\ntitle: Upstream\ndraft: false\n---\nRule.\n\n"
        '{{< dora_callout title="Context" >}}\n\nA useful sidebar.\n\n'
        "{{< /dora_callout >}}\n"
    )
    (checkout / "README.md").write_text("Documentation is CC BY 4.0.\n")
    _git(checkout, "add", ".")
    _git(checkout, "commit", "-qm", "published fixture")
    repo = manifest.repositories["example-repo"]
    repo = replace(
        repo,
        revision=_git(checkout, "rev-parse", "HEAD"),
        adapter="dora",
        license=replace(repo.license, evidence_paths=("README.md",)),
    )
    manifest = replace(manifest, repositories={repo.id: repo})
    collection = manifest.collections["public-guides"]
    artifact = collection.artifacts[0]
    artifact = replace(artifact, excerpts=(replace(artifact.excerpts[0], blocks=(0, 1, 2)),))
    builder.build_skill(manifest, collection, artifact)
    skill = manifest.root_for("committed") / artifact.name
    assert "A useful sidebar." in (skill / "SKILL.md").read_text()
    assert "{{<" not in (skill / "SKILL.md").read_text()
    assert "Additional license evidence: README.md" in (skill / "LICENSE.txt").read_text()
    (checkout / "README.md").write_text("Changed terms")
    with pytest.raises(BuildError):
        builder.build_skill(manifest, collection, artifact)
    path.write_text('---\ntitle: Upstream\ndraft: false\n---\n{{< execute "bad" >}}\n')
    with pytest.raises(BuildError, match="unsupported template"):
        builder._selected_excerpts(
            replace(artifact, excerpts=(replace(artifact.excerpts[0], blocks=(0,)),)),
            (path,),
            checkout,
            "dora",
        )


def test_packs_union_default_and_unknown_names(web_project):
    manifest = web_project
    assert select_skills(manifest) == ["web-guide"]
    assert select_skills(manifest, ["web-guide"], ["documentation", "legacy"]) == ["web-guide"]
    assert select_skills(manifest, []) == []
    assert installer.selected_install_skills(manifest, None, ["documentation"]) == (
        ["web-guide"],
        [],
    )
    with pytest.raises(GoogleGuideSkillsError, match="Unknown pack"):
        select_skills(manifest, packs=["missing"])
    with pytest.raises(GoogleGuideSkillsError, match="Unknown skills"):
        select_skills(manifest, ["missing"])


def test_declared_default_includes_new_skills_without_expanding_explicit_selections(web_project):
    collection = web_project.collections["web-guides"]
    extra = replace(collection.artifacts[0], name="additional-guide")
    manifest = replace(
        web_project,
        collections={collection.id: replace(collection, artifacts=(*collection.artifacts, extra))},
        packs={"default": ("web-guide", "additional-guide"), "legacy": ("web-guide",)},
    )
    assert installer.selected_install_skills(manifest, None) == (
        ["additional-guide", "web-guide"],
        [],
    )
    assert select_skills(manifest, packs=["legacy"]) == ["web-guide"]
    assert select_skills(manifest, ["additional-guide"]) == ["additional-guide"]


def test_install_budget_checks_existing_union_and_real_paths_before_mutation(web_project, tmp_path):
    manifest = web_project
    builder.build(manifest, sync_first=False)
    home = tmp_path / "home"
    existing = home / ".claude/skills/unrelated/SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(
        "---\nname: unrelated\ndescription: " + "context " * 1000 + "\n---\nKeep me.\n"
    )
    before = existing.read_bytes()
    with pytest.raises(GoogleGuideSkillsError, match="No skills were installed or removed"):
        installer.install_links(manifest, ["codex", "claude-code"], ["web-guide"], user_home=home)
    assert not (home / ".codex").exists()
    assert existing.read_bytes() == before
    artifact = manifest.collections["web-guides"].artifacts[0]
    collection = replace(
        manifest.collections["web-guides"], artifacts=(replace(artifact, description="x" * 7800),)
    )
    large = replace(manifest, collections={collection.id: collection})
    long_home = tmp_path / ("long" * 50)
    with pytest.raises(GoogleGuideSkillsError, match="limit 8000"):
        installer.install_links(large, ["codex"], ["web-guide"], user_home=long_home, dry_run=True)
    assert not long_home.exists()
    assert metadata_budget_records([("x", "short")], install_root="/short")["headroom_chars"] > 0


@pytest.mark.parametrize("overflow", [False, True])
def test_install_budgets_existing_skill_with_aliased_folder(web_project, tmp_path, overflow):
    builder.build(web_project, sync_first=False)
    home = tmp_path / "home"
    existing = home / ".codex/skills/gstack-helper/SKILL.md"
    existing.parent.mkdir(parents=True)
    description = "context " * 1000 if overflow else "Use the helper."
    existing.write_text(f"---\nname: helper\ndescription: {description}\n---\nKeep me.\n")
    original = existing.read_bytes()
    destination = home / ".codex/skills/web-guide"
    if overflow:
        with pytest.raises(GoogleGuideSkillsError, match="limit 8000"):
            installer.install_links(web_project, ["codex"], ["web-guide"], user_home=home)
        assert not destination.exists()
    else:
        installer.install_links(web_project, ["codex"], ["web-guide"], user_home=home)
        assert destination.is_symlink()
        assert (destination / "SKILL.md").is_file()
    assert existing.read_bytes() == original


def test_pack_evaluation_records_selection_and_rejects_mismatched_cases(
    web_project, tmp_path, monkeypatch
):
    # /ship coverage audit extension.
    # Value: protects=CLI pack plans contain only cases from the selected pack;
    # fails_when=CLI drops pack filtering or chooses the all profile;
    # why_new=existing assertions call the evaluation API without CLI selection;
    # seam=none; no_claim=live routing quality; fixture cases replace the case file.
    manifest = web_project
    builder.build(manifest, sync_first=False)
    case = evals.EvalCase("web-case", "smoke", "validation", "Apply the rule.", ("web-guide",), ())
    report, _ = evals.run_evaluation(
        manifest,
        [case],
        mode="triggers",
        agents=["codex"],
        profile="pack",
        packs=["documentation"],
        dry_run=True,
        results_root=tmp_path / "results",
    )
    assert report["packs"] == ["documentation"]
    assert report["records"][0]["status"] == "planned"
    run = evals._install_profile(
        manifest, tmp_path / "project", "codex", "pack", case, ("documentation",)
    )
    assert run["installed_skills"] == ["web-guide"]
    assert run["hashes_verified"] is True
    for cases, packs in [
        ([case], None),
        ([replace(case, expected_skills=("outside",))], ["documentation"]),
    ]:
        with pytest.raises(EvaluationError):
            evals.run_evaluation(
                manifest,
                cases,
                mode="triggers",
                agents=["codex"],
                profile="pack",
                packs=packs,
                dry_run=True,
            )
    monkeypatch.setattr(cli, "_manifest", lambda _: manifest)
    monkeypatch.setattr(
        cli,
        "load_cases",
        lambda _: [case, replace(case, id="outside-case", expected_skills=("outside",))],
    )
    plans = tmp_path / "cli-results"
    assert (
        cli.main(
            [
                "eval",
                "triggers",
                "--pack",
                "documentation",
                "--agent",
                "codex",
                "--results-root",
                str(plans),
            ]
        )
        == 0
    )
    plan = json.loads(next(plans.glob("*/report.json")).read_text())
    assert plan["profile"] == "pack"
    assert plan["packs"] == ["documentation"]
    assert [record["case_id"] for record in plan["records"]] == ["web-case"]
    assert cli.main(["snapshot", "--source", "public-web"]) == 0
    assert cli.main(["install", "--project", str(tmp_path), "--pack", "missing", "--dry-run"]) == 2


@pytest.mark.parametrize("metadata", ["no frontmatter", "---\nname: helper\n---\nBody"])
def test_unbudgetable_existing_skill_stops_all_install_mutation(web_project, tmp_path, metadata):
    # Generated by /ship coverage audit.
    # Value: protects=invalid existing metadata stops every agent install without mutation;
    # fails_when=preflight ignores unreadable metadata or runs after the first install;
    # why_new=existing budget tests cover valid oversized metadata only;
    # seam=none; no_claim=concurrent filesystem changes after preflight.
    builder.build(web_project, sync_first=False)
    home = tmp_path / "home"
    existing = home / ".claude/skills/helper/SKILL.md"
    existing.parent.mkdir(parents=True)
    existing.write_text(metadata)
    with pytest.raises(GoogleGuideSkillsError, match="Cannot budget installed skill"):
        installer.install_links(
            web_project, ["codex", "claude-code"], ["web-guide"], user_home=home
        )
    assert not (home / ".codex").exists()
    assert not (existing.parent.parent / "web-guide").exists()
    assert existing.read_text() == metadata


def test_downloader_limits_content_and_redirects(monkeypatch):
    from email.message import Message
    from types import SimpleNamespace

    class Response:
        def __init__(self, data=None, content_type="text/html", url=None):
            self.data = HTML.encode() if data is None else data
            self.url = url or "https://developers.google.com/style/tone"
            self.headers = Message()
            self.headers["Content-Type"] = content_type

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def geturl(self):
            return self.url

        def read(self, limit):
            return self.data[:limit]

    responses = [
        Response(),
        Response(content_type="application/pdf"),
        Response(data=b"a" * (snapshots.MAX_PAGE_BYTES + 1)),
        Response(url="https://evil.test/style/tone"),
    ]
    opener = SimpleNamespace(open=lambda *_args, **_kwargs: responses.pop(0))
    monkeypatch.setattr(snapshots.urllib.request, "build_opener", lambda *_: opener)
    url = "https://developers.google.com/style/tone"
    assert snapshots._download(url) == (HTML.encode(), url)
    for message in ("Expected HTML", "page limit", "approved public"):
        with pytest.raises(SourceError, match=message):
            snapshots._download(url)

    def failing_open(*_args, **_kwargs):
        raise OSError("offline")

    opener.open = failing_open
    with pytest.raises(SourceError, match="Could not capture"):
        snapshots._download(url)
    handler = snapshots._PublicRedirects()
    request = snapshots.urllib.request.Request(url)
    with pytest.raises(SourceError):
        handler.redirect_request(request, None, 302, "Found", {}, "https://evil.test/page")
    redirected = handler.redirect_request(request, None, 302, "Found", {}, url)
    assert redirected.full_url == url


def test_web_input_hash_and_pack_routing_are_validated(web_project):
    manifest = web_project
    builder.build(manifest, sync_first=False)
    path = manifest.root_for("committed") / "web-guide/source.json"
    provenance = json.loads(path.read_text())
    provenance["inputs"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(provenance))
    assert any("Web input provenance" in issue.message for issue in validation.validate(manifest))
    case = evals.EvalCase("web-case", "smoke", "validation", "Apply the rule.", ("web-guide",), ())
    expected, forbidden = evals._case_expectations(
        case, "pack", frozenset({"web-guide", "unrelated"})
    )
    assert expected == ("web-guide",)
    assert forbidden == ("unrelated",)
    groups = evals._routing_groups([{"stage": "smoke", "profile": "pack"}])
    assert len(groups["direct"]) == 1


@pytest.mark.parametrize(
    "field,value", [("schema_version", []), ("adapter", []), ("code_samples_spdx", {})]
)
def test_manifest_invalid_types_produce_actionable_errors(tmp_path, field, value):
    data = _web_data()
    if field == "schema_version":
        data[field] = value
    elif field == "adapter":
        data["repositories"] = _manifest_data("0" * 40)["repositories"]
        data["repositories"]["example-repo"][field] = value
    else:
        data["web_sources"]["public-web"]["license"][field] = value
    with pytest.raises(ManifestError):
        _write_manifest(tmp_path, data)


@pytest.mark.parametrize("linked", [False, True])
def test_nested_existing_skills_are_budgeted_before_mutating_either_agent(
    web_project, tmp_path, linked
):
    # Value: protects=nested entries with repeated folder names count before either install;
    # fails_when=recursive or linked discovery omits entries or collapses their paths;
    # why_new=existing overflow cases contain only top-level skills;
    # seam=none; no_claim=other client skill roots outside the target directory.
    builder.build(web_project, sync_first=False)
    home = tmp_path / "home"
    root = home / ".claude/skills"
    root.mkdir(parents=True)
    collection = tmp_path / "shared" if linked else root / "collection"
    collection.mkdir()
    if linked:
        (root / "collection").symlink_to(collection, target_is_directory=True)
    for group in ("one", "two"):
        skill = collection / group / "helper" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            f"---\nname: {group}\ndescription: " + "context " * 500 + "\n---\nKeep me.\n"
        )
    before = {str(p): p.read_bytes() for p in collection.glob("*/helper/SKILL.md")}
    with pytest.raises(GoogleGuideSkillsError, match="limit 8000"):
        installer.install_links(
            web_project, ["codex", "claude-code"], ["web-guide"], user_home=home
        )
    assert not (home / ".codex").exists()
    assert not (root / "web-guide").exists()
    assert {str(p): p.read_bytes() for p in collection.glob("*/helper/SKILL.md")} == before


def test_install_follows_nested_skill_links_but_skips_cycles_and_hidden_dirs(web_project, tmp_path):
    # Value: protects=finite discovery of visible skills in linked collections;
    # fails_when=a cycle prevents completion or hidden invalid metadata blocks installation;
    # why_new=nested overflow cases contain neither cycles nor hidden directories;
    # seam=none; no_claim=concurrent filesystem mutation.
    builder.build(web_project, sync_first=False)
    home = tmp_path / "home"
    root = home / ".codex/skills"
    root.mkdir(parents=True)
    collection = tmp_path / "shared"
    collection.mkdir()
    (root / "collection").symlink_to(collection, target_is_directory=True)
    (collection / "cycle").symlink_to(collection, target_is_directory=True)
    (collection / "SKILL.md").write_text(
        "---\nname: collection\ndescription: Use this collection.\n---\nBody\n"
    )
    hidden = collection / ".hidden/SKILL.md"
    hidden.parent.mkdir()
    hidden.write_text("not skill metadata")
    installer.install_links(web_project, ["codex"], ["web-guide"], user_home=home)
    assert (root / "web-guide").is_symlink()
    assert (collection / "cycle").is_symlink()
    assert hidden.read_text() == "not skill metadata"


def test_install_discovery_limit_stops_before_mutation(web_project, tmp_path, monkeypatch):
    # Value: protects=bounded scanning fails closed before changing target directories;
    # fails_when=discovery exceeds its cap silently or installation precedes scanning;
    # why_new=overflow tests limit metadata size rather than traversal size;
    # seam=existing policy constant; no_claim=latency of filesystem operations.
    builder.build(web_project, sync_first=False)
    home = tmp_path / "home"
    root = home / ".codex/skills"
    (root / "collection/helper").mkdir(parents=True)
    monkeypatch.setattr(installer, "MAX_EXISTING_SKILL_ENTRIES", 1)
    with pytest.raises(GoogleGuideSkillsError, match="scan exceeds 1 entries"):
        installer.install_links(
            web_project, ["claude-code", "codex"], ["web-guide"], user_home=home
        )
    assert not (home / ".claude").exists()
    assert not (root / "web-guide").exists()


def test_snapshot_without_sample_license_does_not_claim_an_apache_grant(web_project, monkeypatch):
    # Value: protects=license evidence includes only declared and verified grants;
    # fails_when=content-only sources acquire an unsupported code-sample license;
    # why_new=existing web snapshots all declare the Apache code-sample grant;
    # seam=existing downloader boundary; no_claim=independent legal interpretation.
    source = web_project.web_sources["public-web"]
    source = replace(source, license=replace(source.license, code_samples_spdx=None))
    manifest = replace(web_project, web_sources={source.id: source})
    html = (
        '<article class="devsite-article"><h1>Guide</h1><p>A rule.</p></article>'
        "<p>The content of this page is licensed under "
        f'<a href="{snapshots.CC_URL}">CC BY 4.0</a>.</p>'
    )
    monkeypatch.setattr(snapshots, "_download", lambda url: (html.encode(), url))
    snapshots.refresh_snapshot(manifest, source.id)
    bundle, _ = snapshots.verify_snapshot(manifest, source)
    evidence = (bundle / "LICENSE.txt").read_text()
    assert snapshots.CC_URL in evidence
    assert snapshots.APACHE_URL not in evidence
    assert "Code samples:" not in evidence
