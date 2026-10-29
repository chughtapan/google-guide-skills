"""Load and validate the pinned corpus manifest."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .errors import ManifestError, SourceError
from .models import (
    Artifact,
    CatalogOnly,
    Collection,
    LicenseInfo,
    Manifest,
    Repository,
    SourceExcerpt,
    SourcePathPolicy,
    SupplementalLicense,
    WebPage,
    WebSource,
    require_mapping,
)
from .snapshots import require_public_url
from .strict_yaml import strict_safe_load

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_DISTRIBUTIONS = {"committed", "local-only"}
REQUIRED_GENERATED_ROOTS = {"committed": "skills", "local_only": ".generated/skills"}
REQUIRED_CANONICAL_PATH_POLICIES = {
    "abseil/abseil.github.io": {("resources/swe-book/html/**", "local-only")},
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
    item = require_mapping(data, context)
    evidence_path = _optional_text(item.get("evidence_path"))
    evidence_glob = _optional_text(item.get("evidence_glob"))
    evidence_contains = _optional_text(item.get("evidence_contains"))
    if not evidence_path and not evidence_glob:
        raise ManifestError(f"{context} must provide evidence_path or evidence_glob")
    if evidence_contains and not evidence_glob:
        raise ManifestError(f"{context}.evidence_contains requires evidence_glob")
    allow_committed = item.get("allow_committed_output")
    if not isinstance(allow_committed, bool):
        raise ManifestError(f"{context}.allow_committed_output must be a boolean")
    evidence_paths = item.get("evidence_paths", [])
    if not isinstance(evidence_paths, list) or not all(
        isinstance(value, str) and value for value in evidence_paths
    ):
        raise ManifestError(f"{context}.evidence_paths must be a list of paths")
    code_license = item.get("code_samples_spdx")
    if code_license is not None and code_license != "Apache-2.0":
        raise ManifestError(f"{context}.code_samples_spdx must be Apache-2.0 when provided")
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
        evidence_paths=tuple(_safe_relative(value, context) for value in evidence_paths),
        code_samples_spdx=code_license,
    )


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


def _generated_roots(data: dict[str, Any]) -> dict[str, str]:
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
    return roots


def _repository(repo_id: object, raw: object) -> Repository:
    context = f"repositories.{repo_id}"
    if not NAME_RE.fullmatch(str(repo_id)):
        raise ManifestError(f"{context} has an invalid identifier")
    item = require_mapping(raw, context)
    revision = _text(item, "revision", context)
    if not REVISION_RE.fullmatch(revision):
        raise ManifestError(f"{context}.revision must be a full 40-character commit SHA")
    url = _text(item, "url", context)
    protected = PROTECTED_GITHUB_REPOSITORIES.get(_github_repository_identity(url) or "")
    canonical_url = CANONICAL_REPOSITORY_URLS.get(str(repo_id))
    if protected is not None:
        protected_id, protected_url = protected
        if str(repo_id) != protected_id or url != protected_url:
            raise ManifestError(
                f"{context}.url must use canonical protected source "
                f"{protected_url} under repository id {protected_id!r}"
            )
    elif canonical_url is not None and url != canonical_url:
        raise ManifestError(
            f"{context}.url must use the canonical protected source {canonical_url}"
        )
    adapter = item.get("adapter", "default")
    if not isinstance(adapter, str) or adapter not in {"default", "aip", "dora", "html-book"}:
        raise ManifestError(f"{context}.adapter is unsupported: {adapter!r}")
    return Repository(
        id=str(repo_id),
        url=url,
        revision=revision,
        default_branch=_text(item, "default_branch", context),
        license=_license(item.get("license"), f"{context}.license"),
        adapter=adapter,
    )


def _repositories(data: dict[str, Any]) -> dict[str, Repository]:
    raw = require_mapping(data.get("repositories"), "repositories")
    return {str(repo_id): _repository(repo_id, item) for repo_id, item in raw.items()}


def _web_sources(data: dict[str, Any]) -> dict[str, WebSource]:
    raw = require_mapping(data.get("web_sources", {}), "web_sources")
    sources: dict[str, WebSource] = {}
    for source_id, value in raw.items():
        context = f"web_sources.{source_id}"
        if not isinstance(source_id, str) or not NAME_RE.fullmatch(source_id):
            raise ManifestError(f"{context} has an invalid identifier")
        item = require_mapping(value, context)
        url = _text(item, "url", context)
        license_info = _license(item.get("license"), f"{context}.license")
        if (
            license_info.spdx != "CC-BY-4.0"
            or not license_info.allow_committed_output
            or license_info.evidence_path != "LICENSE.txt"
            or license_info.evidence_glob
            or license_info.evidence_paths
        ):
            raise ManifestError(f"{context}: web sources require public CC-BY-4.0 page evidence")
        pages_raw = item.get("pages")
        if not isinstance(pages_raw, list) or not pages_raw:
            raise ManifestError(f"{context}.pages must explicitly enumerate pages")
        pages: list[WebPage] = []
        seen_paths: set[str] = set()
        seen_urls: set[str] = set()
        try:
            require_public_url(url)
            for candidate in pages_raw:
                page = require_mapping(candidate, f"{context}.pages")
                path = _text(page, "path", context)
                page_url = _text(page, "url", context)
                if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.html", path):
                    raise ManifestError(f"{context}: page paths must be simple .html filenames")
                if path in seen_paths or page_url in seen_urls:
                    raise ManifestError(f"{context}: duplicate page path or URL")
                require_public_url(page_url)
                seen_paths.add(path)
                seen_urls.add(page_url)
                pages.append(WebPage(path, page_url, _text(page, "selector", context)))
        except SourceError as exc:
            raise ManifestError(f"{context}: {exc}") from exc
        sources[source_id] = WebSource(source_id, url, license_info, tuple(pages))
    return sources


def _packs(data: dict[str, Any], collections: dict[str, Collection]) -> dict[str, tuple[str, ...]]:
    known = {
        artifact.name for collection in collections.values() for artifact in collection.artifacts
    }
    if data["schema_version"] == 2:
        return {"legacy": tuple(sorted(known))}
    raw = require_mapping(data.get("packs"), "packs")
    if "legacy" not in raw:
        raise ManifestError("packs must retain the legacy installation selection")
    packs: dict[str, tuple[str, ...]] = {}
    for name, members in raw.items():
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            raise ManifestError(f"Invalid pack name: {name!r}")
        if (
            not isinstance(members, list)
            or not members
            or not all(isinstance(value, str) and value in known for value in members)
        ):
            raise ManifestError(f"packs.{name} must contain known skill names")
        if len(members) != len(set(members)):
            raise ManifestError(f"packs.{name} repeats a skill")
        packs[name] = tuple(members)
    missing = known - {member for members in packs.values() for member in members}
    if missing:
        raise ManifestError(f"Skills missing from packs: {', '.join(sorted(missing))}")
    return packs


def _artifact(raw: object, context: str, seen_names: set[str]) -> Artifact:
    item = require_mapping(raw, context)
    name = _text(item, "name", context)
    if not NAME_RE.fullmatch(name) or len(name) > 64:
        raise ManifestError(f"{context}.name violates Agent Skills naming rules")
    if name in seen_names:
        raise ManifestError(f"Duplicate skill name: {name}")
    seen_names.add(name)
    description = _text(item, "description", context)
    if len(description) > 1024:
        raise ManifestError(f"{context}.description exceeds 1024 characters")
    inputs_raw = item.get("inputs")
    if not isinstance(inputs_raw, list) or not inputs_raw:
        raise ManifestError(f"{context}.inputs must be a non-empty list")
    tags_raw = item.get("tags", [])
    if not isinstance(tags_raw, list) or not all(
        isinstance(value, str) and value for value in tags_raw
    ):
        raise ManifestError(f"{context}.tags must be a list of strings")
    supplemental_raw = item.get("supplemental_licenses", [])
    if not isinstance(supplemental_raw, list):
        raise ManifestError(f"{context}.supplemental_licenses must be a list")
    inputs = tuple(_safe_relative(str(value), f"{context}.inputs") for value in inputs_raw)
    if any(any(marker in input_path for marker in "*?[") for input_path in inputs):
        raise ManifestError(f"{context}.inputs must name exact source files")
    if "recipe" in item:
        raise ManifestError(f"{context}.recipe is no longer supported; use source excerpts")
    excerpts_raw = item.get("excerpts", [])
    if not isinstance(excerpts_raw, list):
        raise ManifestError(f"{context}.excerpts must be a list")
    excerpts: list[SourceExcerpt] = []
    seen_excerpts: set[tuple[str, str]] = set()
    for index, candidate in enumerate(excerpts_raw):
        excerpt_context = f"{context}.excerpts[{index}]"
        excerpt = require_mapping(candidate, excerpt_context)
        input_path = _safe_relative(_text(excerpt, "input", excerpt_context), excerpt_context)
        if input_path not in inputs:
            raise ManifestError(f"{excerpt_context}.input must name one of the artifact inputs")
        heading = _text(excerpt, "heading", excerpt_context)
        blocks_raw = excerpt.get("blocks")
        valid_blocks = (
            isinstance(blocks_raw, list)
            and bool(blocks_raw)
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in blocks_raw
            )
            and len(set(blocks_raw)) == len(blocks_raw)
            and blocks_raw == sorted(blocks_raw)
        )
        if not valid_blocks:
            raise ManifestError(
                f"{excerpt_context}.blocks must be strictly increasing nonnegative integers"
            )
        key = (input_path, " ".join(heading.split()).casefold())
        if key in seen_excerpts:
            raise ManifestError(f"{excerpt_context} duplicates an input and heading selector")
        seen_excerpts.add(key)
        excerpts.append(SourceExcerpt(input=input_path, heading=heading, blocks=tuple(blocks_raw)))
    return Artifact(
        name=name,
        title=_text(item, "title", context),
        description=description,
        tags=tuple(tags_raw),
        inputs=inputs,
        excerpts=tuple(excerpts),
        license_note=_optional_text(item.get("license_note")),
        supplemental_licenses=tuple(
            _supplemental_license(
                candidate,
                f"{context}.supplemental_licenses[{index}]",
            )
            for index, candidate in enumerate(supplemental_raw)
        ),
    )


def _collection(
    collection_id: object,
    raw: object,
    repositories: dict[str, Repository],
    seen_names: set[str],
    web_sources: dict[str, WebSource],
) -> Collection:
    context = f"collections.{collection_id}"
    if not NAME_RE.fullmatch(str(collection_id)):
        raise ManifestError(f"{context} has an invalid identifier")
    item = require_mapping(raw, context)
    if ("repository" in item) == ("web_source" in item):
        raise ManifestError(f"{context} must name exactly one repository or web_source")
    web_id = _text(item, "web_source", context) if "web_source" in item else None
    repo_id = _text(item, "repository", context) if web_id is None else ""
    if web_id is not None and web_id not in web_sources:
        raise ManifestError(f"{context} references unknown web source {web_id!r}")
    if web_id is None and repo_id not in repositories:
        raise ManifestError(f"{context} references unknown repository {repo_id!r}")
    distribution = _text(item, "distribution", context)
    if distribution not in ALLOWED_DISTRIBUTIONS:
        raise ManifestError(f"{context}.distribution must be one of {ALLOWED_DISTRIBUTIONS}")
    artifacts_raw = item.get("artifacts")
    if not isinstance(artifacts_raw, list) or not artifacts_raw:
        raise ManifestError(f"{context}.artifacts must be a non-empty list")
    artifacts = tuple(
        _artifact(candidate, f"{context}.artifacts[{index}]", seen_names)
        for index, candidate in enumerate(artifacts_raw)
    )
    missing_excerpts = [artifact.name for artifact in artifacts if not artifact.excerpts]
    incomplete_excerpts = [
        artifact.name
        for artifact in artifacts
        if artifact.excerpts
        and {excerpt.input for excerpt in artifact.excerpts} != set(artifact.inputs)
    ]
    if missing_excerpts:
        raise ManifestError(
            f"{context} artifacts require source excerpts: {', '.join(missing_excerpts)}"
        )
    if incomplete_excerpts:
        raise ManifestError(
            f"{context} artifacts must select from every input: {', '.join(incomplete_excerpts)}"
        )
    override = item.get("license_override")
    if distribution == "local-only" and override is None:
        raise ManifestError(f"{context} is local-only but has no explicit license_override")
    override_license = (
        _license(override, f"{context}.license_override") if override is not None else None
    )
    if web_id is not None and (distribution != "committed" or override is not None):
        raise ManifestError(
            f"{context}: web collections require committed output without overrides"
        )
    if web_id is not None:
        pages = {page.path for page in web_sources[web_id].pages}
        if any(set(artifact.inputs) - pages for artifact in artifacts):
            raise ManifestError(f"{context}: inputs must be explicitly enumerated web pages")
    effective_license = (
        web_sources[web_id].license
        if web_id is not None
        else override_license or repositories[repo_id].license
    )
    if distribution == "committed" and not effective_license.allow_committed_output:
        raise ManifestError(
            f"{context} cannot use committed distribution under its recorded license policy"
        )
    return Collection(
        id=str(collection_id),
        repository=repo_id,
        distribution=distribution,
        description=_text(item, "description", context),
        artifacts=artifacts,
        license_override=override_license,
        web_source=web_id,
    )


def _collections(
    data: dict[str, Any],
    repositories: dict[str, Repository],
    seen_names: set[str],
    web_sources: dict[str, WebSource],
) -> dict[str, Collection]:
    raw = require_mapping(data.get("collections"), "collections")
    return {
        str(collection_id): _collection(collection_id, item, repositories, seen_names, web_sources)
        for collection_id, item in raw.items()
    }


def _catalog_items(data: dict[str, Any], seen_names: set[str]) -> tuple[CatalogOnly, ...]:
    raw = data.get("catalog_only", [])
    if not isinstance(raw, list):
        raise ManifestError("catalog_only must be a list")
    items: list[CatalogOnly] = []
    for index, candidate in enumerate(raw):
        context = f"catalog_only[{index}]"
        item = require_mapping(candidate, context)
        item_id = _text(item, "id", context)
        if not NAME_RE.fullmatch(item_id):
            raise ManifestError(f"{context}.id has an invalid identifier")
        if item_id in seen_names:
            raise ManifestError(f"Duplicate skill or catalog id: {item_id}")
        seen_names.add(item_id)
        tags_raw = item.get("tags", [])
        if not isinstance(tags_raw, list) or not all(isinstance(tag, str) for tag in tags_raw):
            raise ManifestError(f"{context}.tags must be a list of strings")
        items.append(
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
    return tuple(items)


def _source_path_policies(
    data: dict[str, Any], repositories: dict[str, Repository]
) -> tuple[SourcePathPolicy, ...]:
    raw = data.get("source_path_policies", [])
    if not isinstance(raw, list):
        raise ManifestError("source_path_policies must be a list")
    policies: list[SourcePathPolicy] = []
    for index, candidate in enumerate(raw):
        context = f"source_path_policies[{index}]"
        item = require_mapping(candidate, context)
        repository = _text(item, "repository", context)
        if repository not in repositories:
            raise ManifestError(f"{context} references unknown repository {repository!r}")
        distribution = _text(item, "required_distribution", context)
        if distribution not in {*ALLOWED_DISTRIBUTIONS, "catalog-only"}:
            raise ManifestError(
                f"{context}.required_distribution must be committed, local-only, or catalog-only"
            )
        policies.append(
            SourcePathPolicy(
                repository=repository,
                pattern=_safe_relative(_text(item, "pattern", context), f"{context}.pattern"),
                required_distribution=distribution,
                reason=_text(item, "reason", context),
            )
        )
    _require_protected_path_policies(repositories, policies)
    return tuple(policies)


def _require_protected_path_policies(
    repositories: dict[str, Repository], policies: list[SourcePathPolicy]
) -> None:
    for repository in repositories.values():
        identity = _github_repository_identity(repository.url)
        required = REQUIRED_CANONICAL_PATH_POLICIES.get(identity or "", set())
        actual = {
            (policy.pattern, policy.required_distribution)
            for policy in policies
            if policy.repository == repository.id
        }
        missing = sorted(required - actual)
        if not missing:
            continue
        formatted = ", ".join(f"{pattern} -> {distribution}" for pattern, distribution in missing)
        raise ManifestError(
            f"Repository {repository.id} is missing mandatory source path policies: {formatted}"
        )


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        return require_mapping(strict_safe_load(path.read_text(encoding="utf-8")), "corpus")
    except OSError as exc:
        raise ManifestError(f"Cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {path}: {exc}") from exc


def load_manifest(path: Path | None = None) -> Manifest:
    """Parse corpus.yaml and enforce its source and distribution policies."""
    manifest_path = (path or (find_project_root() / "corpus.yaml")).resolve()
    data = _read_manifest(manifest_path)
    schema_version = data.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version not in {2, 3}
    ):
        raise ManifestError(f"Unsupported schema_version: {schema_version!r}")
    if schema_version == 2 and any(key in data for key in ("web_sources", "packs")):
        raise ManifestError("web_sources and packs require schema_version 3")
    generator = require_mapping(data.get("generator"), "generator")
    canonical_python = _text(generator, "python", "generator")
    if not re.fullmatch(r"3\.\d+\.\d+", canonical_python):
        raise ManifestError("generator.python must be an exact Python 3 version such as 3.13.7")

    roots = _generated_roots(data)
    repositories = _repositories(data)
    web_sources = _web_sources(data)
    seen_names: set[str] = set()
    collections = _collections(data, repositories, seen_names, web_sources)
    return Manifest(
        path=manifest_path,
        schema_version=schema_version,
        canonical_python=canonical_python,
        generated_roots=roots,
        repositories=repositories,
        collections=collections,
        catalog_only=_catalog_items(data, seen_names),
        source_path_policies=_source_path_policies(data, repositories),
        web_sources=web_sources,
        packs=_packs(data, collections),
    )
