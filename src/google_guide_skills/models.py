"""Typed manifest and result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ManifestError


@dataclass(frozen=True)
class LicenseInfo:
    """License terms and the upstream evidence used to verify them."""

    spdx: str
    name: str
    url: str
    attribution: str
    audited: str
    allow_committed_output: bool
    evidence_path: str | None = None
    evidence_glob: str | None = None
    evidence_contains: str | None = None
    warning: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return populated fields in provenance format."""
        values = {
            "spdx": self.spdx,
            "name": self.name,
            "url": self.url,
            "attribution": self.attribution,
            "audited": self.audited,
            "allow_committed_output": self.allow_committed_output,
            "evidence_path": self.evidence_path,
            "evidence_glob": self.evidence_glob,
            "evidence_contains": self.evidence_contains,
            "warning": self.warning,
        }
        return {key: value for key, value in values.items() if value is not None}


@dataclass(frozen=True)
class SupplementalLicense:
    """An additional license that applies to part of an artifact."""

    spdx: str
    name: str
    url: str
    attribution: str
    scope: str
    license_file: str
    evidence_contains: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        """Return the supplemental license in provenance format."""
        return {
            "spdx": self.spdx,
            "name": self.name,
            "url": self.url,
            "attribution": self.attribution,
            "scope": self.scope,
            "license_file": self.license_file,
            "evidence_contains": self.evidence_contains,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class Repository:
    """A pinned upstream repository and its default license."""

    id: str
    url: str
    revision: str
    default_branch: str
    license: LicenseInfo


@dataclass(frozen=True)
class SourceExcerpt:
    """Source blocks selected for a generated skill."""

    input: str
    heading: str
    blocks: tuple[int, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the excerpt selector in provenance format."""
        return {"input": self.input, "heading": self.heading, "blocks": list(self.blocks)}


@dataclass(frozen=True)
class Artifact:
    """One generated skill within a source collection."""

    name: str
    title: str
    description: str
    tags: tuple[str, ...]
    inputs: tuple[str, ...]
    excerpts: tuple[SourceExcerpt, ...]
    license_note: str | None = None
    supplemental_licenses: tuple[SupplementalLicense, ...] = ()


@dataclass(frozen=True)
class Collection:
    """Artifacts that share a repository and distribution policy."""

    id: str
    repository: str
    distribution: str
    description: str
    artifacts: tuple[Artifact, ...]
    license_override: LicenseInfo | None = None


@dataclass(frozen=True)
class CatalogOnly:
    """A known guide that the generator does not currently package."""

    id: str
    title: str
    url: str
    license: str
    status: str
    reason: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SourcePathPolicy:
    """A distribution restriction for matching upstream paths."""

    repository: str
    pattern: str
    required_distribution: str
    reason: str


@dataclass(frozen=True)
class Manifest:
    """The validated corpus configuration used by every command."""

    path: Path
    schema_version: int
    canonical_python: str
    generated_roots: dict[str, str]
    repositories: dict[str, Repository]
    collections: dict[str, Collection]
    catalog_only: tuple[CatalogOnly, ...] = field(default_factory=tuple)
    source_path_policies: tuple[SourcePathPolicy, ...] = field(default_factory=tuple)

    @property
    def project_root(self) -> Path:
        """Return the directory containing corpus.yaml."""
        return self.path.parent

    def root_for(self, distribution: str) -> Path:
        """Return the generated root for a supported distribution."""
        keys = {"committed": "committed", "local-only": "local_only"}
        try:
            key = keys[distribution]
        except KeyError as exc:
            raise ManifestError(f"Unknown distribution: {distribution}") from exc
        return self.project_root / self.generated_roots[key]

    def license_for(self, collection: Collection) -> LicenseInfo:
        """Return the collection override or its repository license."""
        return collection.license_override or self.repositories[collection.repository].license

    def artifacts(self, include_local: bool = False) -> list[tuple[Collection, Artifact]]:
        """List artifacts allowed by the requested distribution scope."""
        values: list[tuple[Collection, Artifact]] = []
        for collection in self.collections.values():
            if include_local or collection.distribution == "committed":
                values.extend((collection, artifact) for artifact in collection.artifacts)
        return values


@dataclass(frozen=True)
class BuiltSkill:
    """The output and source list for one completed build."""

    collection: str
    name: str
    distribution: str
    path: Path
    source_files: tuple[str, ...]


@dataclass(frozen=True)
class ValidationIssue:
    """One validation finding with a project-relative path."""

    severity: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Return the finding in report format."""
        return {"severity": self.severity, "path": self.path, "message": self.message}


def require_mapping(value: Any, context: str) -> dict[str, Any]:
    """Return a manifest mapping or raise an error naming its context."""
    if not isinstance(value, dict):
        raise ManifestError(f"{context} must be a mapping")
    return value
