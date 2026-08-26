"""Generate the human-readable and machine-readable guide catalogs."""

from __future__ import annotations

import json
from pathlib import Path

from .errors import GoogleGuideSkillsError
from .models import Manifest
from .path_policy import require_safe_project_path
from .project_license import wrapper_license_metadata


def catalog_records(manifest: Manifest) -> list[dict[str, object]]:
    """Build catalog records from every generated and catalog-only entry."""
    records: list[dict[str, object]] = []
    for collection, artifact in manifest.artifacts(include_local=True):
        repository = manifest.repositories[collection.repository]
        license_info = manifest.license_for(collection)
        output = manifest.root_for(collection.distribution) / artifact.name
        records.append(
            {
                "id": artifact.name,
                "title": artifact.title,
                "description": artifact.description,
                "tags": list(artifact.tags),
                "collection": collection.id,
                "distribution": collection.distribution,
                # The committed catalog must not change based on ignored local state.
                "generated": collection.distribution == "committed"
                and (output / "SKILL.md").is_file(),
                "path": output.relative_to(manifest.project_root).as_posix(),
                "license": license_info.spdx,
                "wrapper_license": wrapper_license_metadata(),
                "supplemental_licenses": [
                    supplemental.to_dict() for supplemental in artifact.supplemental_licenses
                ],
                "source": repository.url,
                "revision": repository.revision,
            }
        )
    for item in manifest.catalog_only:
        records.append(
            {
                "id": item.id,
                "title": item.title,
                "description": item.reason,
                "tags": list(item.tags),
                "collection": "catalog-only",
                "distribution": "catalog-only",
                "generated": False,
                "path": None,
                "license": item.license,
                "source": item.url,
                "revision": None,
                "status": item.status,
            }
        )
    return sorted(records, key=lambda record: str(record["id"]))


def render_catalog_markdown(records: list[dict[str, object]]) -> str:
    """Render catalog records as a Markdown table."""
    lines = [
        "# Google Guides Skill Catalog",
        "",
        "This catalog is generated from `corpus.yaml`. `committed` skills are redistributable",
        "under their recorded source licenses. Every generated skill contains selected source",
        "excerpts. `local-only` output must not be redistributed.",
        "",
        "| Skill | Scope | Distribution | License | Tags | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        skill_id = str(record["id"])
        path = record.get("path")
        linkable = (
            path and record.get("distribution") == "committed" and record.get("generated") is True
        )
        label = f"[`{skill_id}`](../{path}/SKILL.md)" if linkable else f"`{skill_id}`"
        tags = ", ".join(str(tag) for tag in record.get("tags", []))
        source = str(record["source"])
        description = " ".join(str(record.get("description", "")).split())
        supplemental = record.get("supplemental_licenses", [])
        additional_spdx = [
            str(item["spdx"])
            for item in supplemental
            if isinstance(item, dict) and item.get("spdx")
        ]
        license_label = " + ".join([str(record["license"]), *additional_spdx])
        if record.get("wrapper_license") and record["license"] != "Apache-2.0":
            license_label += " + Apache-2.0 (wrapper)"
        lines.append(
            f"| {label} | {description} | {record['distribution']} | {license_label} | "
            f"{tags} | "
            f"[upstream]({source}) |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _catalog_paths(manifest: Manifest) -> tuple[Path, Path]:
    catalog_dir = require_safe_project_path(
        manifest.project_root,
        manifest.project_root / "catalog",
        context="Catalog output",
        error_type=GoogleGuideSkillsError,
    )
    catalog_dir.mkdir(parents=True, exist_ok=True)
    json_path = catalog_dir / "catalog.json"
    markdown_path = catalog_dir / "catalog.md"
    for path in (json_path, markdown_path):
        require_safe_project_path(
            manifest.project_root,
            path,
            context="Catalog output",
            error_type=GoogleGuideSkillsError,
        )
    return json_path, markdown_path


def _write_catalog_files(
    records: list[dict[str, object]], json_path: Path, markdown_path: Path
) -> None:
    json_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_manifest": "corpus.yaml",
                "skills": records,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_catalog_markdown(records), encoding="utf-8")


def write_catalog(manifest: Manifest) -> tuple[Path, Path]:
    """Write the catalog files and return their paths."""
    records = catalog_records(manifest)
    json_path, markdown_path = _catalog_paths(manifest)
    _write_catalog_files(records, json_path, markdown_path)
    return json_path, markdown_path
