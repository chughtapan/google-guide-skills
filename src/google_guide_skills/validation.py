"""Validate skill structure, provenance, size, and distribution policy."""

from __future__ import annotations

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path

import tiktoken
import yaml

from . import __version__
from .errors import GoogleGuideSkillsError
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .metrics import (
    CODEX_FALLBACK_METADATA_CHARS,
    MIN_SUPPORTED_INSTALL_ROOT_CHARS,
    metadata_budget,
)
from .models import Artifact, Collection, Manifest, ValidationIssue
from .path_policy import require_safe_project_path
from .project_license import (
    PROJECT_LICENSE_SHA256,
    WRAPPER_LICENSE_FILENAME,
    wrapper_license_metadata,
)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", flags=re.DOTALL)
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _issue(severity: str, path: Path, root: Path, message: str) -> ValidationIssue:
    try:
        display = path.relative_to(root).as_posix()
    except ValueError:
        display = str(path)
    return ValidationIssue(severity=severity, path=display, message=message)


def _parse_skill(path: Path, root: Path) -> tuple[dict[str, object], str, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, "", [_issue("error", path, root, f"Cannot read file: {exc}")]
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, [_issue("error", path, root, "Missing YAML frontmatter")]
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return {}, match.group(2), [_issue("error", path, root, f"Invalid frontmatter: {exc}")]
    if not isinstance(metadata, dict):
        issues.append(_issue("error", path, root, "Frontmatter must be a mapping"))
        return {}, match.group(2), issues
    return metadata, match.group(2), issues


def _validate_links(markdown_path: Path, project_root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    text = markdown_path.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        target = target.split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        resolved = (markdown_path.parent / target).resolve()
        if not resolved.is_relative_to(project_root.resolve()):
            issues.append(
                _issue("error", markdown_path, project_root, f"Link escapes project root: {target}")
            )
        elif not resolved.exists():
            issues.append(
                _issue("error", markdown_path, project_root, f"Broken local link: {target}")
            )
    return issues


def _is_git_ignored(path: Path, project_root: Path) -> bool:
    completed = subprocess.run(
        git_command("check-ignore", "--quiet", "--", str(path)),
        cwd=project_root,
        env=git_environment(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def _tracked_files_under(path: Path, project_root: Path) -> list[str]:
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        return [str(path)]
    completed = subprocess.run(
        git_command("ls-files", "--", relative.as_posix()),
        cwd=project_root,
        env=git_environment(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode:
        return []
    return [line for line in completed.stdout.splitlines() if line]


def _local_boundary_issues(manifest: Manifest) -> list[ValidationIssue]:
    root = manifest.project_root
    local_root = manifest.root_for("local-only")
    issues: list[ValidationIssue] = []
    if not _is_git_ignored(local_root, root):
        issues.append(
            _issue("error", local_root, root, "The local-only generated root is not ignored by git")
        )
    tracked = _tracked_files_under(local_root, root)
    if tracked:
        issues.append(
            _issue(
                "error",
                local_root,
                root,
                f"Local-only generated output is tracked by git: {', '.join(tracked[:5])}",
            )
        )
    return issues


def _frontmatter_issues(skill_dir: Path, project_root: Path) -> list[ValidationIssue]:
    skill_path = skill_dir / "SKILL.md"
    metadata, body, issues = _parse_skill(skill_path, project_root)
    unknown_fields = sorted(set(metadata) - {"name", "description"})
    if unknown_fields:
        issues.append(
            _issue(
                "error",
                skill_path,
                project_root,
                f"Frontmatter has unsupported fields: {', '.join(unknown_fields)}",
            )
        )
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
        issues.append(_issue("error", skill_path, project_root, "Invalid skill name"))
    elif name != skill_dir.name:
        issues.append(
            _issue(
                "error",
                skill_path,
                project_root,
                f"Skill name {name!r} does not match directory {skill_dir.name!r}",
            )
        )
    if not isinstance(description, str) or not description.strip():
        issues.append(_issue("error", skill_path, project_root, "Missing skill description"))
    elif len(description) > 1024:
        issues.append(
            _issue("error", skill_path, project_root, "Skill description exceeds 1024 characters")
        )
    if not body.strip():
        issues.append(_issue("error", skill_path, project_root, "Skill body is empty"))
    return issues


def _skill_size_issues(
    skill_path: Path, project_root: Path, encoding: tiktoken.Encoding
) -> list[ValidationIssue]:
    text = skill_path.read_text(encoding="utf-8")
    line_count = len(text.splitlines())
    token_count = len(encoding.encode(text))
    issues: list[ValidationIssue] = []
    if line_count > 500:
        issues.append(
            _issue(
                "error",
                skill_path,
                project_root,
                f"Skill has {line_count} lines; this pack requires at most 500",
            )
        )
    if token_count > 5000:
        issues.append(
            _issue(
                "error",
                skill_path,
                project_root,
                f"Skill has {token_count} tokens; this pack requires at most 5000",
            )
        )
    return issues


def _skill_content_issues(
    skill_dir: Path, project_root: Path, encoding: tiktoken.Encoding
) -> list[ValidationIssue]:
    skill_path = skill_dir / "SKILL.md"
    if not skill_path.is_file():
        return [_issue("error", skill_dir, project_root, "Missing SKILL.md")]
    issues = _frontmatter_issues(skill_dir, project_root)
    issues.extend(_skill_size_issues(skill_path, project_root, encoding))
    issues.extend(_validate_links(skill_path, project_root))
    references = skill_dir / "references"
    if references.exists():
        issues.append(
            _issue(
                "error",
                references,
                project_root,
                "Generated skills must be self-contained; references are not allowed",
            )
        )
    return issues


def _artifact_provenance_checks(
    manifest: Manifest,
    provenance: dict[str, object],
    expected_collection: Collection,
    artifact: Artifact,
    expected_recipe: dict[str, str] | None,
) -> tuple[tuple[bool, str], ...]:
    repository = manifest.repositories[expected_collection.repository]
    return (
        (
            provenance.get("collection") == expected_collection.id,
            "Provenance collection does not own this artifact",
        ),
        (
            provenance.get("generated_by") == f"google-guide-skills/{__version__}",
            "Generated provenance version is stale",
        ),
        (
            provenance.get("repository")
            == {"id": repository.id, "url": repository.url, "revision": repository.revision},
            "Repository provenance does not match corpus.yaml",
        ),
        (
            provenance.get("license") == manifest.license_for(expected_collection).to_dict(),
            "License provenance does not match corpus.yaml",
        ),
        (
            provenance.get("supplemental_licenses", [])
            == [supplemental.to_dict() for supplemental in artifact.supplemental_licenses],
            "Supplemental license provenance does not match corpus.yaml",
        ),
        (
            provenance.get("recipe") == expected_recipe,
            "Recipe provenance does not match corpus.yaml",
        ),
        (
            provenance.get("excerpts", []) == [excerpt.to_dict() for excerpt in artifact.excerpts],
            "Excerpt provenance does not match corpus.yaml",
        ),
        (
            provenance.get("rendering")
            == ("curated" if expected_recipe is not None else "source-excerpts"),
            "Rendering provenance does not match corpus.yaml",
        ),
        (
            provenance.get("license_note") == artifact.license_note,
            "Artifact license note does not match corpus.yaml",
        ),
        (
            provenance.get("wrapper_license") == wrapper_license_metadata(),
            "Wrapper license provenance does not match the project policy",
        ),
    )


def _runtime_is_current(manifest: Manifest, provenance: dict[str, object]) -> bool:
    runtime = provenance.get("generator_runtime")
    return (
        isinstance(runtime, dict)
        and runtime.get("python") == manifest.canonical_python
        and all(
            isinstance(runtime.get(name), str) and runtime.get(name)
            for name in ("beautifulsoup4", "lxml", "markdownify")
        )
    )


def _artifact_license_file_issues(
    manifest: Manifest, skill_dir: Path, artifact: Artifact
) -> list[ValidationIssue]:
    root = manifest.project_root
    issues: list[ValidationIssue] = []
    wrapper_path = skill_dir / WRAPPER_LICENSE_FILENAME
    if (
        wrapper_path.is_symlink()
        or not wrapper_path.is_file()
        or sha256(wrapper_path.read_bytes()).hexdigest() != PROJECT_LICENSE_SHA256
    ):
        issues.append(
            _issue(
                "error",
                wrapper_path,
                root,
                "Project-authored wrapper Apache license is missing or stale",
            )
        )
    for supplemental in artifact.supplemental_licenses:
        path = skill_dir / f"LICENSE-{supplemental.spdx}.txt"
        if (
            path.is_symlink()
            or not path.is_file()
            or sha256(path.read_bytes()).hexdigest() != supplemental.sha256
        ):
            issues.append(
                _issue("error", path, root, "Supplemental source license is missing or stale")
            )
    return issues


def _artifact_provenance_issues(
    manifest: Manifest,
    skill_dir: Path,
    provenance: dict[str, object],
    expected_collection: Collection,
    artifact: Artifact,
) -> list[ValidationIssue]:
    root = manifest.project_root
    provenance_path = skill_dir / "source.json"
    expected_recipe: dict[str, str] | None = None
    recipe_issues: list[ValidationIssue] = []
    if artifact.recipe is not None:
        try:
            recipe_path = require_safe_project_path(
                manifest.project_root,
                manifest.project_root / artifact.recipe,
                context="Skill recipe",
                error_type=GoogleGuideSkillsError,
            )
        except GoogleGuideSkillsError:
            recipe_path = manifest.project_root / artifact.recipe
            recipe_issues.append(
                _issue("error", recipe_path, root, "Skill recipe is missing or unsafe")
            )
        else:
            if recipe_path.is_symlink() or not recipe_path.is_file():
                recipe_issues.append(
                    _issue("error", recipe_path, root, "Skill recipe is missing or unsafe")
                )
            else:
                expected_recipe = {
                    "path": artifact.recipe,
                    "sha256": sha256(recipe_path.read_bytes()).hexdigest(),
                }
    checks = _artifact_provenance_checks(
        manifest,
        provenance,
        expected_collection,
        artifact,
        expected_recipe,
    )
    issues = [
        _issue("error", provenance_path, root, message) for passed, message in checks if not passed
    ]
    issues.extend(recipe_issues)
    if not _runtime_is_current(manifest, provenance):
        issues.append(
            _issue(
                "error",
                provenance_path,
                root,
                "Generator runtime provenance is missing or stale",
            )
        )
    issues.extend(_artifact_license_file_issues(manifest, skill_dir, artifact))
    return issues


def _provenance_file_issues(
    provenance_path: Path, license_path: Path, project_root: Path
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if provenance_path.is_symlink() or not provenance_path.is_file():
        issues.append(_issue("error", provenance_path, project_root, "Missing source metadata"))
    if license_path.is_symlink() or not license_path.is_file():
        issues.append(_issue("error", license_path, project_root, "Missing source license"))
    return issues


def _load_provenance(
    provenance_path: Path, project_root: Path
) -> tuple[dict[str, object] | None, list[ValidationIssue]]:
    try:
        value = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [
            _issue("error", provenance_path, project_root, f"Invalid source metadata: {exc}")
        ]
    if not isinstance(value, dict):
        return None, [
            _issue("error", provenance_path, project_root, "Source metadata must be an object")
        ]
    return value, []


def _recorded_provenance_issues(
    provenance: dict[str, object],
    provenance_path: Path,
    skill_name: str,
    distribution: str,
    project_root: Path,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    recorded = provenance.get("distribution")
    if recorded != distribution:
        issues.append(
            _issue(
                "error",
                provenance_path,
                project_root,
                f"Recorded distribution {recorded!r} does not match {distribution!r}",
            )
        )
    if provenance.get("artifact") != skill_name:
        issues.append(
            _issue(
                "error",
                provenance_path,
                project_root,
                "Provenance artifact does not match the skill directory",
            )
        )
    return issues


def _collection_boundary_issues(
    manifest: Manifest,
    distribution: str,
    provenance: dict[str, object],
    provenance_path: Path,
) -> list[ValidationIssue]:
    collection = manifest.collections.get(str(provenance.get("collection")))
    if collection is None:
        return [
            _issue("error", provenance_path, manifest.project_root, "Unknown provenance collection")
        ]
    if distribution == "committed" and collection.distribution != "committed":
        return [
            _issue(
                "error",
                provenance_path,
                manifest.project_root,
                "Local-only source material appeared in the committed skills root",
            )
        ]
    return []


def _provenance_issues(
    manifest: Manifest,
    skill_dir: Path,
    distribution: str,
    owner: tuple[Collection, Artifact] | None,
) -> list[ValidationIssue]:
    root = manifest.project_root
    provenance_path = skill_dir / "source.json"
    license_path = skill_dir / "LICENSE.txt"
    issues = _provenance_file_issues(provenance_path, license_path, root)
    if provenance_path.is_symlink() or not provenance_path.is_file():
        return issues
    provenance, read_issues = _load_provenance(provenance_path, root)
    issues.extend(read_issues)
    if provenance is None:
        return issues
    issues.extend(
        _recorded_provenance_issues(
            provenance,
            provenance_path,
            skill_dir.name,
            distribution,
            root,
        )
    )
    issues.extend(
        _collection_boundary_issues(
            manifest,
            distribution,
            provenance,
            provenance_path,
        )
    )
    if owner is not None:
        issues.extend(_artifact_provenance_issues(manifest, skill_dir, provenance, *owner))
    return issues


def _skill_directory_issues(
    manifest: Manifest,
    skill_dir: Path,
    distribution: str,
    expected: dict[str, str],
    owner: tuple[Collection, Artifact] | None,
    encoding: tiktoken.Encoding,
) -> list[ValidationIssue]:
    root = manifest.project_root
    issues: list[ValidationIssue] = []
    expected_distribution = expected.get(skill_dir.name)
    if expected_distribution is None:
        issues.append(
            _issue(
                "error",
                skill_dir,
                root,
                "Unexpected generated skill not declared in corpus.yaml",
            )
        )
    elif expected_distribution != distribution:
        issues.append(
            _issue(
                "error",
                skill_dir,
                root,
                f"Skill belongs in {expected_distribution}, not {distribution}",
            )
        )
    content_issues = _skill_content_issues(skill_dir, root, encoding)
    issues.extend(content_issues)
    if not (skill_dir / "SKILL.md").is_file():
        return issues
    issues.extend(_provenance_issues(manifest, skill_dir, distribution, owner))
    return issues


def _missing_skill_issues(
    manifest: Manifest,
    expected: dict[str, str],
    discovered: set[str],
    include_local: bool,
) -> list[ValidationIssue]:
    required = {
        name
        for name, distribution in expected.items()
        if distribution == "committed" or include_local
    }
    return [
        _issue(
            "error",
            manifest.root_for(expected[name]) / name,
            manifest.project_root,
            "Skill not built",
        )
        for name in sorted(required - discovered)
    ]


def _metadata_budget_issues(manifest: Manifest) -> list[ValidationIssue]:
    committed_root = manifest.root_for("committed")
    if not committed_root.is_dir():
        return []
    skill_dirs = sorted(
        path for path in committed_root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()
    )
    if not skill_dirs:
        return []
    budget = metadata_budget(skill_dirs)
    issues: list[ValidationIssue] = []
    if int(budget["maximum_install_root_chars"]) < MIN_SUPPORTED_INSTALL_ROOT_CHARS:
        issues.append(
            _issue(
                "error",
                committed_root,
                manifest.project_root,
                "Committed skill metadata no longer fits the audited minimum install-root length",
            )
        )
    if int(budget["codex_list_chars"]) > CODEX_FALLBACK_METADATA_CHARS:
        issues.append(
            _issue(
                "error",
                committed_root,
                manifest.project_root,
                "Committed skill metadata exceeds Codex's fallback startup budget at the "
                "documented reference path",
            )
        )
    return issues


def validate(manifest: Manifest, include_local: bool = False) -> list[ValidationIssue]:
    """Return structural, provenance, and distribution findings."""
    issues = _local_boundary_issues(manifest)
    expected = {
        artifact.name: collection.distribution
        for collection, artifact in manifest.artifacts(include_local=True)
    }
    owners = {
        artifact.name: (collection, artifact)
        for collection, artifact in manifest.artifacts(include_local=True)
    }
    skill_roots = [(manifest.root_for("committed"), "committed")]
    if include_local:
        skill_roots.append((manifest.root_for("local-only"), "local-only"))
    discovered: set[str] = set()
    encoding = tiktoken.get_encoding("o200k_base")
    for skill_root, distribution in skill_roots:
        if not skill_root.is_dir():
            issues.append(
                _issue(
                    "error", skill_root, manifest.project_root, "Generated skill root is missing"
                )
            )
            continue
        for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
            discovered.add(skill_dir.name)
            issues.extend(
                _skill_directory_issues(
                    manifest,
                    skill_dir,
                    distribution,
                    expected,
                    owners.get(skill_dir.name),
                    encoding,
                )
            )
    issues.extend(_missing_skill_issues(manifest, expected, discovered, include_local))
    issues.extend(_metadata_budget_issues(manifest))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    """Return whether any finding blocks the command."""
    return any(issue.severity == "error" for issue in issues)
