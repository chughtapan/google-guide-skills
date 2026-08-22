"""Generate the machine-readable catalog and the agent-facing index skill."""

from __future__ import annotations

import json
import shutil
from hashlib import sha256
from pathlib import Path

from . import __version__
from .errors import GoogleGuideSkillsError
from .models import Manifest
from .path_policy import require_safe_project_path
from .project_license import verified_project_license, wrapper_license_metadata


def catalog_records(manifest: Manifest) -> list[dict[str, object]]:
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
                    supplemental.to_dict()
                    for supplemental in artifact.supplemental_licenses
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


def render_catalog_markdown(
    records: list[dict[str, object]], *, from_index_skill: bool = False
) -> str:
    lines = [
        "# Google Guides Skill Catalog",
        "",
        "This catalog is generated from `corpus.yaml`. `committed` skills are redistributable",
        "under their recorded source licenses. `local-only` skills are recipes whose generated",
        "output must remain ignored and must not be redistributed.",
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
        if linkable and from_index_skill:
            label = f"[`{skill_id}`](../../{skill_id}/SKILL.md)"
        elif linkable:
            label = f"[`{skill_id}`](../{path}/SKILL.md)"
        else:
            label = f"`{skill_id}`"
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


def render_index_skill() -> str:
    return """---
name: google-guides-index
description: >-
  Use only when several Google guide skills could apply, the request spans guide categories, or
  the right guide is unclear. Route to the narrowest installed skill and identify catalog-only or
  local-only coverage gaps. Do not use when one named language, library, or code-review role
  clearly selects a direct skill.
---

# Google Guides Index

Read [the generated catalog](references/catalog.md), select the narrowest guide that matches the
task, and then read that guide's `SKILL.md`. Prefer project instructions and current requirements
when they conflict with upstream guidance.

Treat distribution labels as hard boundaries:

- Use `committed` skills normally under their recorded source licenses.
- Generate `local-only` skills only for private local use, keep them under `.generated/`, and do
  not redistribute them.
- Treat `catalog-only` entries as discovery leads, not installed guidance.

When no single guide covers the task, name the small set of guides you are combining and keep
their scopes distinct.
"""


def write_catalog(manifest: Manifest) -> tuple[Path, Path]:
    records = catalog_records(manifest)
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
    markdown = render_catalog_markdown(records)
    markdown_path.write_text(markdown, encoding="utf-8")

    index_dir = require_safe_project_path(
        manifest.project_root,
        manifest.project_root / "skills" / "google-guides-index",
        context="Index skill output",
        error_type=GoogleGuideSkillsError,
    )
    references = index_dir / "references"
    require_safe_project_path(
        manifest.project_root,
        references,
        context="Index skill output",
        error_type=GoogleGuideSkillsError,
    )
    references.mkdir(parents=True, exist_ok=True)
    skill_path = index_dir / "SKILL.md"
    reference_path = references / "catalog.md"
    license_path = references / "LICENSE.txt"
    source_path = references / "source.json"
    for path in (skill_path, reference_path, license_path, source_path):
        require_safe_project_path(
            manifest.project_root,
            path,
            context="Index skill output",
            error_type=GoogleGuideSkillsError,
        )
    skill_path.write_text(render_index_skill(), encoding="utf-8")
    reference_path.write_text(
        render_catalog_markdown(records, from_index_skill=True), encoding="utf-8"
    )
    project_license = verified_project_license(manifest.project_root)
    shutil.copyfile(project_license, license_path)
    source_path.write_text(
        json.dumps(
            {
                "artifact": "google-guides-index",
                "authorship": "Project-authored routing index generated from corpus.yaml.",
                "collection": "authored-index",
                "distribution": "committed",
                "generated_by": f"google-guide-skills/{__version__}",
                "license": wrapper_license_metadata("references/LICENSE.txt"),
                "source_manifest": {
                    "path": "corpus.yaml",
                    "sha256": sha256(
                        (manifest.project_root / "corpus.yaml").read_bytes()
                    ).hexdigest(),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return json_path, markdown_path
