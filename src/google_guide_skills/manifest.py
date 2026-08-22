"""Load and validate the pinned corpus manifest."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .errors import ManifestError
from .models import (
    Artifact,
    CatalogOnly,
    Collection,
    LicenseInfo,
    Manifest,
    Repository,
    SourcePathPolicy,
    SupplementalLicense,
    require_mapping,
)
from .strict_yaml import strict_safe_load

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_DISTRIBUTIONS = {"committed", "local-only"}
ALLOWED_LAYOUTS = {"inline", "references"}
REQUIRED_GENERATED_ROOTS = {"committed": "skills", "local_only": ".generated/skills"}
REQUIRED_CANONICAL_PATH_POLICIES = {
    "abseil/abseil.github.io": {
        ("resources/swe-book/html/**", "local-only")
    },
    "google/styleguide": {("Rguide.md", "catalog-only")},
}
CANONICAL_REPOSITORY_URLS = {
    "styleguide": "https://github.com/google/styleguide.git",
    "eng-practices": "https://github.com/google/eng-practices.git",
    "abseil": "https://github.com/abseil/abseil.github.io.git",
}
PROTECTED_GITHUB_REPOSITORIES = {
    "google/styleguide": ("styleguide", CANONICAL_REPOSITORY_URLS["styleguide"]),
    "google/eng-practices": (
        "eng-practices",
        CANONICAL_REPOSITORY_URLS["eng-practices"],
    ),
    "abseil/abseil.github.io": ("abseil", CANONICAL_REPOSITORY_URLS["abseil"]),
}


def _github_repository_identity(url: str) -> str | None:
    """Normalize common GitHub transports to a lowercase owner/repository identity."""

    prefixes = (
        "https://github.com/",
        "http://github.com/",
        "git://github.com/",
        "ssh://git@github.com/",
        "git@github.com:",
    )
    lowered = url.lower()
    for prefix in prefixes:
        if not lowered.startswith(prefix):
            continue
        path = url[len(prefix) :].rstrip("/")
        if path.lower().endswith(".git"):
            path = path[:-4]
        parts = path.split("/")
        if len(parts) == 2 and all(parts):
            return "/".join(parts).lower()
        return None
    return None


def find_project_root(start: Path | None = None) -> Path:
    """Find the closest parent containing corpus.yaml."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "corpus.yaml").is_file():
            return candidate
    raise ManifestError(f"Could not find corpus.yaml from {current}")


def _text(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _license(data: Any, context: str) -> LicenseInfo:
    try:
        item = require_mapping(data, context)
        evidence_path = _optional_text(item.get("evidence_path"))
        evidence_glob = _optional_text(item.get("evidence_glob"))
        evidence_contains = _optional_text(item.get("evidence_contains"))
        if not evidence_path and not evidence_glob:
            raise ManifestError(
                f"{context} must provide evidence_path or evidence_glob"
            )
        if evidence_contains and not evidence_glob:
            raise ManifestError(
                f"{context}.evidence_contains requires evidence_glob"
            )
        allow_committed = item.get("allow_committed_output")
        if not isinstance(allow_committed, bool):
            raise ManifestError(f"{context}.allow_committed_output must be a boolean")
        return LicenseInfo(
            spdx=_text(item, "spdx", context),
            name=_text(item, "name", context),
            url=_text(item, "url", context),
            attribution=_text(item, "attribution", context),
            audited=_text(item, "audited", context),
            allow_committed_output=allow_committed,
            evidence_path=_safe_relative(evidence_path, f"{context}.evidence_path")
            if evidence_path
            else None,
            evidence_glob=_safe_relative(evidence_glob, f"{context}.evidence_glob")
            if evidence_glob
            else None,
            evidence_contains=evidence_contains,
            warning=_optional_text(item.get("warning")),
        )
    except TypeError as exc:
        raise ManifestError(str(exc)) from exc


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError("Optional text fields must be non-empty strings when present")
    return value.strip()


def _supplemental_license(data: Any, context: str) -> SupplementalLicense:
    item = require_mapping(data, context)
    sha256 = _text(item, "sha256", context)
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ManifestError(f"{context}.sha256 must be a lowercase SHA-256 digest")
    return SupplementalLicense(
        spdx=_text(item, "spdx", context),
        name=_text(item, "name", context),
        url=_text(item, "url", context),
        attribution=_text(item, "attribution", context),
        scope=_text(item, "scope", context),
        license_file=_safe_relative(
            _text(item, "license_file", context), f"{context}.license_file"
        ),
        evidence_contains=_text(item, "evidence_contains", context),
        sha256=sha256,
    )


def _safe_relative(pattern: str, context: str) -> str:
    pure = PurePosixPath(pattern)
    if pure.is_absolute() or ".." in pure.parts or pattern.startswith("~"):
        raise ManifestError(f"{context} contains an unsafe path: {pattern}")
    return pattern


def load_manifest(path: Path | None = None) -> Manifest:
    """Parse corpus.yaml and enforce all static safety invariants."""

    manifest_path = (path or (find_project_root() / "corpus.yaml")).resolve()
    try:
        raw = strict_safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ManifestError(f"Cannot read {manifest_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {manifest_path}: {exc}") from exc

    try:
        data = require_mapping(raw, "corpus")
    except TypeError as exc:
        raise ManifestError(str(exc)) from exc

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise ManifestError(f"Unsupported schema_version: {schema_version!r}")
    generator = require_mapping(data.get("generator"), "generator")
    canonical_python = _text(generator, "python", "generator")
    if not re.fullmatch(r"3\.\d+\.\d+", canonical_python):
        raise ManifestError("generator.python must be an exact Python 3 version such as 3.13.7")

    roots_data = require_mapping(data.get("generated_roots"), "generated_roots")
    roots = {
        "committed": _safe_relative(
            _text(roots_data, "committed", "generated_roots"), "generated_roots.committed"
        ),
        "local_only": _safe_relative(
            _text(roots_data, "local_only", "generated_roots"), "generated_roots.local_only"
        ),
    }
    if roots["committed"] == roots["local_only"]:
        raise ManifestError("Committed and local-only generated roots must differ")
    if roots != REQUIRED_GENERATED_ROOTS:
        raise ManifestError(
            f"generated_roots are a fixed security boundary and must be {REQUIRED_GENERATED_ROOTS}"
        )

    repositories: dict[str, Repository] = {}
    for repo_id, repo_raw in require_mapping(data.get("repositories"), "repositories").items():
        context = f"repositories.{repo_id}"
        if not NAME_RE.fullmatch(str(repo_id)):
            raise ManifestError(f"{context} has an invalid identifier")
        repo = require_mapping(repo_raw, context)
        revision = _text(repo, "revision", context)
        if not REVISION_RE.fullmatch(revision):
            raise ManifestError(f"{context}.revision must be a full 40-character commit SHA")
        repository_url = _text(repo, "url", context)
        identity = _github_repository_identity(repository_url)
        protected = PROTECTED_GITHUB_REPOSITORIES.get(identity or "")
        canonical_url = CANONICAL_REPOSITORY_URLS.get(str(repo_id))
        if protected is not None:
            protected_id, protected_url = protected
            if str(repo_id) != protected_id or repository_url != protected_url:
                raise ManifestError(
                    f"{context}.url must use canonical protected source "
                    f"{protected_url} under repository id {protected_id!r}"
                )
        elif canonical_url is not None and repository_url != canonical_url:
            raise ManifestError(
                f"{context}.url must use the canonical protected source {canonical_url}"
            )
        repositories[repo_id] = Repository(
            id=repo_id,
            url=repository_url,
            revision=revision,
            default_branch=_text(repo, "default_branch", context),
            license=_license(repo.get("license"), f"{context}.license"),
        )

    collections: dict[str, Collection] = {}
    seen_skills: set[str] = set()
    for collection_id, collection_raw in require_mapping(
        data.get("collections"), "collections"
    ).items():
        context = f"collections.{collection_id}"
        if not NAME_RE.fullmatch(str(collection_id)):
            raise ManifestError(f"{context} has an invalid identifier")
        item = require_mapping(collection_raw, context)
        repo_id = _text(item, "repository", context)
        if repo_id not in repositories:
            raise ManifestError(f"{context} references unknown repository {repo_id!r}")
        distribution = _text(item, "distribution", context)
        if distribution not in ALLOWED_DISTRIBUTIONS:
            raise ManifestError(f"{context}.distribution must be one of {ALLOWED_DISTRIBUTIONS}")
        artifacts_raw = item.get("artifacts")
        if not isinstance(artifacts_raw, list) or not artifacts_raw:
            raise ManifestError(f"{context}.artifacts must be a non-empty list")

        artifacts: list[Artifact] = []
        for index, artifact_raw in enumerate(artifacts_raw):
            artifact_context = f"{context}.artifacts[{index}]"
            artifact_item = require_mapping(artifact_raw, artifact_context)
            name = _text(artifact_item, "name", artifact_context)
            if not NAME_RE.fullmatch(name) or len(name) > 64:
                raise ManifestError(f"{artifact_context}.name violates Agent Skills naming rules")
            if name in seen_skills:
                raise ManifestError(f"Duplicate skill name: {name}")
            seen_skills.add(name)
            description = _text(artifact_item, "description", artifact_context)
            if len(description) > 1024:
                raise ManifestError(f"{artifact_context}.description exceeds 1024 characters")
            layout = _text(artifact_item, "layout", artifact_context)
            if layout not in ALLOWED_LAYOUTS:
                raise ManifestError(f"{artifact_context}.layout must be one of {ALLOWED_LAYOUTS}")
            inputs_raw = artifact_item.get("inputs")
            if not isinstance(inputs_raw, list) or not inputs_raw:
                raise ManifestError(f"{artifact_context}.inputs must be a non-empty list")
            inputs = tuple(
                _safe_relative(str(value), f"{artifact_context}.inputs") for value in inputs_raw
            )
            tags_raw = artifact_item.get("tags", [])
            if not isinstance(tags_raw, list) or not all(
                isinstance(value, str) and value for value in tags_raw
            ):
                raise ManifestError(f"{artifact_context}.tags must be a list of strings")
            supplemental_raw = artifact_item.get("supplemental_licenses", [])
            if not isinstance(supplemental_raw, list):
                raise ManifestError(
                    f"{artifact_context}.supplemental_licenses must be a list"
                )
            artifacts.append(
                Artifact(
                    name=name,
                    title=_text(artifact_item, "title", artifact_context),
                    description=description,
                    tags=tuple(tags_raw),
                    layout=layout,
                    inputs=inputs,
                    license_note=_optional_text(artifact_item.get("license_note")),
                    supplemental_licenses=tuple(
                        _supplemental_license(
                            candidate,
                            f"{artifact_context}.supplemental_licenses[{supplemental_index}]",
                        )
                        for supplemental_index, candidate in enumerate(supplemental_raw)
                    ),
                )
            )

        override = item.get("license_override")
        if distribution == "local-only" and override is None:
            raise ManifestError(f"{context} is local-only but has no explicit license_override")
        override_license = (
            _license(override, f"{context}.license_override") if override is not None else None
        )
        effective_license = override_license or repositories[repo_id].license
        if distribution == "committed" and not effective_license.allow_committed_output:
            raise ManifestError(
                f"{context} cannot use committed distribution under its recorded license policy"
            )
        collections[collection_id] = Collection(
            id=collection_id,
            repository=repo_id,
            distribution=distribution,
            description=_text(item, "description", context),
            artifacts=tuple(artifacts),
            license_override=override_license,
        )

    catalog_items: list[CatalogOnly] = []
    catalog_raw = data.get("catalog_only", [])
    if not isinstance(catalog_raw, list):
        raise ManifestError("catalog_only must be a list")
    for index, candidate_raw in enumerate(catalog_raw):
        context = f"catalog_only[{index}]"
        item = require_mapping(candidate_raw, context)
        item_id = _text(item, "id", context)
        if not NAME_RE.fullmatch(item_id):
            raise ManifestError(f"{context}.id has an invalid identifier")
        if item_id in seen_skills:
            raise ManifestError(f"Duplicate skill or catalog id: {item_id}")
        seen_skills.add(item_id)
        tags_raw = item.get("tags", [])
        if not isinstance(tags_raw, list) or not all(isinstance(tag, str) for tag in tags_raw):
            raise ManifestError(f"{context}.tags must be a list of strings")
        catalog_items.append(
            CatalogOnly(
                id=item_id,
                title=_text(item, "title", context),
                url=_text(item, "url", context),
                license=_text(item, "license", context),
                status=_text(item, "status", context),
                reason=_text(item, "reason", context),
                tags=tuple(tags_raw),
            )
        )

    policies_raw = data.get("source_path_policies", [])
    if not isinstance(policies_raw, list):
        raise ManifestError("source_path_policies must be a list")
    source_path_policies: list[SourcePathPolicy] = []
    for index, policy_raw in enumerate(policies_raw):
        context = f"source_path_policies[{index}]"
        item = require_mapping(policy_raw, context)
        repository = _text(item, "repository", context)
        if repository not in repositories:
            raise ManifestError(f"{context} references unknown repository {repository!r}")
        required_distribution = _text(item, "required_distribution", context)
        if required_distribution not in {*ALLOWED_DISTRIBUTIONS, "catalog-only"}:
            raise ManifestError(
                f"{context}.required_distribution must be committed, local-only, or catalog-only"
            )
        source_path_policies.append(
            SourcePathPolicy(
                repository=repository,
                pattern=_safe_relative(_text(item, "pattern", context), f"{context}.pattern"),
                required_distribution=required_distribution,
                reason=_text(item, "reason", context),
            )
        )
    for repository in repositories.values():
        identity = _github_repository_identity(repository.url)
        required = REQUIRED_CANONICAL_PATH_POLICIES.get(identity or "", set())
        actual = {
            (policy.pattern, policy.required_distribution)
            for policy in source_path_policies
            if policy.repository == repository.id
        }
        missing = sorted(required - actual)
        if missing:
            formatted = ", ".join(
                f"{pattern} -> {distribution}" for pattern, distribution in missing
            )
            raise ManifestError(
                f"Repository {repository.id} is missing mandatory source path policies: {formatted}"
            )

    return Manifest(
        path=manifest_path,
        schema_version=schema_version,
        canonical_python=canonical_python,
        generated_roots=roots,
        repositories=repositories,
        collections=collections,
        catalog_only=tuple(catalog_items),
        source_path_policies=tuple(source_path_policies),
    )
