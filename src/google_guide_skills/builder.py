"""Build deterministic Agent Skill directories from manifest artifacts."""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .convert import source_to_markdown
from .errors import BuildError
from .git_safe import command as git_command
from .git_safe import environment as git_environment
from .git_safe import git_dir_is_safe, repository_config_problem
from .models import Artifact, BuiltSkill, Collection, LicenseInfo, Manifest, Repository
from .path_policy import require_safe_project_path
from .project_license import (
    PROJECT_LICENSE_SHA256,
    WRAPPER_LICENSE_FILENAME,
    verified_project_license,
    wrapper_license_metadata,
)
from .sources import checkout_path, sync

GLOB_CHARS = frozenset("*?[")
ALLOWED_SUPPLEMENTAL_LICENSES = {("Apache-2.0", "LICENSE"): PROJECT_LICENSE_SHA256}
MANDATORY_SOURCE_PATH_RULES = {
    "resources/swe-book/html/**": (
        "local-only",
        "Software Engineering at Google is generated only into ignored local output.",
    ),
    "Rguide.md": (
        "catalog-only",
        "The R guide has composite upstream licensing pending a redistribution audit.",
    ),
}


@dataclass(frozen=True)
class _PreparedSources:
    running_python: str
    repository: Repository
    checkout: Path
    inputs: tuple[Path, ...]
    license_info: LicenseInfo
    matched_path_policies: tuple[dict[str, str], ...]


def assert_canonical_runtime(manifest: Manifest) -> str:
    """Reject non-canonical generation before source sync or output mutation."""
    running_python = platform.python_version()
    if running_python != manifest.canonical_python:
        raise BuildError(
            f"Canonical generation requires Python {manifest.canonical_python}; "
            f"running {running_python}"
        )
    return running_python


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frontmatter(name: str, description: str) -> str:
    wrapped = textwrap.wrap(
        " ".join(description.split()),
        width=94,
        break_long_words=False,
        break_on_hyphens=False,
    )
    description_lines = "\n".join(f"  {line}" for line in wrapped)
    return f"---\nname: {name}\ndescription: >-\n{description_lines}\n---\n"


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _assert_safe_output_root(manifest: Manifest, distribution: str) -> Path:
    """Reject symlinked or physically overlapping generated roots before writing."""
    output_root = require_safe_project_path(
        manifest.project_root,
        manifest.root_for(distribution),
        context="Generated output path",
        error_type=BuildError,
    )
    other_distribution = "local-only" if distribution == "committed" else "committed"
    other_root = manifest.root_for(other_distribution)
    if output_root.resolve() == other_root.resolve():
        raise BuildError("Committed and local-only generated roots resolve to the same directory")
    return output_root


def _evidence_file(path: Path, checkout: Path, context: str) -> Path:
    if not path.is_file():
        raise BuildError(f"Missing license evidence file: {path}")
    if not _is_within(path, checkout):
        raise BuildError(f"{context}: license evidence escapes the pinned checkout: {path}")
    return path


def _assert_matches_revision(path: Path, checkout: Path, revision: str, context: str) -> None:
    """Require bytes to come from a tracked regular file at the pinned commit."""
    try:
        relative = path.relative_to(checkout).as_posix()
    except ValueError as exc:
        raise BuildError(f"{context}: source escapes the pinned checkout: {path}") from exc
    completed = subprocess.run(
        git_command("show", f"{revision}:{relative}"),
        cwd=checkout,
        env=git_environment(checkout),
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise BuildError(f"{context}: source is not tracked at the pinned revision: {relative}")
    if completed.stdout != path.read_bytes():
        raise BuildError(f"{context}: source differs from the pinned revision: {relative}")


def _project_license_file(
    manifest: Manifest, spdx: str, relative: str, expected_sha256: str, context: str
) -> Path:
    path = manifest.project_root / relative
    if path.is_symlink() or not path.is_file() or not _is_within(path, manifest.project_root):
        raise BuildError(f"{context}: invalid supplemental license file: {relative}")
    allowlisted_hash = ALLOWED_SUPPLEMENTAL_LICENSES.get((spdx, relative))
    if allowlisted_hash is None or expected_sha256 != allowlisted_hash:
        raise BuildError(f"{context}: supplemental license asset is not allowlisted")
    if _sha256(path) != expected_sha256:
        raise BuildError(f"{context}: supplemental license asset hash does not match")
    return path


def _expand_inputs(checkout: Path, artifact: Artifact) -> list[Path]:
    found: dict[str, Path] = {}
    for pattern in artifact.inputs:
        matches = sorted(checkout.glob(pattern))
        if not any(char in pattern for char in GLOB_CHARS):
            exact = checkout / pattern
            matches = [exact] if exact.is_file() else []
        matches = [path for path in matches if path.is_file() and _is_within(path, checkout)]
        if not matches:
            raise BuildError(f"{artifact.name}: input pattern matched no files: {pattern}")
        for match in matches:
            relative = match.relative_to(checkout).as_posix()
            found[relative] = match
    return [found[key] for key in sorted(found)]


def _reference_name(relative_path: str) -> str:
    value = relative_path.replace("/", "--")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    suffix = Path(value).suffix.lower()
    if suffix in {".html", ".htm", ".xml", ".xhtml"}:
        value = f"{value[: -len(suffix)]}.md"
    elif suffix != ".md":
        value = f"{value}.md"
    if not value:
        raise BuildError(f"Could not derive a reference filename from {relative_path!r}")
    return value


def _matches_policy(relative: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        return relative.startswith(pattern[:-3].rstrip("/") + "/")
    return fnmatch.fnmatchcase(relative, pattern)


def _enforce_source_path_policies(
    manifest: Manifest,
    collection: Collection,
    inputs: list[Path],
    checkout: Path,
) -> list[dict[str, str]]:
    matched: list[dict[str, str]] = []
    for source_path in inputs:
        relative = source_path.relative_to(checkout).as_posix()
        rules = [
            (policy.pattern, policy.required_distribution, policy.reason)
            for policy in manifest.source_path_policies
            if policy.repository == collection.repository
            and _matches_policy(relative, policy.pattern)
        ]
        for pattern, (required_distribution, reason) in MANDATORY_SOURCE_PATH_RULES.items():
            if _matches_policy(relative, pattern) and not any(
                candidate[0] == pattern and candidate[1] == required_distribution
                for candidate in rules
            ):
                # These rules are deliberately repository-independent. Renaming or aliasing a
                # protected source entry must not turn restricted bytes into committed output.
                rules.append((pattern, required_distribution, reason))
        for pattern, required_distribution, reason in rules:
            if required_distribution == "catalog-only":
                raise BuildError(
                    f"{collection.id}: {relative} is catalog-only and cannot be generated"
                )
            if collection.distribution != required_distribution:
                raise BuildError(
                    f"{collection.id}: {relative} requires {required_distribution} output"
                )
            matched.append(
                {
                    "path": relative,
                    "pattern": pattern,
                    "required_distribution": required_distribution,
                    "reason": reason,
                }
            )
    return matched


def _license_notice(license_info: LicenseInfo, checkout: Path) -> str:
    header = [
        f"Source license: {license_info.name} ({license_info.spdx})",
        f"License URL: {license_info.url}",
        f"Attribution: {license_info.attribution}",
        f"License audit date: {license_info.audited}",
    ]
    if license_info.warning:
        header.extend(["", f"WARNING: {license_info.warning}"])
    if license_info.evidence_path:
        evidence = _evidence_file(checkout / license_info.evidence_path, checkout, "license notice")
        header.extend(
            [
                "",
                f"The upstream license text below is copied from {license_info.evidence_path}.",
                "",
                evidence.read_text(encoding="utf-8").rstrip(),
            ]
        )
    else:
        header.extend(
            [
                "",
                "The source files carry the file-level license notice recorded in source.json.",
                "Follow the linked legal terms; this generator does not grant extra rights.",
            ]
        )
    return "\n".join(header).rstrip() + "\n"


def verify_license_evidence(
    manifest: Manifest, collection: Collection, checkout: Path
) -> LicenseInfo:
    """Fail closed if required repository or file-level license evidence disappears."""
    license_info = manifest.license_for(collection)
    if collection.distribution == "committed" and not license_info.allow_committed_output:
        raise BuildError(
            f"{collection.id}: recorded license policy forbids committed generated output"
        )
    revision = manifest.repositories[collection.repository].revision
    if license_info.evidence_path:
        evidence = _evidence_file(
            checkout / license_info.evidence_path,
            checkout,
            collection.id,
        )
        _assert_matches_revision(evidence, checkout, revision, collection.id)
    if license_info.evidence_glob:
        files = sorted(checkout.glob(license_info.evidence_glob))
        if not files:
            raise BuildError(
                f"{collection.id}: license evidence glob matched no files: "
                f"{license_info.evidence_glob}"
            )
        for path in files:
            evidence = _evidence_file(path, checkout, collection.id)
            _assert_matches_revision(evidence, checkout, revision, collection.id)
        if license_info.evidence_contains:
            missing = [
                path.relative_to(checkout).as_posix()
                for path in files
                if license_info.evidence_contains.lower()
                not in path.read_text(encoding="utf-8").lower()
            ]
            if missing:
                preview = ", ".join(missing[:5])
                raise BuildError(
                    f"{collection.id}: {len(missing)} files lost the required license notice: "
                    f"{preview}"
                )
    return license_info


def _render_inline(artifact: Artifact, converted: list[tuple[str, str, str]]) -> str:
    sections = [
        _frontmatter(artifact.name, artifact.description),
        f"# {artifact.title}\n",
        "Apply the mechanically converted source guidance below when it is relevant to the task. "
        "Keep project-specific requirements and newer authoritative rules in force.\n",
        "The source prose is not summarized or editorially rewritten. HTML and XML inputs are "
        "converted mechanically to Markdown.\n",
        "## Source material\n",
    ]
    for relative, content, _mode in converted:
        sections.extend([f"### `{relative}`\n", content.rstrip() + "\n"])
    sections.extend(
        [
            "## Provenance\n",
            "Read [source metadata](references/source.json) and "
            "[the source license](references/LICENSE.txt) when attribution, revision, or reuse "
            "terms matter.\n",
        ]
    )
    return "\n".join(section.rstrip() for section in sections).rstrip() + "\n"


def _render_references(artifact: Artifact, references: list[tuple[str, str]]) -> str:
    lines = [
        _frontmatter(artifact.name, artifact.description).rstrip(),
        "",
        f"# {artifact.title}",
        "",
        "Read only the source references needed for the task. Search reference filenames and "
        "headings first when the collection is large. Apply the source guidance without "
        "silently inventing new rules.",
        "",
        "The reference prose is not summarized or editorially rewritten. HTML and XML inputs "
        "are converted mechanically to Markdown.",
        "",
        "## References",
        "",
    ]
    lines.extend(f"- [{source}](references/{filename})" for source, filename in references)
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "Read [source metadata](references/source.json) and "
            "[the source license](references/LICENSE.txt) when attribution, revision, or reuse "
            "terms matter.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _replace_generated_directory(staged: Path, target: Path, output_root: Path) -> None:
    if target.parent.resolve() != output_root.resolve():
        raise BuildError(f"Refusing to replace output outside {output_root}: {target}")
    if target.exists():
        marker = target / "references" / "source.json"
        if not marker.is_file():
            raise BuildError(f"Refusing to replace unrecognized directory without {marker}")
        shutil.rmtree(target)
    staged.replace(target)


def _verified_checkout(manifest: Manifest, collection: Collection) -> tuple[Repository, Path]:
    repository = manifest.repositories[collection.repository]
    checkout = require_safe_project_path(
        manifest.project_root,
        checkout_path(manifest, repository.id),
        context="Source checkout",
        error_type=BuildError,
    )
    if not git_dir_is_safe(checkout):
        raise BuildError(f"Missing checkout for {repository.id}; run `google-guides sync` first")
    config_problem = repository_config_problem(checkout, repository.url, repository.default_branch)
    if config_problem:
        raise BuildError(f"Checkout {repository.id} has unsafe local Git config: {config_problem}")
    revision = subprocess_revision(checkout)
    if revision != repository.revision:
        raise BuildError(
            f"Checkout {repository.id} is at {revision}, expected pinned {repository.revision}"
        )
    return repository, checkout


def _prepare_sources(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
    running_python: str,
) -> _PreparedSources:
    repository, checkout = _verified_checkout(manifest, collection)
    license_info = verify_license_evidence(manifest, collection, checkout)
    inputs = _expand_inputs(checkout, artifact)
    matched_policies = _enforce_source_path_policies(manifest, collection, inputs, checkout)
    for source_path in inputs:
        _assert_matches_revision(source_path, checkout, repository.revision, artifact.name)
    for supplemental in artifact.supplemental_licenses:
        has_evidence = any(
            supplemental.evidence_contains.lower()
            in source_path.read_text(encoding="utf-8").lower()
            for source_path in inputs
        )
        if not has_evidence:
            raise BuildError(
                f"{artifact.name}: supplemental {supplemental.spdx} evidence disappeared"
            )
    return _PreparedSources(
        running_python=running_python,
        repository=repository,
        checkout=checkout,
        inputs=tuple(inputs),
        license_info=license_info,
        matched_path_policies=tuple(matched_policies),
    )


def _convert_inputs(
    artifact: Artifact,
    inputs: tuple[Path, ...],
    checkout: Path,
    references_dir: Path,
) -> tuple[list[tuple[str, str, str]], list[dict[str, str]], list[tuple[str, str]]]:
    converted: list[tuple[str, str, str]] = []
    provenance_inputs: list[dict[str, str]] = []
    reference_links: list[tuple[str, str]] = []
    used_reference_names: set[str] = set()
    for source_path in inputs:
        relative = source_path.relative_to(checkout).as_posix()
        markdown, mode = source_to_markdown(source_path)
        converted.append((relative, markdown, mode))
        provenance_inputs.append(
            {"path": relative, "sha256": _sha256(source_path), "conversion": mode}
        )
        if artifact.layout != "references":
            continue
        reference_name = _reference_name(relative)
        if reference_name in used_reference_names:
            raise BuildError(f"{artifact.name}: reference filename collision for {relative}")
        used_reference_names.add(reference_name)
        (references_dir / reference_name).write_text(markdown, encoding="utf-8")
        reference_links.append((relative, reference_name))
    return converted, provenance_inputs, reference_links


def _write_licenses(
    manifest: Manifest,
    artifact: Artifact,
    prepared: _PreparedSources,
    references_dir: Path,
) -> None:
    license_notice = _license_notice(prepared.license_info, prepared.checkout)
    if artifact.license_note:
        license_notice = (
            f"{license_notice.rstrip()}\n\n"
            f"Artifact-specific license note: {artifact.license_note}\n"
        )
    (references_dir / "LICENSE.txt").write_text(license_notice, encoding="utf-8")
    shutil.copyfile(
        verified_project_license(manifest.project_root, error_type=BuildError),
        references_dir / WRAPPER_LICENSE_FILENAME,
    )
    for supplemental in artifact.supplemental_licenses:
        source = _project_license_file(
            manifest,
            supplemental.spdx,
            supplemental.license_file,
            supplemental.sha256,
            artifact.name,
        )
        shutil.copyfile(source, references_dir / f"LICENSE-{supplemental.spdx}.txt")


def _source_metadata(
    collection: Collection,
    artifact: Artifact,
    prepared: _PreparedSources,
    provenance_inputs: list[dict[str, str]],
) -> dict[str, object]:
    return {
        "artifact": artifact.name,
        "collection": collection.id,
        "distribution": collection.distribution,
        "generated_by": f"google-guide-skills/{__version__}",
        "generator_runtime": {
            "python": prepared.running_python,
            "beautifulsoup4": importlib.metadata.version("beautifulsoup4"),
            "lxml": importlib.metadata.version("lxml"),
            "markdownify": importlib.metadata.version("markdownify"),
        },
        "inputs": provenance_inputs,
        "license": prepared.license_info.to_dict(),
        "license_note": artifact.license_note,
        "wrapper_license": wrapper_license_metadata(),
        "supplemental_licenses": [
            supplemental.to_dict() for supplemental in artifact.supplemental_licenses
        ],
        "repository": {
            "id": prepared.repository.id,
            "url": prepared.repository.url,
            "revision": prepared.repository.revision,
        },
        "source_path_policies": list(prepared.matched_path_policies),
    }


def _stage_skill(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
    prepared: _PreparedSources,
    staged: Path,
) -> list[dict[str, str]]:
    references_dir = staged / "references"
    references_dir.mkdir(parents=True)
    converted, provenance_inputs, reference_links = _convert_inputs(
        artifact, prepared.inputs, prepared.checkout, references_dir
    )
    skill_text = (
        _render_inline(artifact, converted)
        if artifact.layout == "inline"
        else _render_references(artifact, reference_links)
    )
    (staged / "SKILL.md").write_text(skill_text, encoding="utf-8")
    _write_licenses(
        manifest,
        artifact,
        prepared,
        references_dir,
    )
    _write_json(
        references_dir / "source.json",
        _source_metadata(
            collection,
            artifact,
            prepared,
            provenance_inputs,
        ),
    )
    return provenance_inputs


def build_skill(
    manifest: Manifest,
    collection: Collection,
    artifact: Artifact,
) -> BuiltSkill:
    """Build one artifact into its policy-selected root."""
    running_python = assert_canonical_runtime(manifest)
    prepared = _prepare_sources(manifest, collection, artifact, running_python)
    output_root = _assert_safe_output_root(manifest, collection.distribution)
    output_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f".{artifact.name}-", dir=output_root) as temporary:
        staged = Path(temporary) / artifact.name
        provenance_inputs = _stage_skill(
            manifest,
            collection,
            artifact,
            prepared,
            staged,
        )
        target = output_root / artifact.name
        _replace_generated_directory(staged, target, output_root)

    return BuiltSkill(
        collection=collection.id,
        name=artifact.name,
        distribution=collection.distribution,
        path=target,
        source_files=tuple(item["path"] for item in provenance_inputs),
    )


def subprocess_revision(checkout: Path) -> str:
    """Return the checkout's current commit SHA."""
    completed = subprocess.run(
        git_command("rev-parse", "HEAD"),
        cwd=checkout,
        env=git_environment(checkout),
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def _selected_collections(
    manifest: Manifest, collection_ids: list[str] | None, include_local: bool
) -> list[str]:
    selected = collection_ids or list(manifest.collections)
    unknown = sorted(set(selected) - set(manifest.collections))
    if unknown:
        raise BuildError(f"Unknown collections: {', '.join(unknown)}")
    blocked = sorted(
        collection_id
        for collection_id in selected
        if manifest.collections[collection_id].distribution == "local-only" and not include_local
    )
    if collection_ids and blocked:
        raise BuildError(
            "Explicit local-only collections require --include-swe-book: " + ", ".join(blocked)
        )
    return selected


def _selected_artifacts(manifest: Manifest, artifact_names: list[str] | None) -> set[str]:
    selected = set(artifact_names or [])
    known = {
        artifact.name
        for collection in manifest.collections.values()
        for artifact in collection.artifacts
    }
    unknown = sorted(selected - known)
    if unknown:
        raise BuildError(f"Unknown artifacts: {', '.join(unknown)}")
    return selected


def _build_pairs(
    manifest: Manifest,
    collection_ids: list[str],
    artifact_names: set[str],
    include_local: bool,
) -> list[tuple[Collection, Artifact]]:
    pairs: list[tuple[Collection, Artifact]] = []
    for collection_id in collection_ids:
        collection = manifest.collections[collection_id]
        if collection.distribution == "local-only" and not include_local:
            continue
        pairs.extend(
            (collection, artifact)
            for artifact in collection.artifacts
            if not artifact_names or artifact.name in artifact_names
        )
    omitted = sorted(artifact_names - {artifact.name for _collection, artifact in pairs})
    if omitted:
        raise BuildError(
            "Selected artifacts are outside the selected collections or local-only policy: "
            + ", ".join(omitted)
        )
    return pairs


def build(
    manifest: Manifest,
    collection_ids: list[str] | None = None,
    artifact_names: list[str] | None = None,
    include_local: bool = False,
    sync_first: bool = True,
) -> list[BuiltSkill]:
    """Build selected skills; local-only material remains in its ignored root."""
    assert_canonical_runtime(manifest)
    selected_collections = _selected_collections(manifest, collection_ids, include_local)
    selected_artifacts = _selected_artifacts(manifest, artifact_names)
    build_pairs = _build_pairs(manifest, selected_collections, selected_artifacts, include_local)
    if sync_first:
        repository_ids = list(dict.fromkeys(pair[0].repository for pair in build_pairs))
        sync(manifest, repository_ids)

    return [build_skill(manifest, collection, artifact) for collection, artifact in build_pairs]
