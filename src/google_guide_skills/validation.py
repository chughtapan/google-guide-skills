"""Validate skill structure, references, provenance, and distribution policy."""

from __future__ import annotations

import json
import re
import subprocess
from hashlib import sha256
from pathlib import Path

import tiktoken
import yaml

from . import __version__
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .metrics import (
    CODEX_FALLBACK_METADATA_CHARS,
    MIN_SUPPORTED_INSTALL_ROOT_CHARS,
    metadata_budget,
)
from .models import Manifest, ValidationIssue
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


def _validate_links(
    markdown_path: Path, project_root: Path, *, catalog: bool = False
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    text = markdown_path.read_text(encoding="utf-8")
    for target in LINK_RE.findall(text):
        target = target.split("#", 1)[0]
        if not target or "://" in target or target.startswith(("mailto:", "#")):
            continue
        if not catalog and not target.startswith("references/"):
            # Links inside the mechanically preserved source body retain upstream-relative
            # semantics. Only links authored by this generator are structural invariants.
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


def validate(manifest: Manifest, include_local: bool = False) -> list[ValidationIssue]:
    """Return errors and warnings without hiding policy failures."""

    root = manifest.project_root
    issues: list[ValidationIssue] = []
    encoding = tiktoken.get_encoding("o200k_base")
    skill_roots = [(manifest.root_for("committed"), "committed")]
    local_root = manifest.root_for("local-only")
    if include_local:
        skill_roots.append((local_root, "local-only"))
    if not _is_git_ignored(local_root, root):
        issues.append(
            _issue(
                "error",
                local_root,
                root,
                "The local-only generated root is not ignored by git",
            )
        )
    tracked_local = _tracked_files_under(local_root, root)
    if tracked_local:
        preview = ", ".join(tracked_local[:5])
        issues.append(
            _issue(
                "error",
                local_root,
                root,
                f"Local-only generated output is tracked by git: {preview}",
            )
        )

    expected: dict[str, str] = {
        artifact.name: collection.distribution
        for collection, artifact in manifest.artifacts(include_local=True)
    }
    expected["google-guides-index"] = "committed"
    owners = {
        artifact.name: (collection, artifact)
        for collection, artifact in manifest.artifacts(include_local=True)
    }

    discovered: set[str] = set()
    for skill_root, distribution in skill_roots:
        if not skill_root.is_dir():
            issues.append(_issue("error", skill_root, root, "Generated skill root is missing"))
            continue
        for skill_dir in sorted(path for path in skill_root.iterdir() if path.is_dir()):
            skill_path = skill_dir / "SKILL.md"
            discovered.add(skill_dir.name)
            if skill_dir.name not in expected:
                issues.append(
                    _issue(
                        "error",
                        skill_dir,
                        root,
                        "Unexpected generated skill not declared in corpus.yaml",
                    )
                )
            elif expected[skill_dir.name] != distribution:
                issues.append(
                    _issue(
                        "error",
                        skill_dir,
                        root,
                        f"Skill belongs in {expected[skill_dir.name]}, not {distribution}",
                    )
                )
            if not skill_path.is_file():
                issues.append(_issue("error", skill_dir, root, "Missing SKILL.md"))
                continue
            metadata, body, parse_issues = _parse_skill(skill_path, root)
            issues.extend(parse_issues)
            unknown_fields = sorted(set(metadata) - {"name", "description"})
            if unknown_fields:
                issues.append(
                    _issue(
                        "error",
                        skill_path,
                        root,
                        f"Frontmatter has unsupported fields: {', '.join(unknown_fields)}",
                    )
                )
            name = metadata.get("name")
            description = metadata.get("description")
            if not isinstance(name, str) or not NAME_RE.fullmatch(name) or len(name) > 64:
                issues.append(_issue("error", skill_path, root, "Invalid skill name"))
            elif name != skill_dir.name:
                issues.append(
                    _issue(
                        "error",
                        skill_path,
                        root,
                        f"Skill name {name!r} does not match directory {skill_dir.name!r}",
                    )
                )
            if not isinstance(description, str) or not description.strip():
                issues.append(_issue("error", skill_path, root, "Missing skill description"))
            elif len(description) > 1024:
                issues.append(
                    _issue("error", skill_path, root, "Skill description exceeds 1024 characters")
                )
            if not body.strip():
                issues.append(_issue("error", skill_path, root, "Skill body is empty"))
            line_count = len(skill_path.read_text(encoding="utf-8").splitlines())
            token_count = len(encoding.encode(skill_path.read_text(encoding="utf-8")))
            if line_count > 500:
                issues.append(
                    _issue(
                        "warning",
                        skill_path,
                        root,
                        f"Baseline skill has {line_count} lines; Agent Skills recommends under 500",
                    )
                )
            if token_count > 5000:
                issues.append(
                    _issue(
                        "warning",
                        skill_path,
                        root,
                        f"Baseline skill has {token_count} tokens; "
                        "progressive disclosure is advised",
                    )
                )
            issues.extend(_validate_links(skill_path, root))
            if skill_dir.name == "google-guides-index":
                index_catalog = skill_dir / "references" / "catalog.md"
                if index_catalog.is_file():
                    issues.extend(_validate_links(index_catalog, root, catalog=True))

            provenance_path = skill_dir / "references" / "source.json"
            license_path = skill_dir / "references" / "LICENSE.txt"
            if provenance_path.is_symlink() or not provenance_path.is_file():
                issues.append(_issue("error", provenance_path, root, "Missing source metadata"))
            if license_path.is_symlink() or not license_path.is_file():
                issues.append(_issue("error", license_path, root, "Missing source license"))
            if provenance_path.is_file() and not provenance_path.is_symlink():
                try:
                    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    issues.append(
                        _issue("error", provenance_path, root, f"Invalid source metadata: {exc}")
                    )
                    continue
                recorded = provenance.get("distribution")
                if recorded != distribution:
                    issues.append(
                        _issue(
                            "error",
                            provenance_path,
                            root,
                            f"Recorded distribution {recorded!r} does not match {distribution!r}",
                        )
                    )
                if provenance.get("artifact") != skill_dir.name:
                    issues.append(
                        _issue(
                            "error",
                            provenance_path,
                            root,
                            "Provenance artifact does not match the skill directory",
                        )
                    )
                collection_id = provenance.get("collection")
                collection = manifest.collections.get(str(collection_id))
                if skill_dir.name == "google-guides-index":
                    expected_index_license = wrapper_license_metadata(
                        "references/LICENSE.txt"
                    )
                    expected_manifest = {
                        "path": "corpus.yaml",
                        "sha256": sha256(
                            (manifest.project_root / "corpus.yaml").read_bytes()
                        ).hexdigest(),
                    }
                    if (
                        collection_id != "authored-index"
                        or provenance.get("generated_by")
                        != f"google-guide-skills/{__version__}"
                        or provenance.get("license") != expected_index_license
                        or provenance.get("source_manifest") != expected_manifest
                    ):
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Authored index provenance is missing or stale",
                            )
                        )
                    if (
                        license_path.is_symlink()
                        or not license_path.is_file()
                        or sha256(license_path.read_bytes()).hexdigest()
                        != PROJECT_LICENSE_SHA256
                    ):
                        issues.append(
                            _issue(
                                "error",
                                license_path,
                                root,
                                "Authored index Apache license is missing or stale",
                            )
                        )
                elif collection is None:
                    issues.append(
                        _issue("error", provenance_path, root, "Unknown provenance collection")
                    )
                elif distribution == "committed" and collection.distribution != "committed":
                    issues.append(
                        _issue(
                            "error",
                            provenance_path,
                            root,
                            "Local-only source material appeared in the committed skills root",
                        )
                    )
                owner = owners.get(skill_dir.name)
                if owner is not None:
                    expected_collection, artifact = owner
                    repository = manifest.repositories[expected_collection.repository]
                    if collection_id != expected_collection.id:
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Provenance collection does not own this artifact",
                            )
                        )
                    if provenance.get("generated_by") != f"google-guide-skills/{__version__}":
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Generated provenance version is stale",
                            )
                        )
                    runtime = provenance.get("generator_runtime")
                    if (
                        not isinstance(runtime, dict)
                        or runtime.get("python") != manifest.canonical_python
                        or not all(
                            isinstance(runtime.get(name), str) and runtime.get(name)
                            for name in ("beautifulsoup4", "lxml", "markdownify")
                        )
                    ):
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Generator runtime provenance is missing or stale",
                            )
                        )
                    if provenance.get("repository") != {
                        "id": repository.id,
                        "url": repository.url,
                        "revision": repository.revision,
                    }:
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Repository provenance does not match corpus.yaml",
                            )
                        )
                    if provenance.get("license") != manifest.license_for(
                        expected_collection
                    ).to_dict():
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "License provenance does not match corpus.yaml",
                            )
                        )
                    expected_supplemental = [
                        supplemental.to_dict()
                        for supplemental in artifact.supplemental_licenses
                    ]
                    if provenance.get("supplemental_licenses", []) != expected_supplemental:
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Supplemental license provenance does not match corpus.yaml",
                            )
                        )
                    if provenance.get("license_note") != artifact.license_note:
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Artifact license note does not match corpus.yaml",
                            )
                        )
                    expected_wrapper = wrapper_license_metadata()
                    wrapper_path = skill_dir / "references" / WRAPPER_LICENSE_FILENAME
                    if provenance.get("wrapper_license") != expected_wrapper:
                        issues.append(
                            _issue(
                                "error",
                                provenance_path,
                                root,
                                "Wrapper license provenance does not match the project policy",
                            )
                        )
                    if (
                        wrapper_path.is_symlink()
                        or not wrapper_path.is_file()
                        or sha256(wrapper_path.read_bytes()).hexdigest()
                        != PROJECT_LICENSE_SHA256
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
                        supplemental_path = (
                            skill_dir
                            / "references"
                            / f"LICENSE-{supplemental.spdx}.txt"
                        )
                        if not supplemental_path.is_file():
                            issues.append(
                                _issue(
                                    "error",
                                    supplemental_path,
                                    root,
                                    "Missing supplemental source license",
                                )
                            )

    required = {
        name
        for name, distribution in expected.items()
        if distribution == "committed" or include_local
    }
    for missing in sorted(required - discovered):
        distribution = expected[missing]
        output_root = manifest.root_for(distribution)
        issues.append(_issue("error", output_root / missing, root, "Skill not built"))
    committed_dirs = (
        sorted(
            path
            for path in manifest.root_for("committed").iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        )
        if manifest.root_for("committed").is_dir()
        else []
    )
    if committed_dirs:
        budget = metadata_budget(committed_dirs)
        if int(budget["maximum_install_root_chars"]) < MIN_SUPPORTED_INSTALL_ROOT_CHARS:
            issues.append(
                _issue(
                    "error",
                    manifest.root_for("committed"),
                    root,
                    "Committed skill metadata no longer fits the audited minimum install-root "
                    "length",
                )
            )
        if int(budget["codex_list_chars"]) > CODEX_FALLBACK_METADATA_CHARS:
            issues.append(
                _issue(
                    "error",
                    manifest.root_for("committed"),
                    root,
                    "Committed skill metadata exceeds Codex's fallback startup budget at the "
                    "documented reference path",
                )
            )
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)
