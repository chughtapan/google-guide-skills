"""Contracts over the checked-in corpus, generated artifacts, and release metadata."""

from __future__ import annotations

import json
import subprocess
import tomllib
from collections import defaultdict
from pathlib import Path

from google_guide_skills import __version__
from google_guide_skills.evals import load_cases, score_output
from google_guide_skills.git_safe import command as git_command
from google_guide_skills.git_safe import environment as git_environment
from google_guide_skills.manifest import load_manifest
from google_guide_skills.metrics import (
    CODEX_FALLBACK_METADATA_CHARS,
    MIN_SUPPORTED_INSTALL_ROOT_CHARS,
    metadata_budget,
)

ROOT = Path(__file__).resolve().parents[1]


def test_real_corpus_and_eval_matrix_cannot_drift_silently() -> None:
    manifest = load_manifest(ROOT / "corpus.yaml")
    cases = load_cases(manifest)
    committed = {artifact.name for collection, artifact in manifest.artifacts(include_local=False)}
    local = {
        artifact.name
        for collection, artifact in manifest.artifacts(include_local=True)
        if collection.distribution == "local-only"
    }

    smoke = [case for case in cases if case.stage == "smoke"]
    controls = [case for case in cases if case.stage == "controls"]
    local_smoke = [case for case in cases if case.stage == "local-smoke"]
    assert len(smoke) == len(committed) == 16
    assert [skill for case in smoke for skill in case.expected_skills] == list(
        dict.fromkeys(skill for case in smoke for skill in case.expected_skills)
    )
    assert {skill for case in smoke for skill in case.expected_skills} == committed
    assert len(controls) == len(committed) == 16
    assert {skill for case in controls for skill in case.expected_skills} == committed
    assert all("{invocation}" in case.prompt for case in controls)
    assert len(local_smoke) == len(local) == 8
    assert {skill for case in local_smoke for skill in case.expected_skills} == local
    representative = [case for case in cases if case.stage == "representative"]
    counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for case in representative:
        if case.expected_skills:
            skill = case.expected_skills[0]
            polarity = "positive"
        else:
            skill = case.forbidden_skills[0]
            polarity = "negative"
        counts[skill][polarity][case.split] += 1
    assert set(counts) == {
        "google-python-style",
        "google-code-review-reviewer",
        "google-documentation-guide",
    }
    for polarities in counts.values():
        assert polarities["positive"] == {"train": 6, "validation": 4}
        assert polarities["negative"] == {"train": 6, "validation": 4}


def test_real_corpus_path_policies_and_metadata_budget_are_enforced() -> None:
    manifest = load_manifest(ROOT / "corpus.yaml")
    policies = {
        (policy.repository, policy.pattern, policy.required_distribution)
        for policy in manifest.source_path_policies
    }
    assert ("abseil", "resources/swe-book/html/**", "local-only") in policies
    assert ("styleguide", "Rguide.md", "catalog-only") in policies

    skill_dirs = sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())
    budget = metadata_budget(skill_dirs)
    assert budget["skills"] == 16
    assert int(budget["maximum_install_root_chars"]) >= MIN_SUPPORTED_INSTALL_ROOT_CHARS
    assert int(budget["codex_list_chars"]) <= CODEX_FALLBACK_METADATA_CHARS
    eval_budget = metadata_budget(skill_dirs, install_root="/w/.agents/skills")
    assert eval_budget["reference_install_root"] == "/w/.agents/skills"
    assert int(eval_budget["codex_list_chars"]) <= CODEX_FALLBACK_METADATA_CHARS
    recorded = json.loads((ROOT / "catalog" / "tokens.json").read_text(encoding="utf-8"))
    assert recorded["metadata_budget"] == budget

    go_artifact = next(
        artifact
        for _collection, artifact in manifest.artifacts(include_local=False)
        if artifact.name == "google-go-style"
    )
    assert go_artifact.recipe == "recipes/google-go-style.md"
    go_skill = ROOT / "skills/google-go-style/SKILL.md"
    assert len(go_skill.read_text(encoding="utf-8").splitlines()) < 500
    assert not (go_skill.parent / "references").exists()


def test_go_quality_rubric_matches_guide_headings() -> None:
    manifest = load_manifest(ROOT / "corpus.yaml")
    case = next(case for case in load_cases(manifest) if case.id == "smoke-go-style")
    output = "API names\nReturned errors\nPackage comments\nReadable tests"

    assert score_output(output, case.rubric) == (4, 4)


def test_release_version_and_generated_provenance_are_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert project["project"]["version"] == version == __version__
    for source_path in sorted((ROOT / "skills").glob("*/source.json")):
        provenance = json.loads(source_path.read_text(encoding="utf-8"))
        assert provenance["generated_by"] == f"google-guide-skills/{version}"


def test_historical_guides_are_cataloged_not_packaged() -> None:
    manifest = load_manifest(ROOT / "corpus.yaml")
    cataloged = {item.id: item.status for item in manifest.catalog_only}
    assert cataloged["google-angularjs-style"] == "historical-guide-not-packaged"
    assert cataloged["google-json-style"] == "historical-guide-not-packaged"
    assert not (ROOT / "skills/google-angularjs-style").exists()
    assert not (ROOT / "skills/google-json-style").exists()


def test_local_only_output_is_ignored_and_untracked() -> None:
    ignored = subprocess.run(
        git_command("check-ignore", "--quiet", "--", ".generated/skills"),
        cwd=ROOT,
        env=git_environment(),
        check=False,
    )
    assert ignored.returncode == 0
    tracked = subprocess.run(
        git_command("ls-files", "--", ".generated"),
        cwd=ROOT,
        env=git_environment(),
        text=True,
        capture_output=True,
        check=True,
    )
    assert tracked.stdout == ""
